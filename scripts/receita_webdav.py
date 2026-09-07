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
import urllib.parse
import xml.etree.ElementTree as ET
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
USER_AGENT = "ShopVivaliz-MEI-receita-webdav/1.0"
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
COMPETENCE_RE = re.compile(r"^\d{4}-\d{2}$")
EXPECTED_ARCHIVES = tuple(f"Estabelecimentos{i}.zip" for i in range(10))
DAV = "{DAV:}"


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


def resolve_share_url(url: str, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS) -> str:
    """Resolve the stable Receita host to the currently active public share."""
    parsed = urllib.parse.urlparse(url)
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
    if "/s/" not in urllib.parse.urlparse(final_url).path:
        raise RuntimeError("Receita nao redirecionou para um share publico /s/")
    return final_url


def parse_share_url(
    url: str,
    *,
    default_directory: str = DEFAULT_DIRECTORY,
) -> tuple[str, str, str]:
    parsed = urllib.parse.urlparse(url)
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
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RuntimeError("Receita WebDAV retornou XML invalido") from exc
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


def download_remote_zip(
    remote: RemoteZip,
    *,
    token: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    reserve_bytes: int = DEFAULT_DISK_RESERVE_BYTES,
) -> Path:
    ensure_disk_headroom(
        cache_dir,
        remote_size=remote.size,
        reserve_bytes=reserve_bytes,
    )
    final = cache_dir / remote.name
    part = cache_dir / f"{remote.name}.part"
    part.unlink(missing_ok=True)
    req = Request(
        remote.url,
        headers={"Authorization": _basic_auth(token), "User-Agent": USER_AGENT},
        method="GET",
    )
    total = 0
    try:
        with urlopen(req, timeout=timeout_seconds) as response, part.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
                total += len(chunk)
        if total != remote.size:
            raise RuntimeError(
                f"ZIP Receita truncado {remote.name}: recebido={total} esperado={remote.size}"
            )
        part.replace(final)
        return final
    except HTTPError as exc:
        part.unlink(missing_ok=True)
        raise RuntimeError(
            f"Receita WebDAV HTTP {exc.code} ao baixar {remote.name}"
        ) from exc
    except URLError as exc:
        part.unlink(missing_ok=True)
        raise RuntimeError(
            f"Receita WebDAV indisponivel ao baixar {remote.name}: {exc.reason}"
        ) from exc
    except Exception:
        part.unlink(missing_ok=True)
        raise


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
