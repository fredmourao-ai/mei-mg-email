# Repository governance

Mandatory flow for every code, configuration, workflow, infrastructure, or documentation change:

`feature branch -> real validation -> commit -> clean working tree -> push -> pull request -> independent CI validation -> merge -> post-merge verification`

Direct commits or pushes to `main`/`master` are forbidden. Agents must not use `--no-verify` or any equivalent bypass. A failed validation blocks commit, push, PR merge, and task completion until fixed or explicitly reported as a blocker.

Before finishing any task, run `git status --porcelain=v1`; it must be empty for the task branch/worktree. Existing unrelated dirty worktrees must be preserved and must not be silently cleaned, reset, stashed, or overwritten.

Every clone/worktree must enable the versioned hooks once with:

`git config core.hooksPath .githooks`

The GitHub governance workflow repeats validation independently. Native branch protection for `main` must require pull requests and the status checks `safety`, `policy-guard`, `governance-gate`, `self-test`, and `resolve`, with strict/up-to-date checks enabled.

Native GitHub auto-merge must remain disabled (`allow_auto_merge=false`). The required `policy-guard` workflow verifies that live repository setting and fails closed if it is re-enabled, preventing the native merge path from bypassing the resolver gate.

For this private repository, `.github/workflows/pr-auto-merge.yml` is the canonical automatic merge gate. It resolves same-repository pull requests by exact head SHA through the REST API and permits squash merge only after every applicable check run is completed with `success`, `skipped`, or `neutral`, the `resolve` job is materialized and green/skipped, and any legacy commit statuses are successful. It must react to completion of every pull-request gate so the last green gate can finalize the merge without bypassing validation.
