"""
Worker que consome a fila de lotes e dispara os e-mails respeitando limites.

Para Exchange Online, o controle usa janela movel de 24 horas e uma trava
advisory no Postgres garante somente um worker de envio ativo. Pausas por cota
e falhas transitorias devolvem o lote para a fila sem perder os envios ja
confirmados, e lotes abandonados por crash podem ser recuperados no startup.
"""
from __future__ import annotations

import logging
import re
import time
from urllib.parse import urlencode

import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.email_provider import get_email_provider
from app.send_control import email_sends_paused, pause_email_sends

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mei_mg_email.worker")
WORKER_ADVISORY_LOCK_ID = 100002026
MAX_TENTATIVAS_TRANSITORIAS = 5


def _extrair_ndr_code(error: str | None) -> str | None:
    texto = error or ""
    match = re.search(r"AS\(\d+\)", texto, flags=re.IGNORECASE)
    if match:
        return match.group(0).upper()
    match = re.search(r"\b\d\.\d\.\d+\b", texto, flags=re.IGNORECASE)
    if match:
        return match.group(0).upper()
    return None


def _classificar_falha_final(error: str | None) -> tuple[str, str | None, str]:
    texto = (error or "").casefold()
    ndr_code = _extrair_ndr_code(error)

    if any(
        marcador in texto
        for marcador in (
            "as(42004)",
            "errorsendasdenied",
            "bad outbound sender",
            "access denied",
            "5.1.8",
        )
    ):
        return "sender_blocked", ndr_code or "AS(42004)", error or "sender blocked"

    if any(
        marcador in texto
        for marcador in (
            "5.4.312",
            "inforecords",
            "dns query failed",
            "mailbox not found",
            "user unknown",
            "invalid recipient",
            "recipient not found",
            "5.1.1",
        )
    ):
        return "bounce_permanent", ndr_code, error or "permanent bounce"

    if any(
        marcador in texto
        for marcador in (
            "mailbox full",
            "4.2.2",
            "4.4.1",
            "4.4.2",
            "temporary",
            "timed out",
            "timeout",
        )
    ):
        return "bounce_temporary", ndr_code, error or "temporary bounce"

    return "failed", ndr_code, error or "send failed"


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


class SenderBlockedError(RuntimeError):
    pass


def obter_envios_ultimas_24h(conn: psycopg.Connection) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*)
              from mei_email.envios
             where status in ('submitted', 'delivered', 'enviado')
               and coalesce(submitted_at, enviado_em, criado_em) >= now() - interval '24 hours'
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


def _registrar_contadores_campanha(conn, campanha_id, enviados: int, falhas: int) -> None:
    if not enviados and not falhas:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.campanhas
               set total_enviados = total_enviados + %s,
                   total_falhas = total_falhas + %s
             where id = %s
            """,
            (enviados, falhas, campanha_id),
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


def _marcar_envio_processando(conn, envio_id) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.envios
               set status = 'processing',
                   erro = null,
                   last_error = null
             where id = %s
            """,
            (envio_id,),
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


