# Repository governance

Mandatory flow for every code, configuration, workflow, infrastructure, or documentation change:

`feature branch -> real validation -> commit -> clean working tree -> push -> pull request -> independent CI validation -> merge -> post-merge verification`

Direct commits or pushes to `main`/`master` are forbidden. Agents must not use `--no-verify` or any equivalent bypass. A failed validation blocks commit, push, PR merge, and task completion until fixed or explicitly reported as a blocker.

Before finishing any task, run `git status --porcelain=v1`; it must be empty for the task branch/worktree. Existing unrelated dirty worktrees must be preserved and must not be silently cleaned, reset, stashed, or overwritten.

Every clone/worktree must enable the versioned hooks once with:

`git config core.hooksPath .githooks`

The GitHub governance workflow repeats validation independently. Native branch protection/rulesets must additionally require pull requests and the governance status check wherever the GitHub plan supports those controls.
