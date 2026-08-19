#!/usr/bin/env python3
"""Descoberta incremental diaria de novos CNPJs de MG via Casa dos Dados v5.

A rotina consulta apenas empresas ATIVAS, em MG, indicadas pela fonte como
optantes MEI e com e-mail, usando uma janela sobreposta de dias para tolerar
atrasos de publicacao.

Uma base publica de CNPJ comprova apenas a existencia do cadastro e do contato;
ela nao comprova opt-in para comunicacao comercial. Por isso novas linhas desta
fonte entram com ``marketing_autorizado=false``. Um UPSERT tambem nunca eleva
essa flag: eventual autorizacao comercial existente e preservada, mas precisa
ter sido obtida por um fluxo independente e auditavel. O opt_out permanece
soberano e os campos enviado/enviado_em nao sao sobrescritos.

Esta rotina NAO cria campanhas e NAO inicia o worker de e-mail.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import psycopg
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

API_URL = os.getenv(
    "CASA_DOS_DADOS_API_URL",
    "https://api.casadosdados.com.br/v5/cnpj/pesquisa",
).strip()
API_KEY = os.getenv("CASA_DOS_DADOS_API_KEY", "").strip()
LOOKBACK_DAYS = max(int(os.getenv("CNPJ_DAILY_LOOKBACK_DAYS", "3")), 1)
PAGE_SIZE = min(max(int(os.getenv("CASA_DOS_DADOS_PAGE_SIZE", "100")), 1), 1000)
MAX_PAGES = max(int(os.getenv("CASA_DOS_DADOS_MAX_PAGES", "500")), 1)
TIMEOUT_SECONDS = max(int(os.getenv("CASA_DOS_DADOS_TIMEOUT_SECONDS", "45")), 5)
TZ = ZoneInfo(os.getenv("CNPJ_DAILY_TIMEZONE", "America/Sao_Paulo"))
CNPJ_RE = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PUBLIC_BASE_ORIGIN = "base_publica_sem_opt_in"


def normalize_cnpj(value: object) -> str | None:
    text = re.sub(r"[^0-9A-Za-z]", "", str(value or "")).upper()
    return text if CNPJ_RE.fullmatch(text) else None


def clean_text(value: object, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text[:max_len] if max_len else text


def build_search_payload(
    today: date,
    *,
    lookback_days: int = LOOKBACK_DAYS,
    page: int = 1,
    limit: int = PAGE_SIZE,
) -> dict:
    start = today - timedelta(days=max(lookback_days, 1) - 1)
    return {
        "situacao_cadastral": ["ATIVA"],
        "uf": ["mg"],
        "data_abertura": {"inicio": start.isoformat(), "fim": today.isoformat()},
        "mei": {"optante": True},
        "mais_filtros": {
            "com_email": True,
            "excluir_email_contab": True,
        },
        "limite": limit,
        "pagina": page,
    }


def _collect_email_values(node: object, *, parent_key: str = "", depth: int = 0) -> list[str]:
    if depth > 5 or node is None:
        return []
    found: list[str] = []
    if isinstance(node, str):
        value = node.strip().lower()
        if "email" in parent_key.casefold() and "contab" not in parent_key.casefold() and EMAIL_RE.fullmatch(value):
            found.append(value)
        return found
    if isinstance(node, list):
        for item in node:
            found.extend(_collect_email_values(item, parent_key=parent_key, depth=depth + 1))
        return found
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend(_collect_email_values(value, parent_key=str(key), depth=depth + 1))
    return found


def extract_email(item: dict) -> str | None:
    candidates = _collect_email_values(item)
    seen: set[str] = set()
    for value in candidates:
        if value not in seen:
            seen.add(value)
            return value
    return None


def _first_phone(node: object, *, depth: int = 0) -> tuple[str | None, str | None]:
    if depth > 4 or node is None:
        return None, None
    if isinstance(node, dict):
        ddd = clean_text(node.get("ddd"), 3)
        number = clean_text(node.get("telefone") or node.get("numero"), 15)
        if number and re.sub(r"\D", "", number):
            return ddd, number
        for key, value in node.items():
            if "telefone" in str(key).casefold() or "contato" in str(key).casefold():
                result = _first_phone(value, depth=depth + 1)
                if result[1]:
                    return result
    elif isinstance(node, list):
        for value in node:
            result = _first_phone(value, depth=depth + 1)
            if result[1]:
                return result
    elif isinstance(node, str) and re.fullmatch(r"[+()0-9 .-]{8,20}", node.strip()):
        return None, clean_text(node, 15)
    return None, None


def normalize_company(item: dict) -> dict | None:
    cnpj = normalize_cnpj(item.get("cnpj"))
    if not cnpj:
        return None
    situacao_raw = item.get("situacao_cadastral")
    if isinstance(situacao_raw, dict):
        situacao = clean_text(situacao_raw.get("situacao_cadastral") or situacao_raw.get("descricao"))
    else:
        situacao = clean_text(situacao_raw)
    endereco = item.get("endereco") if isinstance(item.get("endereco"), dict) else {}
    uf = clean_text(endereco.get("uf") or item.get("uf"), 2)
    email = extract_email(item)
    ddd, telefone = _first_phone(item)
    return {
        "cnpj": cnpj,
        "razao_social": clean_text(item.get("razao_social")),
        "nome_fantasia": clean_text(item.get("nome_fantasia")),
        "situacao_cadastral": (situacao or "ATIVA").upper(),
        "uf": (uf or "MG").upper(),
        "email": email,
        "ddd_1": ddd,
        "telefone_1": telefone,
        "data_abertura": clean_text(item.get("data_abertura"), 10),
        "tipo_regime": "MEI_CANDIDATO",
        "provavel_terceiro": False,
    }


def request_page(payload: dict) -> dict:
    if not API_KEY:
        raise RuntimeError("CASA_DOS_DADOS_API_KEY nao configurada")
    req = Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "api-key": API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ShopVivaliz-MEI-daily-discovery/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        raise RuntimeError(f"Casa dos Dados HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Casa dos Dados indisponivel: {exc.reason}") from exc


def upsert_companies(conn, companies: list[dict]) -> tuple[int, int]:
    if not companies:
        return 0, 0
    cnpjs = [row["cnpj"] for row in companies]
    with conn.cursor() as cur:
        cur.execute("select cnpj::text from mei_email.empresas where cnpj::text = any(%s)", (cnpjs,))
        existing = {str(row[0]).strip() for row in cur.fetchall()}
        cur.executemany(
            """
            insert into mei_email.empresas
                (cnpj, razao_social, nome_fantasia, situacao_cadastral,
                 uf, email, ddd_1, telefone_1, data_abertura,
                 tipo_regime, provavel_terceiro,
                 marketing_autorizado, marketing_autorizado_em, marketing_autorizado_origem,
                 mei_verificado, mei_verificado_em, mei_verificado_origem)
            values
                (%(cnpj)s, %(razao_social)s, %(nome_fantasia)s, %(situacao_cadastral)s,
                 %(uf)s, %(email)s, %(ddd_1)s, %(telefone_1)s, %(data_abertura)s,
                 %(tipo_regime)s, %(provavel_terceiro)s,
                 false, null, 'base_publica_sem_opt_in',
                 true, now(), 'casa_dos_dados_mei_verificado')
            on conflict (cnpj) do update set
                razao_social = coalesce(excluded.razao_social, mei_email.empresas.razao_social),
                nome_fantasia = coalesce(excluded.nome_fantasia, mei_email.empresas.nome_fantasia),
                situacao_cadastral = excluded.situacao_cadastral,
                uf = excluded.uf,
                data_abertura = coalesce(excluded.data_abertura, mei_email.empresas.data_abertura),
                email = case
                    when mei_email.empresas.email is null or btrim(mei_email.empresas.email::text) = ''
                    then excluded.email else mei_email.empresas.email
                end,
                ddd_1 = coalesce(mei_email.empresas.ddd_1, excluded.ddd_1),
                telefone_1 = coalesce(mei_email.empresas.telefone_1, excluded.telefone_1),
                tipo_regime = case
                    when mei_email.empresas.tipo_regime = 'MEI' then 'MEI'
                    else excluded.tipo_regime
                end,
                marketing_autorizado = mei_email.empresas.marketing_autorizado,
                marketing_autorizado_em = mei_email.empresas.marketing_autorizado_em,
                marketing_autorizado_origem = mei_email.empresas.marketing_autorizado_origem,
                mei_verificado = true,
                mei_verificado_em = coalesce(mei_email.empresas.mei_verificado_em, now()),
                mei_verificado_origem = coalesce(mei_email.empresas.mei_verificado_origem, 'casa_dos_dados_mei_verificado')
            """,
            companies,
        )
    conn.commit()
    inserted = sum(1 for cnpj in cnpjs if cnpj not in existing)
    return inserted, len(companies) - inserted


def mark_shared_emails(conn) -> int:
    with conn.cursor() as cur:
        cur.execute(
            """
            with emails_terceiros as (
                select lower(btrim(email::text)) as email_normalizado
                  from mei_email.empresas
                 where email is not null and btrim(email::text) <> ''
                 group by lower(btrim(email::text))
                having count(*) > 3
            )
            update mei_email.empresas e
               set provavel_terceiro = true
             where e.provavel_terceiro = false
               and lower(btrim(e.email::text)) in (
                   select email_normalizado from emails_terceiros
               )
            """
        )
        changed = max(cur.rowcount, 0)
    conn.commit()
    return changed


def main() -> int:
    if not API_KEY:
        print("CASA_DOS_DADOS_STATUS=unconfigured", flush=True)
        print("MISSING_SECRET=CASA_DOS_DADOS_API_KEY", flush=True)
        return 3

    today = datetime.now(TZ).date()
    start = today - timedelta(days=LOOKBACK_DAYS - 1)
    stats = {
        "source": "casa_dos_dados_v5",
        "window_start": start.isoformat(),
        "window_end": today.isoformat(),
        "pages": 0,
        "api_total": None,
        "received": 0,
        "valid": 0,
        "with_email_in_response": 0,
        "inserted": 0,
        "updated": 0,
        "invalid": 0,
        "shared_email_marks": 0,
        "marketing_policy": PUBLIC_BASE_ORIGIN,
    }

    database_url = os.environ["DATABASE_URL"]
    with psycopg.connect(database_url) as conn:
        for page in range(1, MAX_PAGES + 1):
            payload = build_search_payload(today, page=page, limit=PAGE_SIZE)
            response = request_page(payload)
            if stats["api_total"] is None:
                raw_total = response.get("total")
                stats["api_total"] = int(raw_total) if raw_total is not None else None
            items = response.get("cnpjs") or response.get("resultados") or []
            if not isinstance(items, list):
                raise RuntimeError("Resposta da Casa dos Dados sem lista cnpjs/resultados")
            stats["pages"] += 1
            stats["received"] += len(items)

            normalized: list[dict] = []
            for item in items:
                if not isinstance(item, dict):
                    stats["invalid"] += 1
                    continue
                company = normalize_company(item)
                if company is None:
                    stats["invalid"] += 1
                    continue
                if company["uf"] != "MG" or company["situacao_cadastral"] != "ATIVA":
                    stats["invalid"] += 1
                    continue
                if company["email"]:
                    stats["with_email_in_response"] += 1
                normalized.append(company)

            inserted, updated = upsert_companies(conn, normalized)
            stats["inserted"] += inserted
            stats["updated"] += updated
            stats["valid"] += len(normalized)

            if not items or len(items) < PAGE_SIZE:
                break
            if stats["api_total"] is not None and stats["received"] >= stats["api_total"]:
                break
        else:
            raise RuntimeError(f"Paginacao excedeu CASA_DOS_DADOS_MAX_PAGES={MAX_PAGES}")

        stats["shared_email_marks"] = mark_shared_emails(conn)

    print("CASA_DOS_DADOS_STATUS=success", flush=True)
    print("CASA_DOS_DADOS_RESULT=" + json.dumps(stats, ensure_ascii=False, sort_keys=True), flush=True)
    print(
        "POLICY=base_publica_nao_concede_opt_in;mei_verificado_true;opt_out_preservado;autorizacao_existente_preservada;worker_nao_iniciado",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
