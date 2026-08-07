#!/usr/bin/env python3
"""Valida DNS publico do dominio de envio Microsoft 365 via Cloudflare 1.1.1.1.

Nao altera DNS e nao exige credenciais Cloudflare. A consulta usa o endpoint
DoH publico da Cloudflare e valida SPF, MX, DKIM e DMARC para o subdominio de
envio. O status de Accepted Domain/DKIM Enabled dentro do tenant Microsoft
continua sendo uma verificacao separada no Exchange Admin Center.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DOH_ENDPOINT = "https://cloudflare-dns.com/dns-query"
EXPECTED_DOMAIN = os.getenv("MICROSOFT_SENDER_DOMAIN", "dev.shopvivaliz.com.br").strip().lower().rstrip(".")


def doh(name: str, record_type: str) -> dict:
    query = urlencode({"name": name, "type": record_type, "do": "true"})
    req = Request(
        f"{DOH_ENDPOINT}?{query}",
        headers={"Accept": "application/dns-json", "User-Agent": "mei-mg-email-domain-audit/1.0"},
    )
    with urlopen(req, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"Cloudflare DoH HTTP {response.status} para {name}/{record_type}")
        return json.loads(response.read().decode("utf-8"))


def answers(payload: dict, record_type: int) -> list[str]:
    return [
        str(item.get("data", "")).strip().strip('"')
        for item in payload.get("Answer", [])
        if int(item.get("type", 0)) == record_type
    ]


def main() -> int:
    domain = EXPECTED_DOMAIN
    checks = {
        "txt": doh(domain, "TXT"),
        "mx": doh(domain, "MX"),
        "dmarc": doh(f"_dmarc.{domain}", "TXT"),
        "dkim1": doh(f"selector1._domainkey.{domain}", "CNAME"),
        "dkim2": doh(f"selector2._domainkey.{domain}", "CNAME"),
        "autodiscover": doh(f"autodiscover.{domain}", "CNAME"),
    }

    txt = answers(checks["txt"], 16)
    mx = answers(checks["mx"], 15)
    dmarc = answers(checks["dmarc"], 16)
    dkim1 = answers(checks["dkim1"], 5)
    dkim2 = answers(checks["dkim2"], 5)
    autodiscover = answers(checks["autodiscover"], 5)

    errors: list[str] = []
    warnings: list[str] = []

    spf = [value for value in txt if value.lower().startswith("v=spf1")]
    if len(spf) != 1:
        errors.append(f"spf_record_count={len(spf)}")
    elif "include:spf.protection.outlook.com" not in spf[0].lower():
        errors.append("spf_missing_microsoft365_include")
    elif "-all" not in spf[0].lower():
        warnings.append("spf_without_hard_fail_minus_all")

    if not any("mail.protection.outlook.com" in value.lower() for value in mx):
        errors.append("mx_not_pointing_to_exchange_online")

    def valid_dkim(values: list[str]) -> bool:
        for value in values:
            low = value.lower().rstrip(".")
            if low.endswith(".dkim.mail.microsoft") or ".onmicrosoft.com" in low:
                return True
        return False

    if not valid_dkim(dkim1):
        errors.append("selector1_dkim_cname_missing_or_invalid")
    if not valid_dkim(dkim2):
        errors.append("selector2_dkim_cname_missing_or_invalid")

    dmarc_records = [value for value in dmarc if value.lower().startswith("v=dmarc1")]
    if len(dmarc_records) != 1:
        errors.append(f"dmarc_record_count={len(dmarc_records)}")
    else:
        low = dmarc_records[0].lower()
        if "p=none" in low:
            warnings.append("dmarc_policy_none_consider_quarantine_or_reject_after_monitoring")
        if "p=" not in low:
            errors.append("dmarc_policy_missing")

    if not any("autodiscover.outlook.com" in value.lower() for value in autodiscover):
        warnings.append("autodiscover_cname_not_found_or_not_microsoft")

    verification = [value for value in txt if value.lower().startswith("ms=ms")]
    if not verification:
        warnings.append("microsoft_domain_verification_txt_not_visible_optional_after_verification")

    print("MICROSOFT_DOMAIN_DNS_AUDIT")
    print(f"domain={domain}")
    print(f"spf={spf}")
    print(f"mx={mx}")
    print(f"dkim_selector1={dkim1}")
    print(f"dkim_selector2={dkim2}")
    print(f"dmarc={dmarc_records}")
    print(f"autodiscover={autodiscover}")
    print(f"microsoft_verification_txt_present={'yes' if verification else 'no'}")
    for warning in warnings:
        print(f"WARNING={warning}")

    if errors:
        print("NOT_READY_DNS_MICROSOFT_CUSTOM_DOMAIN")
        for error in errors:
            print(f"ERROR={error}")
        return 1

    print("READY_DNS_MICROSOFT_CUSTOM_DOMAIN")
    print("NOTE=DNS correto nao garante ausencia de throttling ou bloqueio antispam no Exchange Online.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("NOT_READY_DNS_MICROSOFT_CUSTOM_DOMAIN")
        print(f"ERROR=dns_audit_failed:{type(exc).__name__}:{exc}")
        raise SystemExit(1)