def processar_lote(conn: psycopg.Connection, lote: dict, provider) -> None:
    intervalo_entre_envios = 60.0 / max(settings.rate_limit_envios_por_minuto, 1)
    limite_24h = limite_operacional_24h()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select e.id as envio_id, e.cnpj, e.email, e.tentativas,
                   c.assunto, c.corpo_template,
                   emp.razao_social, emp.nome_fantasia,
                   emp.opt_out, emp.situacao_cadastral,
                   emp.marketing_autorizado
              from mei_email.envios e
              join mei_email.campanhas c on c.id = e.campanha_id
              join mei_email.empresas emp on emp.cnpj = e.cnpj
             where e.lote_id = %s
               and e.status = 'pending'
             order by e.criado_em
            """,
            (lote["id"],),
        )
        envios = cur.fetchall()

    enviados = 0
    falhas = 0

    for envio in envios:
        envios_24h = obter_envios_ultimas_24h(conn)
        if envios_24h >= limite_24h:
            _registrar_contadores_campanha(conn, lote["campanha_id"], enviados, falhas)
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

        if envio["opt_out"]:
            _atualizar_envio(
                conn,
                envio["envio_id"],
                "suppressed",
                erro="opt-out registrado apos enfileiramento",
                last_error="opt-out registrado apos enfileiramento",
                incrementar_tentativas=False,
            )
            continue

        if envio["situacao_cadastral"] != "ATIVA":
            _atualizar_envio(
                conn,
                envio["envio_id"],
                "cancelled",
                erro="empresa deixou de estar ATIVA apos enfileiramento",
                last_error="empresa deixou de estar ATIVA apos enfileiramento",
                incrementar_tentativas=False,
            )
            continue

        if not envio["marketing_autorizado"]:
            _atualizar_envio(
                conn,
                envio["envio_id"],
                "cancelled",
                erro="comunicacao comercial nao autorizada no cadastro",
                last_error="comunicacao comercial nao autorizada no cadastro",
                incrementar_tentativas=False,
            )
            continue

        if _email_suprimido(conn, envio["email"]):
            _atualizar_envio(
                conn,
                envio["envio_id"],
                "suppressed",
                erro="destinatario consta em suppression list",
                last_error="destinatario consta em suppression list",
                incrementar_tentativas=False,
            )
            continue

        _marcar_envio_processando(conn, envio["envio_id"])
        corpo = montar_corpo(envio["corpo_template"], envio)
        resultado = provider.send(to=envio["email"], subject=envio["assunto"], body=corpo)

        if resultado.success:
            _atualizar_envio(
                conn,
                envio["envio_id"],
                "submitted",
                provider_message_id=resultado.message_id,
                graph_request_id=resultado.message_id,
                erro=None,
                last_error=None,
                incrementar_tentativas=True,
            )
            enviados += 1
        elif _erro_transitorio(resultado.error) and envio["tentativas"] + 1 < MAX_TENTATIVAS_TRANSITORIAS:
            _atualizar_envio(
                conn,
                envio["envio_id"],
                "pending",
                erro=resultado.error,
                last_error=resultado.error,
                incrementar_tentativas=True,
            )
            _registrar_contadores_campanha(conn, lote["campanha_id"], enviados, falhas)
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
            final_status, ndr_code, ndr_reason = _classificar_falha_final(resultado.error)
            _atualizar_envio(
                conn,
                envio["envio_id"],
                final_status,
                erro=resultado.error,
                last_error=resultado.error,
                ndr_code=ndr_code,
                ndr_reason=ndr_reason,
                incrementar_tentativas=True,
            )
            falhas += 1
            if final_status == "sender_blocked":
                _registrar_contadores_campanha(conn, lote["campanha_id"], enviados, falhas)
                _recolocar_lote_pendente(
                    conn,
                    lote["id"],
                    f"remetente bloqueado pelo provider: {ndr_code or 'AS(42004)'}",
                )
                raise SenderBlockedError(resultado.error or "sender blocked")

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
    _registrar_contadores_campanha(conn, lote["campanha_id"], enviados, falhas)

    logger.info(
        "Lote %s (campanha %s) concluido: %d enviados, %d falhas",
        lote["numero"],
        lote["campanha_id"],
        enviados,
        falhas,
    )
def _email_suprimido(conn: psycopg.Connection, email: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            select exists(
                select 1
                  from mei_email.email_suppressions s
                 where s.active
                   and (
                     (s.scope = 'email' and lower(btrim(s.value::text)) = lower(btrim(%s)))
                     or
                     (s.scope = 'domain' and lower(btrim(s.value::text)) = split_part(lower(btrim(%s)), '@', 2))
                   )
            )
            """,
            (email, email),
        )
        return bool(cur.fetchone()[0])


