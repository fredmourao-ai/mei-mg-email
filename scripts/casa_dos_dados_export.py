#!/usr/bin/env python3
"""Controle auditavel de exportacoes assicronas da Casa dos Dados.

Por padrao este programa apenas mostra a solicitacao que seria enviada. A
criacao de uma exportacao exige uma confirmacao literal porque pode consumir
saldo da conta e o provedor envia o arquivo ao destinatario informado.

O programa nunca cria campanha, habilita o worker ou importa contatos. O
arquivo baixado deve primeiro passar por inspecao de cabecalho e conciliacao de
consentimento antes de qualquer carga na base.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

CREATE_URL = "https://api.casadosdados.com.br/v5/cnpj/pesquisa/arquivo"
LIST_URL = "https://api.casadosdados.com.br/v4/cnpj/pesquisa/arquivo?pagina=1"
DETAIL_URL = "https://api.casadosdados.com.br/v4/public/cnpj/pesquisa/arquivo/{arquivo_uuid}"
TIMEOUT_SECONDS = 60
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}$")


def _require_api_key() -> str:
    api_key = os.getenv("CASA_DOS_DADOS_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("CASA_DOS_DADOS_API_KEY nao configurada")
    return api_key


def _request(url: str, *, method: str = "GET", payload: dict | None = None) -> dict | list:
    headers = {
        "api-key": _require_api_key(),
        "Accept": "application/json",
        "User-Agent": "ShopVivaliz-MEI-export-control/1.0",
    }
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Casa dos Dados HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Casa dos Dados indisponivel: {exc.reason}") from exc


def build_payload(scope: str, recipient: str, name: str) -> dict:
    recipient = recipient.strip().lower()
    if not EMAIL_RE.fullmatch(recipient):
        raise ValueError("destinatario da exportacao invalido")
    research: dict = {
        "situacao_cadastral": ["ATIVA"],
        "mei": {"optante": True},
        "mais_filtros": {
            "com_email": True,
            "excluir_email_contab": True,
        },
    }
    if scope == "mg":
        research["uf"] = ["mg"]
    elif scope != "nacional":
        raise ValueError("escopo invalido; use mg ou nacional")
    return {
        "total_linhas": 0,
        "nome": name,
        "tipo": "csv",
        "enviar_para": [recipient],
        "pesquisa": research,
    }


def sanitized_history(payload: dict | list) -> list[dict]:
    items = payload if isinstance(payload, list) else payload.get("arquivos", payload.get("data", []))
    if not isinstance(items, list):
        raise RuntimeError("resposta inesperada ao listar exportacoes")
    fields = (
        "arquivo_uuid",
        "nome",
        "tipo",
        "status",
        "quantidade",
        "quantidade_solicitada",
        "criado",
        "atualizado",
    )
    return [{field: item.get(field) for field in fields} for item in items if isinstance(item, dict)]


def download_export(arquivo_uuid: str, output: Path) -> None:
    if not UUID_RE.fullmatch(arquivo_uuid):
        raise ValueError("arquivo_uuid invalido")
    detail = _request(DETAIL_URL.format(arquivo_uuid=arquivo_uuid))
    if not isinstance(detail, dict) or not isinstance(detail.get("link"), str):
        raise RuntimeError("exportacao ainda nao disponibilizou link de download")
    download_url = detail["link"]
    if urlparse(download_url).scheme != "https":
        raise RuntimeError("provedor retornou link de download nao HTTPS")
    output.parent.mkdir(parents=True, exist_ok=True)
    request = Request(download_url, headers={"User-Agent": "ShopVivaliz-MEI-export-control/1.0"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response, output.open("wb") as target:
        while chunk := response.read(1024 * 1024):
            target.write(chunk)
    os.chmod(output, 0o600)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--preview", action="store_true", help="mostra o JSON sem chamar a API")
    action.add_argument("--submit", action="store_true", help="cria a exportacao apos confirmacao literal")
    action.add_argument("--list", action="store_true", help="lista exportacoes sem exibir destinatarios")
    action.add_argument("--download", metavar="ARQUIVO_UUID", help="baixa uma exportacao pronta")
    parser.add_argument("--scope", choices=("mg", "nacional"), default="mg")
    parser.add_argument("--recipient", help="caixa postal que recebera a exportacao")
    parser.add_argument("--name", default="mei-ativos-com-email")
    parser.add_argument("--confirm-paid-export", action="store_true")
    parser.add_argument("--output", type=Path, help="destino local para --download")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.preview or args.submit:
        if not args.recipient:
            raise SystemExit("--recipient e obrigatorio para preview ou submit")
        payload = build_payload(args.scope, args.recipient, args.name)
        if args.preview:
            print("CASA_EXPORT_PREVIEW=" + json.dumps(payload, ensure_ascii=True, sort_keys=True))
            return 0
        if not args.confirm_paid_export:
            raise SystemExit("recusado: --submit exige --confirm-paid-export")
        result = _request(CREATE_URL, method="POST", payload=payload)
        if not isinstance(result, dict) or not result.get("arquivo_uuid"):
            raise RuntimeError("Casa dos Dados nao retornou arquivo_uuid")
        print("CASA_EXPORT_SUBMITTED=" + json.dumps({
            "arquivo_uuid": result["arquivo_uuid"],
            "scope": args.scope,
            "name": args.name,
        }, ensure_ascii=True, sort_keys=True))
        return 0
    if args.list:
        print("CASA_EXPORT_HISTORY=" + json.dumps(sanitized_history(_request(LIST_URL)), ensure_ascii=True))
        return 0
    if not args.output:
        raise SystemExit("--output e obrigatorio com --download")
    download_export(args.download, args.output)
    print("CASA_EXPORT_DOWNLOADED=" + str(args.output.resolve()))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as exc:
        print(f"CASA_EXPORT_STATUS=failed error={type(exc).__name__}:{exc}", file=sys.stderr)
        raise SystemExit(1)
