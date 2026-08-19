"""Worker operacional que prioriza a fila existente antes de repor autoqueue.

Evita que uma consulta de reposicao lenta bloqueie milhares de envios ja
prontos. A reposicao ocorre em outra conexao, com timeout, somente depois de
recuperar estados legados e lotes orfaos. Enderecos com sintaxe invalida sao
suprimidos e removidos antes de qualquer chamada ao Graph.

Antes de chamar o Graph, cada envio e persistido como ``enviando``. Isso fecha
a janela de duplicidade em que o Graph podia aceitar a mensagem e o processo
morrer antes de gravar ``submitted``. A migration V034 trata uma recuperacao
de ``enviando`` marcada por este worker como entrega de resultado incerto e a
contabiliza conservadoramente como ``submitted``, em vez de reenviar.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.email_provider import get_email_provider
from app.queue_recovery import (
    recuperar_fila_legada_e_lotes_orfaos,
    repor_fila_automatica_isolada,
)
import worker.worker as base_worker
from worker.worker import (
    WORKER_ADVISORY_LOCK_ID,
    _sender_blocked_pause_ativo,
    logger,
    pegar_proximo_lote,
    recuperar_lotes_travados,
)

# One canonical circuit-breaker path is shared by the worker, monitor and
# hourly auto-repair service. Keep the legacy repository path read-only as a
# second safety signal during the transition.
SENDER_BLOCK_SENTINEL = Path(
    os.getenv(
        "SENDER_BLOCK_SENTINEL_PATH",
        "/var/lib/mei-mg-email/sender_blocked.pause",
    )
)
LEGACY_SENDER_BLOCK_SENTINEL = (
    Path(__file__).resolve().parents[1] / "runtime" / "sender_blocked.pause"
)
base_worker.SENDER_BLOCK_SENTINEL = SENDER_BLOCK_SENTINEL


def _sender_pause_ativo_em_qualquer_caminho() -> bool:
    return _sender_blocked_pause_ativo() or LEGACY_SENDER_BLOCK_SENTINEL.is_file()


def _tabela_cota_externa_existe(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute("select to_regclass('mei_email.envios_externos_cota')")
        return cur.fetchone()[0] is not None


def _obter_envios_ultimas_24h_indexado(conn: psycopg.Connection) -> int:
    """Count the rolling window using the partial index and external ledger."""
    with conn.cursor() as cur:
        cur.execute(
            """
            select count(*)
              from mei_email.envios
             where status in ('submitted', 'enviado')
               and enviado_em >= now() - interval '24 hours'
            """
        )
        total = int(cur.fetchone()[0] or 0)

        if _tabela_cota_externa_existe(conn):
            cur.execute(
                """
                select count(*)
                  from mei_email.envios_externos_cota
                 where sent_at >= now() - interval '24 hours'
                """
            )
            total += int(cur.fetchone()[0] or 0)
        return total


def _ja_submetido_ou_entregue_indexado(
    conn: psycopg.Connection, envio_id, email: str
) -> bool:
    """Consult compact suppression first and then indexed email history."""
    with conn.cursor() as cur:
        cur.execute(
            "select mei_email.is_email_suppressed(%s::citext)",
            (email,),
        )
        if bool(cur.fetchone()[0]):
            return True
        cur.execute(
            """
            select 1
              from mei_email.envios
             where id <> %s
               and status in ('submitted', 'enviado')
               and lower(btrim(email::text)) = lower(btrim(%s))
             limit 1
            """,
            (envio_id, email),
        )
        if cur.fetchone() is not None:
            return True

        if _tabela_cota_externa_existe(conn):
            cur.execute(
                """
                select 1
                  from mei_email.envios_externos_cota
                 where lower(btrim(email::text)) = lower(btrim(%s))
                 limit 1
                """,
                (email,),
            )
            if cur.fetchone() is not None:
                return True
        return False


# processar_lote is defined locally below. Replacing these module globals
# preserves all remaining safety checks while using indexed paths.
base_worker.obter_envios_ultimas_24h = _obter_envios_ultimas_24h_indexado
base_worker._ja_submetido_ou_entregue = _ja_submetido_ou_entregue_indexado


def _purgar_invalidos_do_lote(conn: psycopg.Connection, lote_id) -> int:
    """Suppress and remove invalid recipients before any Graph request."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select distinct e.cnpj, e.email
              from mei_email.envios e
             where e.lote_id = %s
               and e.status in ('pendente', 'pending')
               and not mei_email.is_valid_email_address(e.email)
             order by e.cnpj
            """,
            (lote_id,),
        )
        invalidos = cur.fetchall()

    for item in invalidos:
        with conn.cursor() as cur:
            cur.execute(
                """
                select mei_email.register_operational_suppression(
                    %s, %s, 'filter_email_invalid', 'worker_invalid_guard', null, now()
                )
                """,
                (item["cnpj"], item["email"]),
            )
            cur.execute(
                "delete from mei_email.envios where cnpj = %s",
                (item["cnpj"],),
            )
            cur.execute(
                "delete from mei_email.empresas where cnpj = %s",
                (item["cnpj"],),
            )
        conn.commit()

    if invalidos:
        logger.warning(
            "Lote %s: %d destinatarios invalidos removidos antes do Graph.",
            lote_id,
            len(invalidos),
        )
    return len(invalidos)


def _marcar_envio_em_transito(conn: psycopg.Connection, envio_id) -> None:
    """Persist a durable pre-send checkpoint before the external side effect.

    A Graph ``202`` and the database commit cannot be made atomic. Persisting
    ``enviando`` first turns a process crash into an explicit uncertain state,
    instead of leaving a ``pendente`` row that could be sent again blindly.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.envios
               set status = 'enviando',
                   erro = 'dispatch_started: aguardando resultado do Microsoft Graph'
             where id = %s
               and status = 'pendente'
            """,
            (envio_id,),
        )
        if cur.rowcount != 1:
            raise RuntimeError(
                f"envio {envio_id} deixou de estar pendente antes do checkpoint"
            )
    conn.commit()


def _empresa_para_template(envio: dict) -> dict:
    """Avoid an empty greeting without inventing company data."""
    render = dict(envio)
    nome = (render.get("nome_fantasia") or "").strip()
    razao = (render.get("razao_social") or "").strip()
    render["nome_fantasia"] = nome or razao or "empreendedor(a)"
    render["razao_social"] = razao or nome or "empreendedor(a)"
    return render


def processar_lote(conn: psycopg.Connection, lote: dict, provider) -> None:
    """Process a lot with a durable pre-send checkpoint and all base guards."""
    intervalo_entre_envios = 60.0 / max(settings.rate_limit_envios_por_minuto, 1)
    limite_24h = base_worker.limite_operacional_24h()

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select e.id as envio_id, e.cnpj, e.email, e.tentativas,
                   c.assunto, c.corpo_template,
                   emp.razao_social, emp.nome_fantasia,
                   emp.opt_out, emp.situacao_cadastral,
                   emp.provavel_terceiro, emp.marketing_autorizado
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
        envios_24h = _obter_envios_ultimas_24h_indexado(conn)
        if envios_24h >= limite_24h:
            base_worker._registrar_falhas_campanha(
                conn, lote["campanha_id"], falhas
            )
            base_worker._recolocar_lote_pendente(
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
            base_worker._atualizar_envio(
                conn,
                envio["envio_id"],
                "opt_out",
                erro="opt-out registrado apos enfileiramento",
            )
            continue

        if envio["situacao_cadastral"] != "ATIVA":
            base_worker._atualizar_envio(
                conn,
                envio["envio_id"],
                "bloqueado",
                erro="empresa deixou de estar ATIVA apos enfileiramento",
            )
            continue

        if envio["provavel_terceiro"]:
            base_worker._atualizar_envio(
                conn,
                envio["envio_id"],
                "bloqueado",
                erro="contato marcado como provavel terceiro apos enfileiramento",
            )
            continue

        if not envio["marketing_autorizado"]:
            base_worker._atualizar_envio(
                conn,
                envio["envio_id"],
                "bloqueado",
                erro="comunicacao comercial nao autorizada no cadastro",
            )
            continue

        if _ja_submetido_ou_entregue_indexado(
            conn, envio["envio_id"], envio["email"]
        ):
            base_worker._atualizar_envio(
                conn,
                envio["envio_id"],
                "descartado",
                erro="supressao global: destinatario ja submitted/enviado anteriormente",
            )
            continue

        corpo = base_worker.montar_corpo(
            envio["corpo_template"], _empresa_para_template(envio)
        )
        _marcar_envio_em_transito(conn, envio["envio_id"])
        resultado = provider.send(
            to=envio["email"], subject=envio["assunto"], body=corpo
        )

        if resultado.success:
            provider_status = getattr(resultado, "status", None)
            if provider_status != "submitted":
                raise RuntimeError(
                    f"status Graph inesperado apos sendMail: {provider_status!r}"
                )
            base_worker._atualizar_envio(
                conn,
                envio["envio_id"],
                "submitted",
                provider_message_id=resultado.message_id,
            )
            submetidos += 1
        elif getattr(resultado, "status", None) == "sender_blocked":
            base_worker._atualizar_envio(
                conn,
                envio["envio_id"],
                "sender_blocked",
                erro=resultado.error,
            )
            falhas += 1
            base_worker._registrar_falhas_campanha(
                conn, lote["campanha_id"], falhas
            )
            base_worker._recolocar_lote_pendente(
                conn,
                lote["id"],
                f"sender_blocked; circuito aberto: {resultado.error or 'sem detalhe'}",
            )
            base_worker._registrar_sender_blocked_pause(resultado.error)
            logger.critical(
                "SENDER_BLOCKED: circuito persistente aberto em %s. Nenhum novo envio sera tentado ate recuperacao verificada no Exchange.",
                base_worker.SENDER_BLOCK_SENTINEL,
            )
            return
        elif (
            base_worker._erro_transitorio(resultado.error)
            and envio["tentativas"] + 1 < base_worker.MAX_TENTATIVAS_TRANSITORIAS
        ):
            base_worker._atualizar_envio(
                conn, envio["envio_id"], "pendente", erro=resultado.error
            )
            base_worker._registrar_falhas_campanha(
                conn, lote["campanha_id"], falhas
            )
            base_worker._recolocar_lote_pendente(
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
            base_worker._atualizar_envio(
                conn, envio["envio_id"], "falhou", erro=resultado.error
            )
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
    base_worker._registrar_falhas_campanha(conn, lote["campanha_id"], falhas)

    logger.info(
        "Lote %s (campanha %s) concluido: %d submitted, %d falhas",
        lote["numero"],
        lote["campanha_id"],
        submetidos,
        falhas,
    )


def _processar_se_disponivel(conn: psycopg.Connection, provider) -> bool:
    lote = pegar_proximo_lote(conn)
    if lote is None:
        return False
    _purgar_invalidos_do_lote(conn, lote["id"])
    processar_lote(conn, lote, provider)
    return True


def run() -> None:
    if settings.max_envios_por_dia > 10000:
        raise RuntimeError("MAX_ENVIOS_POR_DIA nao pode ultrapassar 10000.")
    if settings.meta_envios_por_dia <= 0:
        raise RuntimeError("META_ENVIOS_POR_DIA precisa ser maior que zero.")
    if settings.meta_envios_por_dia > settings.max_envios_por_dia:
        raise RuntimeError("META_ENVIOS_POR_DIA nao pode ultrapassar o teto.")
    if settings.rate_limit_envios_por_minuto > 30:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO nao pode ultrapassar 30.")
    if settings.rate_limit_envios_por_minuto <= 0:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO precisa ser positivo.")
    if settings.queue_min_pending < 1:
        raise RuntimeError("QUEUE_MIN_PENDING precisa ser pelo menos 1.")
    if settings.queue_target_pending <= settings.queue_min_pending:
        raise RuntimeError("QUEUE_TARGET_PENDING precisa ser maior que o minimo.")

    provider = get_email_provider(settings.email_provider)
    logger.info(
        "Worker queue-first iniciado. provedor=%s rate_limit=%d/min "
        "meta_24h=%d teto_24h=%d poll=%ds fila_min=%d fila_target=%d",
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
                    "Ja existe outro worker de disparo ativo; instancia unica mantida."
                )

        recuperados = recuperar_lotes_travados(conn)
        recovery = recuperar_fila_legada_e_lotes_orfaos(conn)
        if recuperados or recovery.changed:
            logger.warning(
                "STARTUP_RECOVERY stuck_lots=%d queue_changes=%d",
                recuperados,
                recovery.changed,
            )

        while True:
            try:
                if _sender_pause_ativo_em_qualquer_caminho():
                    logger.critical(
                        "Worker pausado por sender_blocked. canonical=%s legacy=%s",
                        SENDER_BLOCK_SENTINEL,
                        LEGACY_SENDER_BLOCK_SENTINEL,
                    )
                    time.sleep(max(settings.worker_poll_interval_segundos, 60))
                    continue

                # Existing queue always wins. No replenishment query may run
                # while there is a recoverable lot.
                if _processar_se_disponivel(conn, provider):
                    continue

                recovery = recuperar_fila_legada_e_lotes_orfaos(conn)
                if recovery.changed and _processar_se_disponivel(conn, provider):
                    continue

                adicionados = repor_fila_automatica_isolada()
                if adicionados:
                    logger.warning(
                        "AUTOQUEUE_ISOLATED added=%d; retomando consumo.",
                        adicionados,
                    )

                if not _processar_se_disponivel(conn, provider):
                    time.sleep(settings.worker_poll_interval_segundos)
            except Exception:
                logger.exception("Erro no ciclo do worker; conexao sera recuperada")
                conn.rollback()
                time.sleep(settings.worker_poll_interval_segundos)


if __name__ == "__main__":
    run()