def _atualizar_envio(
    conn: psycopg.Connection,
    envio_id,
    status,
    provider_message_id=None,
    erro=None,
    *,
    graph_request_id=None,
    internet_message_id=None,
    ndr_code=None,
    ndr_reason=None,
    last_error=None,
    incrementar_tentativas=True,
):
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.envios
               set status = %s,
                   tentativas = tentativas + case when %s then 1 else 0 end,
                   provider_message_id = coalesce(%s, provider_message_id),
                   graph_request_id = coalesce(%s, graph_request_id),
                   internet_message_id = coalesce(%s, internet_message_id),
                   ndr_code = coalesce(%s, ndr_code),
                   ndr_reason = coalesce(%s, ndr_reason),
                   erro = %s,
                   last_error = %s,
                   submitted_at = case when %s = 'submitted' then coalesce(submitted_at, now()) else submitted_at end,
                   delivered_at = case when %s = 'delivered' then coalesce(delivered_at, now()) else delivered_at end,
                   bounced_at = case when %s in ('bounce_temporary', 'bounce_permanent') then coalesce(bounced_at, now()) else bounced_at end,
                   failed_at = case when %s in ('failed', 'cancelled', 'suppressed', 'sender_blocked') then coalesce(failed_at, now()) else failed_at end,
                   enviado_em = case when %s = 'submitted' then coalesce(enviado_em, now()) else enviado_em end
             where id = %s
            """,
            (
                status,
                incrementar_tentativas,
                provider_message_id,
                graph_request_id,
                internet_message_id,
                ndr_code,
                ndr_reason,
                erro,
                last_error if last_error is not None else erro,
                status,
                status,
                status,
                status,
                status,
                envio_id,
            ),
        )
        if status == "delivered":
            cur.execute(
                """
                update mei_email.empresas
                   set enviado = true,
                       enviado_em = coalesce(enviado_em, now())
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
                select l.id, l.campanha_id, l.numero
                  from mei_email.lotes l
                  join mei_email.campanhas c on c.id = l.campanha_id
                 where l.status = 'pendente'
                   and c.status in ('enfileirada', 'em_andamento')
                   and l.campanha_id = %s
                 order by l.criado_em, l.numero
                 for update skip locked
                 limit 1
                """,
                (campanha_id,),
            )
        else:
            cur.execute(
                """
                select l.id, l.campanha_id, l.numero
                  from mei_email.lotes l
                  join mei_email.campanhas c on c.id = l.campanha_id
                 where l.status = 'pendente'
                   and c.status in ('enfileirada', 'em_andamento')
                 order by l.criado_em, l.numero
                 for update skip locked
                 limit 1
                """
            )
        lote = cur.fetchone()
        if lote is None:
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
    if email_sends_paused():
        logger.warning("Envios pausados por controle operacional; worker nao sera iniciado.")
        return

    provider = get_email_provider(settings.email_provider)
    logger.info(
        "Worker iniciado. provedor=%s rate_limit=%d/min meta_24h=%d teto_24h=%d poll=%ds",
        settings.email_provider,
        settings.rate_limit_envios_por_minuto,
        settings.meta_envios_por_dia,
        settings.max_envios_por_dia,
        settings.worker_poll_interval_segundos,
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
                lote = pegar_proximo_lote(conn)
                if lote is None:
                    time.sleep(settings.worker_poll_interval_segundos)
                    continue
                processar_lote(conn, lote, provider)
            except SenderBlockedError as exc:
                logger.error("Remetente bloqueado pelo provider; pausando worker: %s", exc)
                pause_email_sends(str(exc))
                conn.rollback()
                raise SystemExit(2)
            except Exception:
                logger.exception("Erro processando lote -- worker continua rodando")
                conn.rollback()
                time.sleep(settings.worker_poll_interval_segundos)


if __name__ == "__main__":
    run()
