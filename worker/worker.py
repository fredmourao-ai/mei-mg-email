"""
Worker que consome a fila de lotes e dispara os e-mails respeitando limites.

Para Exchange Online, o controle usa janela movel de 24 horas e uma trava
advisory no Postgres garante somente um worker de envio ativo. HTTP 202 do
Microsoft Graph e registrado como `submitted`, nunca como entrega comprovada.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.email_provider import get_email_provider
from app.queue_manager import repor_fila_automatica

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mei_mg_email.worker")
WORKER_ADVISORY_LOCK_ID = 100002026
MAX_TENTATIVAS_TRANSITORIAS = 5
SENDER_BLOCK_SENTINEL = Path(__file__).resolve().parents[1] / "runtime" / "sender_blocked.pause"


def montar_corpo(template: str, empresa: dict) -> str:
    unsubscribe_url = f"{settings.base_url_descadastro}?{urlencode({'cnpj': empresa['cnpj'], 'email': empresa['email']})}"
    texto = template
    for chave, valor in {
        "razao_social": empresa.get("razao_social") or "",
        "nome_fantasia": empresa.get("nome_fantasia") or "",
        "cnpj": empresa["cnpj"],
        "unsubscribe_url": unsubscribe_url,
    }.items():
        texto = texto.replace("{{" + chave + "}}", valor)
    return texto


def obter_envios_ultimas_24h(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*)
              from mei_email.envios
             where status::text in ('submitted', 'enviado')
               and enviado_em >= now() - interval '24 hours'
            """
        )
        return cur.fetchone()[0]


def limite_operacional_24h() -> int:
    return min(settings.meta_envios_por_dia, settings.max_envios_por_dia)


def _erro_transitorio(error: str | None) -> bool:
    texto = (error or "").casefold()
    marcadores = (
        "429",
        "toomanyrequests",
        "too many requests",
        "throttl",
        "serverbusy",
        "serviceunavailable",
        "service unavailable",
        "temporar",
        "timeout",
        "timed out",
        "http_500",
        "http_502",
        "http_503",
        "http_504",
        "connection reset",
        "connection aborted",
    )
    return any(marcador in texto for marcador in marcadores)


def _registrar_sender_blocked_pause(error: str | None) -> None:
    """Abre um circuito persistente para impedir novas tentativas de envio.

    O arquivo fica fora do banco e sobrevive a restart do worker. A retomada e
    deliberadamente manual: somente remova o sentinel apos confirmar no Exchange
    que o remetente saiu de Restricted entities / AS(42004).
    """
    SENDER_BLOCK_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
    detalhe = (error or "sender_blocked sem detalhe").strip()
    conteudo = (
        f"blocked_at_utc={datetime.now(timezone.utc).isoformat()}\n"
        f"sender=naoresponda@dev.shopvivaliz.com.br\n"
        f"error={detalhe[:1000]}\n"
    )
    SENDER_BLOCK_SENTINEL.write_text(conteudo, encoding="utf-8")


def _sender_blocked_pause_ativo() -> bool:
    return SENDER_BLOCK_SENTINEL.is_file()


def _registrar_falhas_campanha(conn, campanha_id, falhas: int) -> None:
    if not falhas:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.campanhas
               set total_falhas = total_falhas + %s
             where id = %s
            """,
            (falhas, campanha_id),
        )
    conn.commit()


def _recolocar_lote_pendente(conn, lote_id, motivo: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.lotes
               set status = 'pendente',
                   iniciado_em = null,
                   concluido_em = null,
                   erro = %s
             where id = %s
            """,
            (motivo[:1000], lote_id),
        )
    conn.commit()


def recuperar_lotes_travados(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.lotes
               set status = 'pendente',
                   iniciado_em = null,
                   erro = 'recuperado automaticamente apos worker interrompido'
             where status = 'processando'
               and iniciado_em < now() - interval '15 minutes'
            """
        )
        recuperados = cur.rowcount
    conn.commit()
    return recuperados


def _ja_submetido_ou_entregue(conn: psycopg.Connection, envio_id, email: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            select 1
              from mei_email.envios
             where id <> %s
               and status::text in ('submitted', 'enviado')
               and lower(btrim(email::text)) = lower(btrim(%s))
             limit 1
            """,
            (envio_id, email),
        )
        return cur.fetchone() is not None


