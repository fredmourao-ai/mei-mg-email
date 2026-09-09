#!/usr/bin/env python3
"""Official Receita Federal CNPJ snapshot discovery and disk-safe import.

The stable Receita host redirects to a rotating public Nextcloud share token.
This module resolves that redirect at runtime, validates the complete monthly
Estabelecimentos manifest and streams one ZIP at a time without extracting the
uncompressed CSV to disk. It never creates campaigns or starts the email worker.
"""
from __future__ import annotations

import base64
import csv
import io
import os
import re
import shutil
import time
import urllib.parse
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_SHARE_URL = os.getenv(
    "RECEITA_WEBDAV_SHARE_URL",
    "https://arquivos.receitafederal.gov.br/",
).strip()
DEFAULT_DIRECTORY = os.getenv(
    "RECEITA_WEBDAV_DIRECTORY",
    "Dados/Cadastros/CNPJ",
).strip("/")
DEFAULT_CACHE_DIR = Path(
    os.getenv("RECEITA_WEBDAV_CACHE_DIR", "/var/lib/mei-mg-email/receita-cache")
)
DEFAULT_TIMEOUT_SECONDS = max(int(os.getenv("RECEITA_WEBDAV_TIMEOUT_SECONDS", "120")), 10)
DEFAULT_DISK_RESERVE_BYTES = max(
    int(os.getenv("RECEITA_WEBDAV_DISK_RESERVE_BYTES", str(2 * 1024**3))),
    256 * 1024**2,
)
DEFAULT_BATCH_SIZE = max(int(os.getenv("RECEITA_WEBDAV_BATCH_SIZE", "1000")), 100)
DEFAULT_DOWNLOAD_ATTEMPTS = max(int(os.getenv("RECEITA_WEBDAV_DOWNLOAD_ATTEMPTS", "4")), 1)
DEFAULT_RETRY_DELAY_SECONDS = max(float(os.getenv("RECEITA_WEBDAV_RETRY_DELAY_SECONDS", "5")), 0.0)
USER_AGENT = "ShopVivaliz-MEI-receita-webdav/1.0"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
COMPETENCE_RE = re.compile(r"^\d{4}-\d{2}$")
EXPECTED_ARCHIVES = tuple(f"Estabelecimentos{i}.zip" for i in range(10))
DAV = "{DAV:}"
RECEITA_ALLOWED_HOST = "arquivos.receitafederal.gov.br"


@dataclass(frozen=True)
class DavEntry:
    name: str
    href: str
    size: int
    is_dir: bool


@dataclass(frozen=True)
class RemoteZip:
    name: str
    url: str
    size: int


@dataclass(frozen=True)
class SnapshotManifest:
    competence: str
    files: tuple[RemoteZip, ...]
    token: str = ""
    source_url: str = ""


@dataclass
class ImportStats:
    files_processed: int = 0
    rows_read: int = 0
    eligible: int = 0
    upserted: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def _validate_receita_url(url: str) -> urllib.parse.ParseResult:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.casefold() != "https":
        raise RuntimeError("Receita URL deve usar HTTPS")
    if (parsed.hostname or "").casefold() != RECEITA_ALLOWED_HOST:
        raise RuntimeError("Receita URL deve permanecer no host oficial")
    if parsed.username or parsed.password or parsed.port not in (None, 443):
        raise RuntimeError("Receita URL contem autoridade/porta nao permitida")
    return parsed


def resolve_share_url(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Resolve the stable Receita host to the currently active public share."""
    parsed = _validate_receita_url(url)
    if "/s/" in parsed.path:
        return url
    req = Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            final_url = response.geturl()
    except HTTPError as exc:
        raise RuntimeError(f"Receita HTTP {exc.code} ao resolver share publico") from exc
    except URLError as exc:
        raise RuntimeError(f"Receita indisponivel ao resolver share: {exc.reason}") from exc
    final_parsed = _validate_receita_url(final_url)
    if "/s/" not in final_parsed.path:
        raise RuntimeError("Receita nao redirecionou para um share publico /s/")
    return final_url


def parse_share_url(
    url: str,
    *,
    default_directory: str = DEFAULT_DIRECTORY,
) -> tuple[str, str, str]:
    parsed = _validate_receita_url(url)
    marker = "/s/"
    if marker not in parsed.path:
        raise RuntimeError("URL publica da Receita sem token /s/")
    token = parsed.path.split(marker, 1)[1].split("/", 1)[0].strip()
    if not token:
        raise RuntimeError("URL publica da Receita sem token")
    query = urllib.parse.parse_qs(parsed.query)
    directory = query.get("dir", [default_directory])[0].strip("/")
    webdav = f"{parsed.scheme}://{parsed.netloc}/public.php/webdav"
    return token, directory, webdav


def _basic_auth(token: str) -> str:
    raw = f"{token}:".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _propfind(url: str, token: str, timeout_seconds: int) -> bytes:
    body = b"""<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:"><d:prop><d:displayname/><d:resourcetype/><d:getcontentlength/></d:prop></d:propfind>"""
    req = Request(
        url.rstrip("/") + "/",
        data=body,
        headers={
            "Authorization": _basic_auth(token),
            "Depth": "1",
            "Content-Type": "application/xml; charset=utf-8",
            "User-Agent": USER_AGENT,
        },
        method="PROPFIND",
    )
    try:
        with urlopen(req, timeout=timeout_seconds) as response:
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"Receita WebDAV HTTP {exc.code} em PROPFIND") from exc
    except URLError as exc:
        raise RuntimeError(f"Receita WebDAV indisponivel: {exc.reason}") from exc


