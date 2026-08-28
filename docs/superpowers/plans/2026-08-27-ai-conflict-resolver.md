# AI Conflict Resolver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a zero-per-token-cost, conservative AI-assisted merge-conflict resolver for pull requests.

**Architecture:** GitHub Actions detects same-repository PR conflicts, runs deterministic safety checks, starts local Ollama on the runner with a small open model, asks it to resolve only non-protected conflicted files, validates the result, runs repository checks, and pushes a normal resolution commit to the PR branch. Fork PRs and protected paths fail closed without write-back.

**Tech Stack:** GitHub Actions, Python 3 standard library, git, Ollama, qwen2.5-coder:1.5b.

**Spec:** `docs/superpowers/specs/2026-08-27-ai-conflict-resolver-design.md`

## Global Constraints
- No paid AI API.
- Never force-push or merge the PR automatically.
- Never expose secrets or protected files to the model.
- Same-repository PR branches only.
- Existing repository CI/policy checks remain authoritative.

---

### Task 1: Deterministic safety core
**Files:** Create `.github/scripts/ai_conflict_resolver.py`; create `tests/test_ai_conflict_resolver.py`.
- [ ] Add tests for protected paths, conflict-marker rejection, JSON response parsing, and safe-path acceptance.
- [ ] Run tests and confirm RED before implementation.
- [ ] Implement the minimal standard-library helpers.
- [ ] Run tests and confirm GREEN.

### Task 2: Resolution command
**Files:** Modify `.github/scripts/ai_conflict_resolver.py`; create `AI_CONFLICT_RULES.md`.
- [ ] Read git stages BASE/OURS/THEIRS for each conflicted file.
- [ ] Reject protected or secret-bearing paths before inference.
- [ ] Call local Ollama `/api/generate` with JSON output.
- [ ] Write only validated full-file content, `git add` the file, and leave failures unresolved.
- [ ] Verify no conflict markers remain and no unexpected files changed.

### Task 3: GitHub Actions integration
**Files:** Create `.github/workflows/ai-conflict-resolver.yml`.
- [ ] Trigger on PR synchronize/open/reopen and manual dispatch.
- [ ] Skip forks and bots; use least privilege `contents: write`, `pull-requests: write`.
- [ ] Merge base without commit, exit success when there is no conflict.
- [ ] Install/start Ollama only after a safe conflict is confirmed; pull `qwen2.5-coder:1.5b`.
- [ ] Resolve, run unit tests and repository safety tests, commit, and push without force.

### Task 4: Verification and rollout
- [ ] Run unit tests on the branch.
- [ ] Confirm existing CI remains green or document pre-existing unrelated failures.
- [ ] Keep write-back guarded by same-repo, protected-path, marker, and test gates.
- [ ] Merge only after fresh verification evidence.