#!/usr/bin/env python3
"""Retention-aware entrypoint for the asynchronous NDR guard.

V025 intentionally purges recipient PII from successful ``envios`` rows and
keeps durable send evidence in ``email_suppressions`` plus, for reconciled
out-of-band messages, ``envios_externos_cota``. The base NDR guard therefore
needs to recognize all three audited prior-send stores before converting a
permanent recipient NDR into a hard-bounce suppression.
"""
from __future__ import annotations

import psycopg

from app.config import settings
from scripts import ndr_guard as guard

# Google can return 550 5.2.1 for an account that is explicitly inactive.
# This is a permanent recipient condition, not a sender restriction and not a
# transient mailbox-full response. Keep the marker phrase-specific instead of
# classifying every 5.2.1 response as permanent.
guard.PERMANENT_RECIPIENT_MARKERS = guard.PERMANENT_RECIPIENT_MARKERS + (
    "email account that you tried to reach is inactive",
)


def _retention_aware_prior_send_matches(
    addresses: list[str], *, sender_address: str
) -> list[str]:
    normalized = sorted(
        {
            value.casefold()
            for value in addresses
            if value.casefold() != sender_address.casefold()
        }
    )
    if not normalized:
        return []

    matches: set[str] = set()
    with psycopg.connect(settings.database_url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select distinct lower(btrim(email::text))
                  from mei_email.envios
                 where status::text in ('submitted','enviado','delivered','bounced')
                   and lower(btrim(email::text)) = any(%s::text[])
                """,
                (normalized,),
            )
            matches.update(str(row[0]).casefold() for row in cur.fetchall())

            cur.execute(
                "select to_regclass('mei_email.envios_externos_cota')"
            )
            if cur.fetchone()[0] is not None:
                cur.execute(
                    """
                    select distinct lower(btrim(email::text))
                      from mei_email.envios_externos_cota
                     where lower(btrim(email::text)) = any(%s::text[])
                    """,
                    (normalized,),
                )
                matches.update(str(row[0]).casefold() for row in cur.fetchall())

            cur.execute(
                """
                select distinct lower(btrim(value::text))
                  from mei_email.email_suppressions
                 where active
                   and scope = 'email'
                   and lower(btrim(value::text)) = any(%s::text[])
                   and (
                     reason = 'sent'
                     or source = 'worker_send_success'
                   )
                """,
                (normalized,),
            )
            matches.update(str(row[0]).casefold() for row in cur.fetchall())

    return sorted(matches)


guard._previously_sent_recipient_matches = _retention_aware_prior_send_matches


if __name__ == "__main__":
    raise SystemExit(guard.main())