def processar_lote(conn: psycopg.Connection, lote: dict, provider) -> None:
    intervalo_entre_envios = 60.0 / max(settings.rate_limit_envios_por_minuto, 1)
    limite_24h = limite_operacional_24h()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select e.id as envio_id, e.cnpj, e.email, e.tentativas,
                   c.assunto, c.corpo_template,
                   emp.razao_social, emp.nome_fantasia,
                   emp.situacao_cadastral
              from mei_email.envios e
              join mei_email.campanhas c on c.id = e.campanha_id
              join mei_email.empresas emp on emp.cnpj = e.cnpj
             where e.lote_id = %s
               and e.status = 'pendente'
             order by e.criado_em
            """,
            (lote["id"],),
        )
        envios = cur.fetchall()

    submetidos = 0
    falhas = 0

    for envio in envios:
        envios_24h = obter_envios_ultimas_24h(conn)
        if envios_24h >= limite_24h:
            _registrar_falhas_campanha(conn, lote["campanha_id"], falhas)
            _recolocar_lote_pendente(
                conn,
                lote["id"],
                f"meta movel de 24h atingida: {envios_24h}/{limite_24h}",
            )
            logger.warning(
                "Meta movel de 24h atingida: %d/%d. Lote %s devolvido para a fila.",
                envios_24h,
                limite_24h,
                lote["id"],
            )
            return

        if envio["situacao_cadastral"] != "ATIVA":
            _atualizar_envio(conn, envio["envio_id"], "bloqueado", erro="empresa deixou de estar ATIVA apos enfileiramento")
            continue

        if _ja_submetido_ou_entregue(conn, envio["envio_id"], envio["email"]):
            _atualizar_envio(conn, envio["envio_id"], "descartado", erro="supressao global: destinatario ja submitted/enviado anteriormente")
            continue

        corpo = montar_corpo(envio["corpo_template"], envio)
        resultado = provider.send(to=envio["email"], subject=envio["assunto"], body=corpo)

        if resultado.success:
            provider_status = getattr(resultado, "status", None)
            if provider_status != "submitted":
                raise RuntimeError(f"status Graph inesperado apos sendMail: {provider_status!r}")
            _atualizar_envio(
                conn,
                envio["envio_id"],
                "submitted",
                provider_message_id=resultado.message_id,
            )
            submetidos += 1
        elif getattr(resultado, "status", None) == "sender_blocked":
            _atualizar_envio(conn, envio["envio_id"], "sender_blocked", erro=resultado.error)
            falhas += 1
            _registrar_falhas_campanha(conn, lote["campanha_id"], falhas)
            _recolocar_lote_pendente(
                conn,
                lote["id"],
                f"sender_blocked; circuito aberto: {resultado.error or 'sem detalhe'}",
            )
            _registrar_sender_blocked_pause(resultado.error)
            logger.critical(
                "SENDER_BLOCKED: circuito persistente aberto em %s. Nenhum novo envio sera tentado ate remocao manual apos desbloqueio no Exchange.",
                SENDER_BLOCK_SENTINEL,
            )
            return
        elif _erro_transitorio(resultado.error) and envio["tentativas"] + 1 < MAX_TENTATIVAS_TRANSITORIAS:
            _atualizar_envio(conn, envio["envio_id"], "pendente", erro=resultado.error)
            _registrar_falhas_campanha(conn, lote["campanha_id"], falhas)
            _recolocar_lote_pendente(
                conn,
                lote["id"],
                f"falha transitoria; envio sera tentado novamente: {resultado.error or 'sem detalhe'}",
            )
            backoff_local = max(10.0, intervalo_entre_envios * 5)
            retry_after = getattr(resultado, "retry_after_seconds", None)
            espera = max(backoff_local, float(retry_after or 0))
            logger.warning(
                "Falha transitoria no envio %s; lote %s reprogramado. Aguarda %.1fs antes de nova tentativa.",
                envio["envio_id"],
                lote["id"],
                espera,
            )
            time.sleep(espera)
            return
        else:
            _atualizar_envio(conn, envio["envio_id"], "falhou", erro=resultado.error)
            falhas += 1

        time.sleep(intervalo_entre_envios)

    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.lotes
               set status = 'concluido', concluido_em = now(), erro = null
             where id = %s
            """,
            (lote["id"],),
        )
    conn.commit()
    _registrar_falhas_campanha(conn, lote["campanha_id"], falhas)

    logger.info(
        "Lote %s (campanha %s) concluido: %d submitted, %d falhas",
        lote["numero"],
        lote["campanha_id"],
        submetidos,
        falhas,
    )


