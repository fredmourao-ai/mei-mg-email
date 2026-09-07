"""Snapshot reconciliation for Receita Federal establishment data.

Keeps WebDAV transport separate from database reconciliation. Existing CNPJs
are represented by a bounded Bloom filter so inactive/invalid rows can update
only records that may already exist without loading millions of strings in RAM.
"""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import zlib
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
CNPJ_RE = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")
STATUS = {"01": "NULA", "02": "ATIVA", "03": "SUSPENSA", "04": "INAPTA", "08": "BAIXADA"}
DEFAULT_BLOOM_BYTES = max(int(os.getenv("RECEITA_EXISTING_BLOOM_BYTES", str(64 * 1024**2))), 1024)
DEFAULT_BLOOM_HASHES = max(int(os.getenv("RECEITA_EXISTING_BLOOM_HASHES", "4")), 2)
DEFAULT_COMMIT_EVERY_BATCHES = max(int(os.getenv("RECEITA_COMMIT_EVERY_BATCHES", "20")), 1)
DEFAULT_RESERVE_BYTES = max(int(os.getenv("RECEITA_WEBDAV_DISK_RESERVE_BYTES", str(2 * 1024**3))), 256 * 1024**2)


class ExistingCnpjBloom:
    def __init__(self, *, bytes_size: int = DEFAULT_BLOOM_BYTES, hashes: int = DEFAULT_BLOOM_HASHES):
        self.bits = bytearray(max(int(bytes_size), 1))
        self.hashes = max(int(hashes), 1)
        self.bit_count = len(self.bits) * 8

    def _positions(self, value: str):
        data = str(value).encode("ascii", errors="ignore")
        h1 = zlib.crc32(data) & 0xFFFFFFFF
        h2 = zlib.crc32(data, 0x9E3779B9) & 0xFFFFFFFF
        if h2 == 0:
            h2 = 0x85EBCA6B
        for index in range(self.hashes):
            yield (h1 + index * h2 + index * index * 0x27D4EB2D) % self.bit_count

    def add(self, value: str) -> None:
        for position in self._positions(value):
            byte, bit = divmod(position, 8)
            self.bits[byte] |= 1 << bit

    def __contains__(self, value: object) -> bool:
        for position in self._positions(str(value)):
            byte, bit = divmod(position, 8)
            if not self.bits[byte] & (1 << bit):
                return False
        return True


@dataclass
class ImportStats:
    files_processed: int = 0
    rows_read: int = 0
    eligible: int = 0
    upserted: int = 0
    reconciled_existing: int = 0
    existing_indexed: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


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


def classify_establishment_row(row: list[str]) -> dict | None:
    if len(row) < 28:
        return None
    values = [str(value or "").strip().strip('"') for value in row]
    basic = values[0].upper().zfill(8)
    order = values[1].upper().zfill(4)
    dv = values[2].upper().zfill(2)
    cnpj = f"{basic}{order}{dv}"
    if not CNPJ_RE.fullmatch(cnpj):
        return None
    status = STATUS.get(values[5], values[5] or "DESCONHECIDA")
    uf = values[19].upper() if re.fullmatch(r"[A-Za-z]{2}", values[19]) else None
    raw_email = values[27].strip().lower()
    email = raw_email if EMAIL_RE.fullmatch(raw_email) and "contabil" not in raw_email else None
    eligible = status == "ATIVA" and email is not None and uf is not None
    fantasia = _clean(values[4])
    return {
        "cnpj": cnpj,
        "razao_social": fantasia,
        "nome_fantasia": fantasia,
        "situacao_cadastral": status,
        "uf": uf,
        "email": email,
        "ddd_1": _clean(values[21], 3),
        "telefone_1": _clean(values[22], 15),
        "data_abertura": _parse_date(values[10]),
        "eligible": eligible,
    }


