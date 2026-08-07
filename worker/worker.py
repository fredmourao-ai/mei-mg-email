"""
Worker que consome a fila de lotes e dispara os e-mails respeitando limites.

Para Exchange Online, o controle diario usa uma janela movel de 24 horas,
assim como o limite de taxa de destinatarios do servico. Uma trava advisory no
Postgres garante apenas um worker ativo por vez, evitando que multiplos
processos somem suas taxas e ultrapassem o limite por minuto.
"""
from __future__ import annotations

import logging
import time
from urllib.parse import urlencode

import psycopg
from psycopg.rows import dict_row

from app.config import settings
from app.email_provider import get_email_provider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mei_mg_email.worker")
WORKER_ADVISORY_LOCK_ID = 100002026


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
             where status = 'enviado'
               and enviado_em >= now() - interval '24 hours'
            """
        )
        return cur.fetchone()[0]


def processar_lote(conn: psycopg.Connection, lote: dict, provider) -> None:
    intervalo_entre_envios = 60.0 / max(settings.rate_limit_envios_por_minuto, 1)

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            select e.id as envio_id, e.cnpj, e.email,
                   c.assunto, c.corpo_template,
                   emp.razao_social, emp.nome_fantasia,
                   emp.opt_out
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

    enviados = 0
    falhas = 0

    for envio in envios:
        envios_24h = obter_envios_ultimas_24h(conn)
        if envios_24h >= settings.max_envios_por_dia:
            logger.warning(
                "Limite movel de 24h atingido: %d/%d. Pausando novos envios.",
                envios_24h,
                settings.max_envios_por_dia,
            )
            return

        if envio["opt_out"]:
            _atualizar_envio(
                conn,
                envio["envio_id"],
                "opt_out",
                erro="opt-out registrado apos enfileiramento",
            )
            continue

        corpo = montar_corpo(envio["corpo_template"], envio)
        resultado = provider.send(to=envio["email"], subject=envio["assunto"], body=corpo)

        if resultado.success:
            _atualizar_envio(
                conn,
                envio["envio_id"],
                "enviado",
                provider_message_id=resultado.message_id,
            )
            enviados += 1
        else:
            _atualizar_envio(conn, envio["envio_id"], "falhou", erro=resultado.error)
            falhas += 1

        time.sleep(intervalo_entre_envios)

    with conn.cursor() as cur:
        cur.execute(
            """
            update mei_email.lotes
               set status = 'concluido', concluido_em = now()
             where id = %s
            """,
            (lote["id"],),
        )
        cur.execute(
            """
            update mei_email.campanhas
               set total_enviados = total_enviados + %s,
                   total_falhas = total_falhas + %s
             where id = %s
            """,
            (enviados, falhas, lote["campanha_id"]),
        )
    conn.commit()

    logger.info(
        "Lote %s (campanha %s) concluido: %d enviados, %d falhas",
        lote["numero"],
        lote["campanha_id"],
        enviados,
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
                   enviado_em = case when %s = 'enviado' then now() else enviado_em end
             where id = %s
            """,
            (status, provider_message_id, erro, status, envio_id),
        )
        if status == "enviado":
            cur.execute(
                """
                update mei_email.empresas
                   set enviado = true,
                       enviado_em = now()
                 where email = (select email from mei_email.envios where id = %s)
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
            return None

        cur.execute(
            """
            update mei_email.lotes
               set status = 'processando',
                   iniciado_em = now(),
                   tentativas = tentativas + 1
             where id = %s
            """,
            (lote["id"],),
        )
    conn.commit()
    return lote


def run() -> None:
    if settings.max_envios_por_dia > 10000:
        raise RuntimeError("MAX_ENVIOS_POR_DIA nao pode ultrapassar 10000 para Exchange Online.")
    if settings.rate_limit_envios_por_minuto > 30:
        raise RuntimeError("RATE_LIMIT_ENVIOS_POR_MINUTO nao pode ultrapassar 30 no Exchange Online.")

    provider = get_email_provider(settings.email_provider)
    logger.info(
        "Worker iniciado. provedor=%s rate_limit=%d/min limite_24h=%d poll=%ds",
        settings.email_provider,
        settings.rate_limit_envios_por_minuto,
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

        while True:
            try:
                lote = pegar_proximo_lote(conn)
                if lote is None:
                    time.sleep(settings.worker_poll_interval_segundos)
                    continue
                processar_lote(conn, lote, provider)
            except Exception:
                logger.exception("Erro processando lote -- worker continua rodando")
                conn.rollback()
                time.sleep(settings.worker_poll_interval_segundos)


if __name__ == "__main__":
    run()