def _atualizar_envio(conn, envio_id, status, provider_message_id=None, erro=None):
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.envios
               set status = %s,
                   tentativas = tentativas + 1,
                   provider_message_id = coalesce(%s, provider_message_id),
                   erro = %s,
                   enviado_em = case when %s in ('submitted', 'enviado') then now() else enviado_em end,
                   submitted_at = case when %s = 'submitted' then now() else submitted_at end
             where id = %s
            returning status::text, provider_message_id, enviado_em, submitted_at
            """,
            (status, provider_message_id, erro, status, status, envio_id),
        )
        persisted = cur.fetchone()
        if persisted is None:
            conn.rollback()
            raise RuntimeError(f"envio {envio_id} desapareceu antes de persistir status {status}")
        if isinstance(persisted, dict):
            persisted_status = persisted.get("status")
            persisted_provider_message_id = persisted.get("provider_message_id")
            persisted_enviado_em = persisted.get("enviado_em")
            persisted_submitted_at = persisted.get("submitted_at")
        else:
            persisted_status, persisted_provider_message_id, persisted_enviado_em, persisted_submitted_at = persisted
        if persisted_status != status:
            conn.commit()
            raise RuntimeError(
                f"envio {envio_id} persistiu como {persisted_status} em vez de {status}"
            )
        if status == "submitted" and (not persisted_provider_message_id or persisted_enviado_em is None or persisted_submitted_at is None):
            conn.rollback()
            raise RuntimeError(
                f"envio {envio_id} sem prova persistida de submissao (provider/timestamps)"
            )
        if status == "enviado":
            cur.execute(
                """
                update mei_email.empresas
                   set enviado = true,
                       enviado_em = now()
                 where lower(btrim(email::text)) = lower(btrim((select email::text from mei_email.envios where id = %s)))
                """,
                (envio_id,),
            )
    conn.commit()


def pegar_proximo_lote(conn: psycopg.Connection, campanha_id: str | None = None) -> dict | None:
    with conn.cursor(row_factory=dict_row) as cur:
        if campanha_id:
            cur.execute(
                """
                select id, campanha_id, numero
                  from mei_email.lotes
                 where status = 'pendente'
                   and campanha_id = %s
                 order by criado_em, numero
                 for update skip locked
                 limit 1
                """,
                (campanha_id,),
            )
        else:
            cur.execute(
                """
                select id, campanha_id, numero
                  from mei_email.lotes
                 where status = 'pendente'
                 order by criado_em, numero
                 for update skip locked
                 limit 1
                """
            )
        lote = cur.fetchone()
        if lote is None:
            # A SELECT ... FOR UPDATE inicia uma transacao mesmo sem linhas.
            # Fechar imediatamente evita sessoes "idle in transaction" que
            # seguram locks de relacao e podem bloquear futuras migrations.
            conn.commit()
            return None

        cur.execute(
            """
            update mei_email.lotes
               set status = 'processando',
                   iniciado_em = now(),
                   tentativas = tentativas + 1,
                   erro = null
             where id = %s
            """,
            (lote["id"],),
        )
    conn.commit()
    return lote


def run() -> None:
    if settings.max_envios_por_dia > 10000:
        raise RuntimeError("MAX_ENVIOS_POR_DIA nao pode ultrapassar 10000 para Exchange Online.")
    if settings.meta_envios_por_dia <= 0:
        raise RuntimeError("META_ENVIOS_POR_DIA precisa ser maior que zero.")
    if settings.meta_envios_por_dia > settings.max_envios_por_dia:
        raise RuntimeError("META_ENVIOS_POR_DIA nao pode ultrapassar MAX_ENVIOS_POR_DIA.")
    if settings.rate_limit_envios_por_minuto > 30:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO nao pode ultrapassar 30 no Exchange Online.")
    if settings.rate_limit_envios_por_minuto <= 0:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO precisa ser maior que zero.")
    if settings.queue_min_pending < 1:
        raise RuntimeError("QUEUE_MIN_PENDING precisa ser pelo menos 1.")
    if settings.queue_target_pending <= settings.queue_min_pending:
        raise RuntimeError("QUEUE_TARGET_PENDING precisa ser maior que QUEUE_MIN_PENDING.")

    provider = get_email_provider(settings.email_provider)
    logger.info(
        "Worker iniciado. provedor=%s rate_limit=%d/min meta_24h=%d teto_24h=%d poll=%ds fila_min=%d fila_target=%d",
        settings.email_provider,
        settings.rate_limit_envios_por_minuto,
        settings.meta_envios_por_dia,
        settings.max_envios_por_dia,
        settings.worker_poll_interval_segundos,
        settings.queue_min_pending,
        settings.queue_target_pending,
    )

    with psycopg.connect(settings.database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("select pg_try_advisory_lock(%s)", (WORKER_ADVISORY_LOCK_ID,))
            if not cur.fetchone()[0]:
                raise RuntimeError(
                    "Ja existe outro worker de disparo ativo. Mantendo instancia unica para respeitar o rate limit global."
                )

        recuperados = recuperar_lotes_travados(conn)
        if recuperados:
            logger.warning("Recuperados %d lotes que estavam presos em processando.", recuperados)

        while True:
            try:
                if _sender_blocked_pause_ativo():
                    logger.critical(
                        "Worker pausado por sender_blocked. Sentinel=%s. Confirme desbloqueio no Exchange antes de remover o arquivo.",
                        SENDER_BLOCK_SENTINEL,
                    )
                    time.sleep(max(settings.worker_poll_interval_segundos, 60))
                    continue

                # Repor antes de consumir o proximo lote evita que a fila seque.
                # A cota de 24h continua sendo validada antes de cada envio.
                repor_fila_automatica(conn)
                lote = pegar_proximo_lote(conn)
                if lote is None:
                    time.sleep(settings.worker_poll_interval_segundos)
                    continue
                processar_lote(conn, lote, provider)
            except Exception:
                logger.exception("Erro processando lote ou repondo fila -- worker continua rodando")
                conn.rollback()
                time.sleep(settings.worker_poll_interval_segundos)


if __name__ == "__main__":
    run()
