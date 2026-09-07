# Receita Federal WebDAV Base Sync Design

## Objective

Replace the paid Casa dos Dados daily dependency with the official Receita Federal public CNPJ snapshot exposed through Nextcloud/WebDAV, while preserving the repository's canonical eligibility rules and keeping the email worker independent from base refresh.

## Approved operating policy

The canonical eligibility policy remains exactly the one in `AGENTS.md`:

- company status must be `ATIVA`;
- recipient email must not contain `contabil`;
- an email shared by more than 2 company records is excluded from queue/send;
- recipient/CNPJ already sent or queued is excluded;
- MG is ordering priority only, never an eligibility filter;
- retired legacy gates must not be reintroduced.

No part of this design changes opt-out, suppression, replay protection, queue target, or provider attribution.

## Source and rotating share token

Primary source is the stable official host `https://arquivos.receitafederal.gov.br/`. The host currently redirects to the active public Nextcloud share; that share token is intentionally **not** stored in repository configuration because Receita rotates it.

At runtime the sync follows the official redirect, extracts the current public-share token, uses `/public.php/webdav` with public-share Basic auth, enters `Dados/Cadastros/CNPJ`, discovers the newest `YYYY-MM` directory, and requires exactly the ten `Estabelecimentos0.zip` ... `Estabelecimentos9.zip` files before importing a new competence.

`CNPJ_DAILY_SOURCE=receita_webdav` is the documented/default production source. Casa dos Dados and Hugging Face remain explicit manual/fallback modes only; they are not required for normal worker operation.

## Daily behavior

`mei-mg-email-base-sync.timer` continues to run daily. Each run:

1. acquires the existing PostgreSQL advisory lock;
2. resolves the currently active Receita share and discovers the latest competence;
3. derives revision `receita:<YYYY-MM>`;
4. if the latest successful/no-change run already has that revision, records a fresh `no_change` run and exits 0 without downloading data;
5. otherwise validates the complete ten-file manifest and disk headroom, imports the new competence, records row counts and manifest metadata, and exits 0 only after the full import succeeds.

The sync never creates campaigns and never starts the email worker.

## Disk-safe import

The VM has limited root-disk headroom. Files are therefore handled sequentially:

- download exactly one ZIP to `/var/lib/mei-mg-email/receita-cache`;
- use `.part` while downloading and atomic rename after the exact remote size is reached;
- open the CSV directly from `zipfile.ZipFile` without extracting the uncompressed file to disk;
- stream eligible rows in bounded SQL batches directly into `mei_email.empresas`;
- commit each completed ZIP so a long monthly import does not hold one giant transaction;
- delete the ZIP before downloading the next one;
- require free space greater than the current ZIP size plus a fixed safety reserve before every download.

This bounds transient filesystem use to one compressed ZIP and avoids a second multi-million-row staging copy inside PostgreSQL.

## Eligibility and shared-email rule

The importer persists only establishment rows that are `ATIVA`, have a syntactically valid e-mail, and whose e-mail does not contain `contabil`. It never restricts UF; a non-MG company remains importable.

The canonical shared-email rule is enforced at its actual policy boundary by the existing `app/queue_manager.py`. Before enqueue, `email_counts` counts `distinct cnpj` for every candidate email against the full `mei_email.empresas` table and only allows `shared_cnpjs <= 2`. This is stronger and safer than a per-ZIP or temporary staging count and avoids duplicating the whole Receita snapshot on disk.

Upsert behavior refreshes contact/identity fields only. It never clears or overwrites stateful opt-out, suppression, send-history, marketing-authorization, third-party classification, or provider submission evidence. Queue-level anti-replay remains responsible for excluding CNPJ/email already sent or queued.

MG is only an `ORDER BY` priority in the queue manager, never an import or eligibility filter.

## Failure semantics

The sync is fail-closed. It records `failed` and returns nonzero when any of these occur:

- official redirect cannot be resolved to a public share;
- WebDAV is unreachable or malformed;
- no valid competence exists;
- any of the ten establishment files is missing, duplicated, zero-sized, truncated, or corrupt;
- disk headroom is below the configured reserve;
- CSV/ZIP parsing fails;
- database upsert fails.

A partial new competence is never recorded as success. A failed run does not delete or invalidate the previously imported production base. Completed ZIP upserts are idempotent by CNPJ and can be safely repeated when the same failed competence is retried.

## Monitoring and audit

The existing monitor treats `failed` as critical and accepts `no_change`. A successful daily WebDAV check therefore refreshes base-sync freshness even when Receita has not published a new month.

Audit details stored in `mei_email.base_sync_runs.details` include competence, source host, manifest names/sizes, rows read, eligible rows, rows upserted and the no-worker safety marker. Public share tokens and secrets are not logged.

## Brevo release at 300

Base refresh remains operationally separate from sending. After the new source is deployed and a real base-sync returns `success` or `no_change`, release validation must also verify:

- Brevo runtime preflight passes;
- queue is populated and has no stale `enviando` records;
- rolling 24-hour attribution counts queue submissions plus external Brevo test sends;
- runtime target and hard cap are both exactly 300/24h, as explicitly approved by the user;
- the hard cap can never exceed 300 even if a larger environment value is configured;
- pause sentinel is removed only after all guards pass;
- worker and reconciler are active;
- real queue submissions receive `brevo:` provider IDs;
- Brevo reconciliation observes real `delivered` events;
- rolling attributed total reaches 300 and never exceeds 300.

The user explicitly approved this architecture and requested operation at the 300-email/24h ceiling.