# Receita Federal WebDAV Base Sync Design

## Objective

Replace the paid Casa dos Dados daily dependency with the official Receita Federal public CNPJ snapshot exposed through its Nextcloud/WebDAV share, while preserving the repository's canonical eligibility rules and keeping the email worker independent from base refresh.

## Approved operating policy

The canonical eligibility policy remains exactly the one in `AGENTS.md`:

- company status must be `ATIVA`;
- recipient email must not contain `contabil`;
- an email shared by more than 2 company records is excluded;
- recipient/CNPJ already sent or queued is excluded at queue/submission time;
- MG is ordering priority only, never an eligibility filter;
- retired legacy gates must not be reintroduced.

No part of this design changes opt-out, suppression, replay protection, queue target, or provider attribution.

## Source

Primary source: the official Receita Federal public Nextcloud share at `https://arquivos.receitafederal.gov.br/index.php/s/TwY6Wd9h4aQ6DdP?dir=/`.

The sync resolves the public share into `/public.php/webdav`, performs authenticated public-share `PROPFIND` with the share token as username and blank password, discovers the newest `YYYY-MM` directory, and requires exactly the ten `Estabelecimentos0.zip` ... `Estabelecimentos9.zip` files before importing a new competence.

`CNPJ_DAILY_SOURCE=receita_webdav` becomes the documented/default production source. Casa dos Dados and Hugging Face remain explicit manual/fallback modes only; they are not required for normal worker operation.

## Daily behavior

`mei-mg-email-base-sync.timer` continues to run daily. Each run:

1. acquires the existing PostgreSQL advisory lock;
2. discovers the latest official Receita competence;
3. derives revision `receita:<YYYY-MM>`;
4. if the latest successful/no-change run already has that revision, records a fresh `no_change` run and exits 0 without downloading data;
5. otherwise validates the complete ten-file manifest and disk headroom, imports the new competence, records row counts and manifest metadata, and exits 0 only after the full import succeeds.

The sync never creates campaigns and never starts the email worker.

## Disk-safe import

The VM currently has limited root-disk headroom. Therefore files are handled sequentially:

- download exactly one ZIP to a state/cache directory outside the Git checkout;
- use `.part` while downloading and atomic rename after the exact remote size is reached;
- open the CSV directly from `zipfile.ZipFile` without extracting the uncompressed file to disk;
- stage eligible rows into a PostgreSQL temporary table;
- delete the ZIP before downloading the next one;
- require free space greater than the current ZIP size plus a fixed safety reserve before each download.

This bounds local transient disk use to one compressed ZIP at a time.

## Eligibility and staging

The importer reads Receita establishment columns and stages only rows that are `ATIVA`, have a syntactically valid email, and whose email does not contain `contabil`.

After all ten ZIPs are staged, SQL computes email multiplicity across the complete imported competence. Only emails occurring in at most two staged CNPJs are upserted into `mei_email.empresas`.

Upsert behavior preserves user/stateful data. It may refresh CNPJ identity/contact fields, but it never clears opt-out, suppression, send history, or provider submission evidence. Queue-level global dedupe remains responsible for excluding CNPJ/email already sent or queued.

MG is never used in the import `WHERE` clause.

## Failure semantics

The sync is fail-closed. It records `failed` and returns nonzero when any of these occur:

- WebDAV is unreachable or malformed;
- no valid competence exists;
- any of the ten establishment files is missing, duplicated, zero-sized, truncated, or corrupt;
- disk headroom is below the configured reserve;
- CSV/ZIP parsing fails;
- staging/upsert fails.

A partial new competence is never recorded as success. A failed run does not delete or invalidate the previously imported production base.

## Monitoring

The existing monitor already treats `failed` as critical and accepts `no_change`. A successful daily WebDAV check therefore refreshes base-sync freshness even when Receita has not published a new month.

Audit details stored in `mei_email.base_sync_runs.details` include competence, source URL host, manifest names/sizes, staged count, accepted count, excluded-shared-email count, and the disk-safety settings. No credentials are logged.

## Brevo release

Base refresh remains operationally separate from sending. After the new source is deployed and a real base-sync returns `success` or `no_change`, release validation must also verify:

- Brevo runtime preflight passes;
- queue is populated and has no stale `enviando` records;
- rolling 24-hour attribution counts queue submissions plus external Brevo test sends;
- runtime target is explicitly set to 300/24h when approved by the user, never exceeding hard cap 300;
- pause sentinel is removed only after all guards pass;
- worker and reconciler are active;
- real queue submissions receive `brevo:` provider IDs;
- Brevo reconciliation observes real `delivered` events;
- rolling total never exceeds 300.

The user explicitly approved this architecture and requested operation at the 300-email/24h ceiling.