def parse_propfind_entries(payload: bytes) -> list[DavEntry]:
    try:
        root = ET.fromstring(payload, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    except (ET.ParseError, DefusedXmlException) as exc:
        raise RuntimeError("Receita WebDAV retornou XML inseguro ou invalido") from exc
    entries: list[DavEntry] = []
    for response in root.findall(f"{DAV}response"):
        href_el = response.find(f"{DAV}href")
        prop = response.find(f"{DAV}propstat/{DAV}prop")
        if href_el is None or not href_el.text or prop is None:
            continue
        href = urllib.parse.unquote(href_el.text)
        display = prop.find(f"{DAV}displayname")
        name = (
            display.text
            if display is not None and display.text
            else href.rstrip("/").split("/")[-1]
        ).strip()
        if not name:
            continue
        resourcetype = prop.find(f"{DAV}resourcetype")
        is_dir = bool(
            resourcetype is not None
            and resourcetype.find(f"{DAV}collection") is not None
        )
        size_el = prop.find(f"{DAV}getcontentlength")
        try:
            size = int(size_el.text or 0) if size_el is not None else 0
        except (TypeError, ValueError):
            size = 0
        entries.append(DavEntry(name=name, href=href, size=size, is_dir=is_dir))
    return entries


def list_webdav_entries(
    url: str,
    token: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[DavEntry]:
    return parse_propfind_entries(_propfind(url, token, timeout_seconds))


def select_latest_competence(entries: list[DavEntry]) -> str:
    folders = sorted(
        {e.name for e in entries if e.is_dir and COMPETENCE_RE.fullmatch(e.name)}
    )
    if not folders:
        raise RuntimeError("Receita WebDAV sem pasta YYYY-MM")
    return folders[-1]


def build_manifest(
    competence: str,
    entries: list[DavEntry],
    folder_url: str,
    *,
    token: str = "",
    source_url: str = "",
) -> SnapshotManifest:
    by_name: dict[str, list[DavEntry]] = {}
    for entry in entries:
        by_name.setdefault(entry.name, []).append(entry)
    files: list[RemoteZip] = []
    for expected in EXPECTED_ARCHIVES:
        matches = by_name.get(expected, [])
        if len(matches) != 1:
            raise RuntimeError(
                f"Manifesto Receita invalido: esperado exatamente um {expected}"
            )
        entry = matches[0]
        if entry.is_dir or entry.size <= 0:
            raise RuntimeError(
                f"Manifesto Receita invalido: {expected} sem tamanho valido"
            )
        remote_url = folder_url.rstrip("/") + "/" + urllib.parse.quote(expected)
        files.append(RemoteZip(name=expected, url=remote_url, size=entry.size))
    return SnapshotManifest(
        competence=competence,
        files=tuple(files),
        token=token,
        source_url=source_url or folder_url,
    )


def discover_latest_snapshot(
    share_url: str = DEFAULT_SHARE_URL,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> SnapshotManifest:
    resolved_share_url = resolve_share_url(share_url, timeout_seconds)
    token, directory, webdav = parse_share_url(resolved_share_url)
    root_url = webdav.rstrip("/")
    if directory:
        root_url += "/" + "/".join(
            urllib.parse.quote(part) for part in directory.split("/") if part
        )
    root_entries = list_webdav_entries(root_url, token, timeout_seconds)
    competence = select_latest_competence(root_entries)
    folder_url = root_url.rstrip("/") + "/" + urllib.parse.quote(competence)
    entries = list_webdav_entries(folder_url, token, timeout_seconds)
    return build_manifest(
        competence,
        entries,
        folder_url,
        token=token,
        source_url=share_url,
    )


def ensure_disk_headroom(
    path: Path,
    *,
    remote_size: int,
    reserve_bytes: int = DEFAULT_DISK_RESERVE_BYTES,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(path).free
    required = int(remote_size) + int(reserve_bytes)
    if free < required:
        raise RuntimeError(
            f"espaco insuficiente para ZIP Receita: livre={free} necessario={required}"
        )


def _range_is_valid(response, start: int, expected_size: int) -> bool:
    if start <= 0:
        return True
    status = int(getattr(response, "status", 0) or 0)
    content_range = str(response.headers.get("Content-Range") or "")
    expected_prefix = f"bytes {start}-"
    expected_suffix = f"/{expected_size}"
    return status == 206 and content_range.startswith(expected_prefix) and content_range.endswith(expected_suffix)


def _retryable_http(code: int) -> bool:
    return code in {408, 416, 429} or 500 <= code <= 599


def download_remote_zip(
    remote: RemoteZip,
    *,
    token: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    reserve_bytes: int = DEFAULT_DISK_RESERVE_BYTES,
    attempts: int = DEFAULT_DOWNLOAD_ATTEMPTS,
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
) -> Path:
    """Download one ZIP with bounded retry and safe HTTP Range resume."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    final = cache_dir / remote.name
    part = cache_dir / f"{remote.name}.part"
    attempts = max(int(attempts), 1)

    if final.exists():
        if final.stat().st_size == remote.size:
            return final
        final.unlink(missing_ok=True)
    if part.exists() and part.stat().st_size > remote.size:
        part.unlink(missing_ok=True)
    if part.exists() and part.stat().st_size == remote.size:
        part.replace(final)
        return final

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        start = part.stat().st_size if part.exists() else 0
        remaining = max(remote.size - start, 0)
        ensure_disk_headroom(
            cache_dir,
            remote_size=remaining,
            reserve_bytes=reserve_bytes,
        )
        headers = {
            "Authorization": _basic_auth(token),
            "User-Agent": USER_AGENT,
        }
        if start:
            headers["Range"] = f"bytes={start}-"
        req = Request(remote.url, headers=headers, method="GET")
        try:
            with urlopen(req, timeout=timeout_seconds) as response:
                if start and not _range_is_valid(response, start, remote.size):
                    part.unlink(missing_ok=True)
                    raise RuntimeError(
                        f"Receita WebDAV nao confirmou retomada segura de {remote.name}"
                    )
                mode = "ab" if start else "wb"
                with part.open(mode) as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)

            total = part.stat().st_size if part.exists() else 0
            if total == remote.size:
                part.replace(final)
                return final
            if total > remote.size:
                part.unlink(missing_ok=True)
                raise RuntimeError(
                    f"ZIP Receita excedeu tamanho esperado {remote.name}: recebido={total} esperado={remote.size}"
                )
            last_error = RuntimeError(
                f"ZIP Receita incompleto {remote.name}: recebido={total} esperado={remote.size}"
            )
        except HTTPError as exc:
            if not _retryable_http(exc.code):
                raise RuntimeError(
                    f"Receita WebDAV HTTP {exc.code} ao baixar {remote.name}"
                ) from exc
            if exc.code == 416:
                part.unlink(missing_ok=True)
            last_error = exc
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
        except RuntimeError as exc:
            last_error = exc

        if attempt < attempts and retry_delay_seconds:
            time.sleep(retry_delay_seconds)

    total = part.stat().st_size if part.exists() else 0
    raise RuntimeError(
        f"falha ao baixar {remote.name} apos {attempts} tentativas; bytes_preservados={total}"
    ) from last_error


def _clean(value: object, max_len: int | None = None) -> str | None:
    text = str(value or "").strip().strip('"')
    if not text:
        return None
    return text[:max_len] if max_len else text


def _parse_date(value: str | None) -> str | None:
    text = (value or "").strip()
    if len(text) != 8 or text == "00000000" or not text.isdigit():
        return None
    return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"


def parse_establishment_row(row: list[str]) -> dict | None:
    if len(row) < 28:
        return None
    values = [str(value or "").strip().strip('"') for value in row]
    if values[5] != "02":
        return None
    email = values[27].strip().lower()
    if not EMAIL_RE.fullmatch(email) or "contabil" in email:
        return None
    basic = values[0].upper().zfill(8)
    order = values[1].upper().zfill(4)
    dv = values[2].upper().zfill(2)
    cnpj = f"{basic}{order}{dv}"
    if not re.fullmatch(r"[0-9A-Z]{12}[0-9]{2}", cnpj):
        return None
    uf = values[19].upper()
    if not re.fullmatch(r"[A-Z]{2}", uf):
        return None
    fantasia = _clean(values[4])
    return {
        "cnpj": cnpj,
        "razao_social": fantasia,
        "nome_fantasia": fantasia,
        "situacao_cadastral": "ATIVA",
        "uf": uf,
        "email": email,
        "ddd_1": _clean(values[21], 3),
        "telefone_1": _clean(values[22], 15),
        "data_abertura": _parse_date(values[10]),
    }


def build_upsert_sql(
    values_clause: str = "(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
) -> str:
    return f"""
        insert into mei_email.empresas
            (cnpj, razao_social, nome_fantasia, situacao_cadastral,
             uf, email, ddd_1, telefone_1, data_abertura)
        values {values_clause}
        on conflict (cnpj) do update set
            razao_social = coalesce(mei_email.empresas.razao_social, excluded.razao_social),
            nome_fantasia = coalesce(excluded.nome_fantasia, mei_email.empresas.nome_fantasia),
            situacao_cadastral = excluded.situacao_cadastral,
            uf = excluded.uf,
            email = excluded.email,
            ddd_1 = coalesce(excluded.ddd_1, mei_email.empresas.ddd_1),
            telefone_1 = coalesce(excluded.telefone_1, mei_email.empresas.telefone_1),
            data_abertura = coalesce(excluded.data_abertura, mei_email.empresas.data_abertura)
    """


def _upsert_batch(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    one = "(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    sql = build_upsert_sql(",".join(one for _ in rows))
    params: list[object] = []
    for row in rows:
        params.extend(
            [
                row["cnpj"],
                row["razao_social"],
                row["nome_fantasia"],
                row["situacao_cadastral"],
                row["uf"],
                row["email"],
                row["ddd_1"],
                row["telefone_1"],
                row["data_abertura"],
            ]
        )
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return max(int(cur.rowcount or 0), 0)


def process_establishment_zip(
    conn,
    path: Path,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[int, int, int]:
    rows_read = 0
    eligible = 0
    upserted = 0
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise RuntimeError(f"ZIP Receita corrompido: {path.name}") from exc
    with archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if len(members) != 1:
            raise RuntimeError(
                f"ZIP Receita {path.name} deve conter exatamente um arquivo de dados"
            )
        with archive.open(members[0], "r") as raw:
            text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
            reader = csv.reader(text, delimiter=";")
            batch: list[dict] = []
            for row in reader:
                rows_read += 1
                parsed = parse_establishment_row(row)
                if parsed is None:
                    continue
                eligible += 1
                batch.append(parsed)
                if len(batch) >= batch_size:
                    upserted += _upsert_batch(conn, batch)
                    batch.clear()
            if batch:
                upserted += _upsert_batch(conn, batch)
    return rows_read, eligible, upserted


def import_snapshot(
    conn,
    manifest: SnapshotManifest,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    reserve_bytes: int = DEFAULT_DISK_RESERVE_BYTES,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> ImportStats:
    if not manifest.token:
        raise RuntimeError("Manifesto Receita sem token WebDAV")
    stats = ImportStats()
    cache_dir.mkdir(parents=True, exist_ok=True)
    for remote in manifest.files:
        path = download_remote_zip(
            remote,
            token=manifest.token,
            cache_dir=cache_dir,
            timeout_seconds=timeout_seconds,
            reserve_bytes=reserve_bytes,
        )
        try:
            rows_read, eligible, upserted = process_establishment_zip(
                conn,
                path,
                batch_size=batch_size,
            )
            conn.commit()
            stats.files_processed += 1
            stats.rows_read += rows_read
            stats.eligible += eligible
            stats.upserted += upserted
        except Exception:
            conn.rollback()
            raise
        finally:
            path.unlink(missing_ok=True)
            (cache_dir / f"{remote.name}.part").unlink(missing_ok=True)
    return stats


def manifest_public_summary(manifest: SnapshotManifest) -> dict:
    parsed = urllib.parse.urlparse(manifest.source_url)
    return {
        "competence": manifest.competence,
        "source_host": parsed.netloc,
        "files": [{"name": item.name, "size": item.size} for item in manifest.files],
    }

# Database reconciliation is split from transport so WebDAV parsing/downloading
# stays focused. These aliases keep the public API stable for callers/tests.
try:
    from scripts import receita_snapshot_reconcile as _snapshot_reconcile
except ImportError:  # direct execution from scripts/
    import receita_snapshot_reconcile as _snapshot_reconcile  # type: ignore

ExistingCnpjBloom = _snapshot_reconcile.ExistingCnpjBloom
ImportStats = _snapshot_reconcile.ImportStats
classify_establishment_row = _snapshot_reconcile.classify_establishment_row
parse_establishment_row = _snapshot_reconcile.parse_establishment_row
build_upsert_sql = _snapshot_reconcile.build_upsert_sql
build_reconcile_existing_sql = _snapshot_reconcile.build_reconcile_existing_sql
process_establishment_zip = _snapshot_reconcile.process_establishment_zip
import_snapshot = _snapshot_reconcile.import_snapshot
