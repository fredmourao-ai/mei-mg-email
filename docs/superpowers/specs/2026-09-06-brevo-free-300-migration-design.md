# Brevo Free 300 Migration Design

## Goal
Migrate production e-mail delivery from the cancelled Microsoft Graph path to Brevo Transactional Email while preserving the current canonical eligibility policy and enforcing a fail-closed Brevo Free quota.

## Binding constraints
- Production provider is Brevo API; Graph must not be selectable by the production worker after cutover.
- Brevo Free hard cap is **300 accepted submissions in any rolling 24-hour window**.
- Operational target is **295/24h**, reserving 5 messages for controlled/internal validation without ever exceeding 300.
- Queue buffer remains `QUEUE_MIN_PENDING=14800` and `QUEUE_TARGET_PENDING=15000`.
- Canonical eligibility is exactly the current `AGENTS.md`: ATIVA; reject email containing `contabil`; reject email shared by more than 2 records; reject recipient/CNPJ already sent or queued; MG is ordering only.
- No retired authorization/MEI/UF gates may return under a new name.
- `submitted` means accepted by Brevo, never delivered.
- Every commit is pushed immediately; completion requires validated PR, merge and post-merge checks.

## Provider contract
`BrevoEmailProvider` sends one recipient per `POST https://api.brevo.com/v3/smtp/email` using `api-key`, the fixed allowed sender `naoresponda@dev.shopvivaliz.com.br`, and `fiscalmelo@hotmail.com` as reply-to.

HTTP 201 is successful only when a non-empty Brevo `messageId` is returned. The stored provider ID is prefixed as `brevo:<messageId>` so provider attribution is explicit without a schema migration. Authentication material is read only from `BREVO_API_KEY` and is never logged.
## Quota and replay semantics
Brevo quota accounting counts only rows with `provider_message_id LIKE 'brevo:%'` and `submitted_at` inside the rolling 24-hour window, plus external quota rows whose provider ID/source identifies Brevo. Historical Graph submissions therefore do not consume Brevo quota.

Anti-replay is provider-independent: any prior accepted send with durable `provider_message_id` plus `submitted_at`, as well as the external ledger, continues to suppress a resend even after the row becomes `delivered` or `bounce_permanent`.

The worker checks quota immediately before every external call. Runtime configuration is clamped in code to a maximum of 300 even if stale `.env` values still contain 9,500/10,000. Production `.env` is nevertheless rewritten to `MAX_ENVIOS_POR_DIA=300` and `META_ENVIOS_POR_DIA=295` during cutover.

## Delivery reconciliation
A deterministic resident reconciler polls `GET https://api.brevo.com/v3/smtp/statistics/events`, matches exact Brevo message IDs and records final outcomes:
- `delivered` -> `delivered`, set `delivered_at` and `reconciled_at`;
- `hardBounce`, `invalid`, `blocked`, or `spam` -> `bounce_permanent`, set bounce/error evidence and register durable `hard_bounce` suppression with source `brevo_event_reconciler`;
- `softBounce`, `deferred`, or transient `error` -> keep the accepted send non-replayable and record diagnostic evidence without permanent suppression;
- request/open/click and other informational events do not upgrade an email to delivered.

The reconciler is idempotent. The legacy Exchange NDR guard is disabled in production after Brevo validation.

## Fail-closed cutover
The existing persistent pause `/var/lib/mei-mg-email/sender_blocked.pause` remains present throughout migration. It is removed only after the merged code is deployed, Brevo credentials and sender identity validate, the old NDR guard is disabled, the Brevo reconciler is healthy, and one internal controlled message is accepted and then observed as `delivered` by Brevo.
## Controlled validation
`scripts/enviar_teste_brevo.py` uses the current approved template and the internal default `atendimento@shopvivaliz.com.br`. It records an accepted test in `envios_externos_cota` with a Brevo-specific source, then polls Brevo for the exact message ID with a bounded timeout. The validation succeeds only on a real `delivered` event and fails on permanent bounce/block/spam/invalid events.

## Runtime and monitoring
`runtime_sender_preflight.py` fails closed unless production uses Brevo, a non-empty Brevo key exists, the fixed sender is configured, and effective quota values are <=300. The worker systemd description and installer become Brevo-specific. Monitoring reports Brevo accepted submissions and requires the Brevo event reconciler instead of the Exchange NDR guard.

## Deployment and rollback
Deployment follows repository governance: policy guard + full tests -> commit -> immediate push -> PR -> independent CI -> merge -> post-merge checks -> production deploy. Production is never resumed on an unmerged tree.

Rollback is fail-closed: recreate/retain the pause sentinel and stop Brevo sending. Do not reactivate Graph as a fallback because Graph was cancelled. Queue data and canonical eligibility remain untouched.

## Success criteria
1. All repository tests and policy/security gates pass.
2. `EMAIL_PROVIDER=brevo`, effective hard cap 300 and target 295 are proven at runtime.
3. Graph production send path and Exchange NDR guard are inactive.
4. Controlled Brevo message produces a Brevo `messageId` and a subsequent real `delivered` event.
5. The controlled test is counted against Brevo quota.
6. Worker resumes with remaining Brevo capacity only, never exceeding 300 in rolling 24h.
7. Git working tree is clean; PR merged; resulting main SHA has no failed/pending relevant Actions.