def parse_establishment_row(row: list[str]) -> dict | None:
    classified = classify_establishment_row(row)
    if not classified or not classified["eligible"]:
        return None
    return {key: value for key, value in classified.items() if key != "eligible"}


def build_upsert_sql(values_clause: str = "(%s,%s,%s,%s,%s,%s,%s,%s,%s)") -> str:
    return f"""
        insert into mei_email.empresas as current
            (cnpj, razao_social, nome_fantasia, situacao_cadastral,
             uf, email, ddd_1, telefone_1, data_abertura)
        values {values_clause}
        on conflict (cnpj) do update set
            razao_social = coalesce(current.razao_social, excluded.razao_social),
            nome_fantasia = coalesce(excluded.nome_fantasia, current.nome_fantasia),
            situacao_cadastral = excluded.situacao_cadastral,
            uf = excluded.uf,
            email = excluded.email,
            ddd_1 = coalesce(excluded.ddd_1, current.ddd_1),
            telefone_1 = coalesce(excluded.telefone_1, current.telefone_1),
            data_abertura = coalesce(excluded.data_abertura, current.data_abertura)
        where (current.razao_social, current.nome_fantasia, current.situacao_cadastral,
               current.uf, current.email, current.ddd_1, current.telefone_1, current.data_abertura)
          is distinct from
              (coalesce(current.razao_social, excluded.razao_social),
               coalesce(excluded.nome_fantasia, current.nome_fantasia), excluded.situacao_cadastral,
               excluded.uf, excluded.email, coalesce(excluded.ddd_1, current.ddd_1),
               coalesce(excluded.telefone_1, current.telefone_1),
               coalesce(excluded.data_abertura, current.data_abertura))
    """


def build_reconcile_existing_sql(values_clause: str = "(%s,%s,%s)") -> str:
    return f"""
        update mei_email.empresas as current
           set situacao_cadastral = incoming.situacao_cadastral,
               uf = coalesce(incoming.uf, current.uf),
               email = case
                   when incoming.situacao_cadastral = 'ATIVA' then null
                   else current.email
               end
          from (values {values_clause})
               as incoming(cnpj, situacao_cadastral, uf)
         where current.cnpj::text = incoming.cnpj
           and (current.situacao_cadastral, current.uf, current.email)
               is distinct from
               (incoming.situacao_cadastral,
                coalesce(incoming.uf, current.uf),
                case when incoming.situacao_cadastral = 'ATIVA' then null else current.email end)
    """


