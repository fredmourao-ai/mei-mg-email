"""Deterministic recipient quality checks used before external dispatch.

Only obvious provider-domain typos observed in production are blocked. The
address is never rewritten, and legitimate provider/alternate domains are not
inferred from edit distance.
"""
from __future__ import annotations

OBVIOUS_PROVIDER_TYPO_DOMAINS: frozenset[str] = frozenset(
    {
        "ahoo.com.br", "gmai.com", "gamail.com", "gamil.com", "gmaial.com",
        "gmail.co2", "gmail.comma", "gmail.comm", "gmail.ocm", "gmail.om",
        "gmaill.com", "gmial.com", "gmil.com", "homail.com", "hootmail.com",
        "hotamail.com", "hotamil.com", "hotimail.com", "hotmai.com",
        "hotmail.com11", "hotmail.om", "hotmailc.om", "hotmal.com",
        "hotmial.com", "hotmil.com", "hottmail.com", "htmail.com",
        "jahoo.com.br", "otmail.com", "oultlook.com", "outlouk.com",
        "outook.com", "yaahoo.com.br", "yahho.com.br", "yahoo.bom.br",
        "yahoo.cm.br", "yahoo.combr", "yahoo.con.br", "yahoocom.br",
        "yahool.com.br", "yaoo.com.br", "yhaoo.com.br", "yhoo.com.br",
        "yashoo.com.br", "yshoo.com.br",
    }
)


def recipient_has_obvious_provider_typo(address: str) -> bool:
    """Return True only for a known obvious typo in a mailbox-provider domain."""
    if not isinstance(address, str) or address.count("@") != 1:
        return False
    domain = address.rsplit("@", 1)[1].strip().casefold().rstrip(".")
    return domain in OBVIOUS_PROVIDER_TYPO_DOMAINS
