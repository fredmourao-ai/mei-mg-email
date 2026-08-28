# AI Conflict Resolver — Design

Date: 2026-08-27
Status: proposed
Repository: fredmourao-ai/mei-mg-email

## Goal

Add a conservative AI-assisted merge-conflict resolver that has no per-token API cost and does not bypass repository safety checks.

## Current constraint

GitHub Models was retired on 2026-07-30. The implementation therefore must not depend on GitHub Models. AI inference will run locally on a self-hosted runner using Ollama or llama.cpp.

## Architecture

1. A GitHub Actions workflow reacts to pull_request_target/pull_request synchronization events and can also be started manually.
2. A detection job checks whether the PR branch can merge cleanly with the target branch.
3. If conflicts exist, the workflow checks out a disposable workspace on a dedicated self-hosted runner and attempts the merge without committing.
4. Only conflicted files and bounded context are sent to a local inference endpoint on the same trusted runner/host.
5. The resolver produces candidate file contents.
6. Deterministic guards reject unsafe output.
7. Repository tests run.
8. If validation succeeds, the workflow commits only to an allowed same-repository PR branch. It never merges the PR itself.
9. If validation or confidence gates fail, the workflow leaves the branch unchanged and reports that human review is required.

## Security boundaries

- Least-privilege GITHUB_TOKEN permissions.
- No secrets, .env files, credentials, certificates, private keys, database dumps, deployment credentials, or production data are passed to the model.
- No automatic resolution for destructive database migrations, billing/payment logic, production deployment controls, GitHub workflow permission changes, authentication/authorization code, or mass deletion changes.
- No `git checkout --ours` / `--theirs` blanket strategy.
- Never force-push.
- Never push to forks using privileged pull_request_target context.
- The AI may combine compatible edits, but must preserve both sides unless a deterministic rule or tests justify removal.

## Repository-specific protection

For mei-mg-email, email-safety CI, repository policy guards, sending limits, suppression logic, Microsoft Graph provider behavior, campaign eligibility filters, database migrations, and any workflow that can trigger production email sends are treated as protected/high-risk. Conflicts touching these areas require either deterministic resolution with existing tests or human review.

## Proposed files

- `.github/workflows/ai-conflict-resolver.yml`
- `.github/scripts/ai_conflict_resolver.py`
- `.github/scripts/validate_conflict_resolution.sh`
- `AI_CONFLICT_RULES.md`
- tests for parser, protected-path handling, marker detection, and unsafe-output rejection

## Model runtime

Primary: Ollama on a self-hosted Linux runner reachable only locally/private network. The model is configurable by environment and defaults to a code-capable local model sized for the available host.

The workflow must fail closed when the local inference service is unavailable.

## Resolution flow

For every conflicted file, construct a structured prompt containing BASE/OURS/THEIRS plus repository rules. The response must return only the full proposed file content in a machine-validated envelope. The resolver rejects responses containing conflict markers, unexplained file deletion, unexpected path changes, or content for a different file.

## Validation

Before any commit:

1. no `<<<<<<<`, `=======`, or `>>>>>>>` markers remain;
2. only originally conflicted/explicitly allowed generated files changed;
3. protected files are blocked or require human review;
4. repository policy/safety tests pass;
5. syntax/lint/type checks run where available;
6. no secrets are added;
7. diff-size and deletion thresholds remain within conservative limits.

## Commit and PR behavior

Successful automatic resolutions create a normal commit on an eligible same-repository PR branch with a machine-identifiable message. The workflow does not merge the PR and does not alter branch protection. Existing auto-merge logic may act later only after all normal required checks pass.

## Failure behavior

On ambiguity, unavailable model, failed tests, protected-path conflict, fork PR, or unsafe diff, the job exits without modifying the PR branch and records a concise diagnostic.

## Cost model

No paid AI API is required. Self-hosted GitHub Actions runners do not consume GitHub-hosted Actions minutes. Compute cost is limited to infrastructure already operated by the project.

## Rollout

Start in report-only/dry-run mode, validate against real conflicted PRs, then enable write-back only after the dry-run behavior is confirmed. Production-send/deploy capabilities remain outside the resolver.