def _upsert_batch(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    one = "(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    params: list[object] = []
    for row in rows:
        params.extend([row["cnpj"], row["razao_social"], row["nome_fantasia"],
                       row["situacao_cadastral"], row["uf"], row["email"],
                       row["ddd_1"], row["telefone_1"], row["data_abertura"]])
    with conn.cursor() as cur:
        cur.execute(build_upsert_sql(",".join(one for _ in rows)), params)
        return max(int(cur.rowcount or 0), 0)


def _reconcile_batch(conn, rows: list[dict]) -> int:
    if not rows:
        return 0
    one = "(%s,%s,%s)"
    params: list[object] = []
    for row in rows:
        params.extend([row["cnpj"], row["situacao_cadastral"], row["uf"]])
    with conn.cursor() as cur:
        cur.execute(build_reconcile_existing_sql(",".join(one for _ in rows)), params)
        return max(int(cur.rowcount or 0), 0)


def load_existing_bloom(conn) -> tuple[ExistingCnpjBloom, int]:
    bloom = ExistingCnpjBloom()
    count = 0
    with conn.cursor(name="receita_existing_cnpj_bloom") as cur:
        cur.itersize = 50000
        cur.execute("select cnpj::text from mei_email.empresas")
        for row in cur:
            bloom.add(str(row[0]))
            count += 1
    conn.commit()
    return bloom, count


def _check_processing_headroom(path: Path, reserve_bytes: int) -> None:
    free = shutil.disk_usage(path.parent).free
    if free < reserve_bytes:
        raise RuntimeError(
            f"espaco insuficiente durante processamento Receita: livre={free} reserva={reserve_bytes}"
        )


def process_establishment_zip(
    conn,
    path: Path,
    *,
    existing_bloom: ExistingCnpjBloom,
    batch_size: int = 1000,
    commit_every_batches: int = DEFAULT_COMMIT_EVERY_BATCHES,
    reserve_bytes: int = DEFAULT_RESERVE_BYTES,
) -> tuple[int, int, int, int]:
    rows_read = eligible = upserted = reconciled = 0
    eligible_batch: list[dict] = []
    reconcile_batch: list[dict] = []
    batches_since_commit = 0

    def commit_if_needed(force: bool = False) -> None:
        nonlocal batches_since_commit
        if force or batches_since_commit >= commit_every_batches:
            conn.commit()
            batches_since_commit = 0
            _check_processing_headroom(path, reserve_bytes)

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
            reader = csv.reader(io.TextIOWrapper(raw, encoding="latin-1", newline=""), delimiter=";")
            for row in reader:
                rows_read += 1
                classified = classify_establishment_row(row)
                if classified is None:
                    continue
                if classified["eligible"]:
                    eligible += 1
                    eligible_batch.append(classified)
                    if len(eligible_batch) >= batch_size:
                        upserted += _upsert_batch(conn, eligible_batch)
                        eligible_batch.clear()
                        batches_since_commit += 1
                        commit_if_needed()
                elif classified["cnpj"] in existing_bloom:
                    reconcile_batch.append(classified)
                    if len(reconcile_batch) >= batch_size:
                        reconciled += _reconcile_batch(conn, reconcile_batch)
                        reconcile_batch.clear()
                        batches_since_commit += 1
                        commit_if_needed()
    if eligible_batch:
        upserted += _upsert_batch(conn, eligible_batch)
        batches_since_commit += 1
    if reconcile_batch:
        reconciled += _reconcile_batch(conn, reconcile_batch)
        batches_since_commit += 1
    commit_if_needed(force=True)
    return rows_read, eligible, upserted, reconciled


def import_snapshot(
    conn,
    manifest,
    *,
    cache_dir: Path | None = None,
    timeout_seconds: int | None = None,
    reserve_bytes: int | None = None,
    batch_size: int | None = None,
) -> ImportStats:
    try:
        from scripts import receita_webdav as web
    except ImportError:
        import receita_webdav as web

    if not manifest.token:
        raise RuntimeError("Manifesto Receita sem token WebDAV")
    cache_dir = cache_dir or web.DEFAULT_CACHE_DIR
    timeout_seconds = timeout_seconds or web.DEFAULT_TIMEOUT_SECONDS
    reserve_bytes = reserve_bytes if reserve_bytes is not None else web.DEFAULT_DISK_RESERVE_BYTES
    batch_size = batch_size or web.DEFAULT_BATCH_SIZE
    existing_bloom, existing_count = load_existing_bloom(conn)
    stats = ImportStats(existing_indexed=existing_count)
    cache_dir.mkdir(parents=True, exist_ok=True)
    for remote in sorted(manifest.files, key=lambda item: item.size):
        path = web.download_remote_zip(
            remote,
            token=manifest.token,
            cache_dir=cache_dir,
            timeout_seconds=timeout_seconds,
            reserve_bytes=reserve_bytes,
        )
        try:
            rows_read, eligible, upserted, reconciled = process_establishment_zip(
                conn,
                path,
                existing_bloom=existing_bloom,
                batch_size=batch_size,
                reserve_bytes=reserve_bytes,
            )
            stats.files_processed += 1
            stats.rows_read += rows_read
            stats.eligible += eligible
            stats.upserted += upserted
            stats.reconciled_existing += reconciled
        except Exception:
            conn.rollback()
            raise
        finally:
            path.unlink(missing_ok=True)
    return stats
