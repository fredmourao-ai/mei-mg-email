# AI Conflict Resolver — Design

Date: 2026-08-27
Status: implemented
Repository: fredmourao-ai/mei-mg-email

## Goal

Add a conservative AI-assisted merge-conflict resolver with no paid AI API or per-token charge, without bypassing repository safety checks.

## Runtime decision

GitHub Models was retired on 2026-07-30, so the implementation does not depend on it. For portability, inference runs locally inside a GitHub-hosted `ubuntu-latest` job: Ollama is installed only after a safe conflict is confirmed and the workflow pulls `qwen2.5-coder:1.5b`. Private repositories may still consume the account's included GitHub Actions minutes; the zero-cost guarantee applies to AI API/token billing, not runner compute.

## Architecture

1. A GitHub Actions workflow reacts to pull-request open/reopen/synchronize events and supports manual execution.
2. Unit tests and Python syntax validation run first.
3. Same-repository PRs only are checked against their target branch with `git merge --no-ff --no-commit`.
4. If there is no conflict, the merge attempt is aborted and the resolver exits without changes.
5. If conflicts exist, deterministic path guards run before any model installation or inference.
6. Protected conflicts are never sent to a model and require human review.
7. For safe conflicts only, the job starts local Ollama and sends BASE/OURS/THEIRS plus bounded repository rules to the local endpoint.
8. Candidate full-file contents are machine-validated, staged, checked for unresolved markers, and unit-tested.
9. If validation succeeds, the workflow creates a normal commit on the eligible PR branch and pushes without force. It never merges the PR itself.

## Security boundaries

- `contents: write` is limited to the resolver workflow's same-repository PR write-back; `pull-requests` permission is read-only.
- Fork PRs and Dependabot PRs do not execute write-back.
- No secrets, `.env` files, credentials, certificates, private keys, database dumps, deployment credentials, or production data are passed to the model.
- No automatic resolution for migrations, billing/payment logic, production deployment controls, GitHub workflow changes, authentication/authorization code, mass deletion changes, or repository-specific sending safety surfaces.
- No blanket `git checkout --ours` / `--theirs` strategy.
- Never force-push.
- The model may combine compatible edits, but deterministic guards reject conflict markers, empty output, path mismatch, sensitive-content signatures, binary content, and excessive deletion.

## Repository-specific protection

For `mei-mg-email`, email-safety CI, repository policy guards, sending limits, suppression logic, Microsoft Graph provider behavior, campaign eligibility filters, recipient/rate-limit logic, database migrations, and workflows that can trigger production email sends are protected/high-risk and are not model-resolved.

## Implemented files

- `.github/workflows/ai-conflict-resolver.yml`
- `.github/scripts/ai_conflict_resolver.py`
- `AI_CONFLICT_RULES.md`
- `tests/test_ai_conflict_resolver.py`
- `docs/superpowers/plans/2026-08-27-ai-conflict-resolver.md`

## Resolution contract

For every eligible conflicted file, the resolver builds a structured prompt containing BASE/OURS/THEIRS plus repository rules. The local model must return one JSON object with exactly the same path and the complete proposed file contents. The wrapper validates the JSON envelope and candidate before writing anything.

## Validation

Before write-back:

1. no unresolved Git conflict files remain;
2. no `<<<<<<<`, `=======`, or `>>>>>>>` markers remain in candidates;
3. protected paths and sensitive content never reach inference;
4. the candidate is non-empty and does not exceed the conservative deletion threshold;
5. `git diff --check` passes;
6. resolver unit tests pass;
7. existing repository CI and policy checks remain authoritative after the push.

## Commit and PR behavior

Successful automatic resolutions create a normal commit on an eligible same-repository PR branch with message `chore: resolve merge conflicts with local AI`. The workflow does not merge the PR and does not alter branch protection. Existing auto-merge logic may act later only after normal required checks pass.

## Failure behavior

On ambiguity, unavailable model, failed validation, protected-path conflict, fork PR, sensitive/binary content, or unsafe diff, the resolver leaves the PR branch unchanged and records a concise job summary requiring human review.

## Cost model

No paid AI API is required and no per-token model billing is incurred. The workflow uses GitHub-hosted Actions compute, which may draw from the repository/account's included Actions allowance depending on plan and visibility. Ollama/model download occurs only when an eligible safe conflict actually exists.
