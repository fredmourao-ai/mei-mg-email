# AUDIT_UI_EVIDENCE_INTEGRITY_V2 — Real-UI proof, remediation and durable continuation

**Binding policies:** EXTREME_AUDIT_UI_FIRST_HARD_GATE_V1 and AUDIT_UI_EVIDENCE_INTEGRITY_V2.

This policy supplements the V5 absolute gate. It is mandatory for GPT, Gemini, Claude, Codex, subagents, controllers and reviewers of governed repositories whenever a UI exists. A textual assertion that UI testing happened is NOT evidence.

## Observable runtime contract

1. Inventory the published UI with a graphical browser or the authorized graphical desktop, exact account profile and exact SHA/release/environment under certification. Preserve valid sessions and obtain runtime lease/fencing before mutation.
2. Enumerate all material routes, menus, controls, permissions, tenants, state transitions, failure states and historical cases. Reconcile runtime UI inventory with code/routes, incidents and feature flags. Absence of UI must be proven by independent negative inventory sources, never just browser.required=false.
3. The auditor executes each applicable journey via actual navigation, clicks, input/selection and visible submission; observes results, reloads, revisits and verifies persistence. Network/API/SQL independently reconcile effects but do not substitute for UI.
4. Capture a graphical Playwright trace with before/after interactions plus PNG or video, or actual desktop video and recorder event log. A screenshot, a flag or headless-only test never certifies UI.
5. For stateful operational systems, enumerate every material case with a SHA-256 pseudonymous ID and attach actual UI interaction evidence for each. API-only case lists are not UI coverage.
6. Every found material defect requires RED reproduction, root cause, fix SHA, GREEN test, regression, equivalent-failure search, fresh UI reauditing and independent review. Never reclassify an active defect as harmless to obtain APTO.
7. A distinct reviewer must rerun journeys in a separate session, not just sign the primary report. After deployment, repeat UI journeys against the published release and record activation time.
8. New AUDIT_ESCAPE invalidates prior APTO within the affected scope; correct the product defect, detection gap and related cases, then recertify with independent reauditing.

## Mandatory machine-readable proof

Use the official command:

    python3 scripts/certify-audit-manifest.py manifest.json --evidence-root /trusted/evidence

The CLI must read every referenced file from disk, reject symlink/traversal/empty paths, recompute SHA-256, verify SHA/release/environment, decode execution evidence, and reject malformed Playwright traces or media. Never pass invented logs as genuine runtime evidence; authorized browser/desktop recorders must generate captures.

Artifact kinds:
- ui_inventory: JSON AUDIT_UI_INVENTORY_V2, with ui_surface_present, routes with control_ids, material_journey_ids, stateful_cases and inspection_sources.
- ui_execution: JSON AUDIT_UI_EXECUTION_V2 for each journey/role, with auditor, session_id, journey_id, UTC time, release identity, media_refs, interacted_control_ids, optional hashed case IDs, and ordered events navigate, interact, assert_postcondition, reload, revisit, assert_persistence.
- playwright_trace: unmodified ZIP from the real browser run, with before/after API interaction events.
- screenshot: PNG; video: MP4 recording of the graphical session.
- case_inventory: JSON AUDIT_CASE_INVENTORY_V2, enumerating pseudonymous case_sha256_ids for all material cases.

The manifest links browser.ui_inventory_ref, each UI journey's execution_ref and contradictory_execution_ref, and each post_deploy_execution_ref for deploys. case_coverage.inventory_ref and case_coverage.required=true are mandatory whenever the UI inventory reports stateful cases. Reconcile counts and actually operated controls. An independent reviewer needs a different auditor and session. deploy.activated_at_utc must precede fresh post-deploy capture. Negative no-UI inventory must include two independent inspection sources.

The manifest also includes findings.discovered_total and remediation.fixed_findings. Each discovered finding requires root_cause, fix_sha, and four distinct verified files red_ref, green_ref, regression_ref and reaudit_ref.

Hash and file structure alone do NOT prove the identity of the operator: never overclaim cryptographic attestation. Preserve source browser-bridge and Playwright audit IDs, and independently corroborate high-risk actions. A protected, independently attested recorder is the next enforcement layer; never accept agent-authored imitation artifacts.

## Controller: no abandonment of incomplete audits

An extreme audit is a durable task, not a one-turn report. Register it in the canonical continuity controller with the exact corporate account/session and conversation ID when available, original objective and provenance. Follow the documented scripts/agent_task_state.py start, progress, ready, complete and terminal states.

Maintain RUNNING with a specific next_action whenever official certifier returns NAO_APTO, a UI/CI/deploy step remains incomplete, an authorized channel fails recoverably, or a conversation turn is interrupted. The deterministic watchdog can request resume using bounded retries, deduplication, leases/fencing and zero-paid-provider background policy. Never start infinite paid AI loops, duplicate browser writers or untracked local-only tasks.

READY_TO_COMPLETE and complete require an actual AUDIT_VERDICT=APTO from the file-verifying CLI for the same release and scope, including postdeploy UI and independent reviewer if applicable. A PR, merge, green unit tests, API health, screenshot or interim report cannot terminate an audit. Call agent_task_state.py terminal --task ID before claiming conclusion; nonzero status means the task remains incomplete.

External outages, CAPTCHA, absent authorization or irreversible operations require the existing BLOCKED_EXTERNAL protocol after documented safe alternatives. This is not success. Preserve checkpoint/evidence/next action; do not bypass MFA, approvals or expose secrets.

## Enforcement

- scripts/certify-audit-manifest.py invokes scripts/audit_ui_evidence_gate.py unconditionally in the official CLI. Missing files, import failures, bad integrity or missing UI proofs force AUDIT_VERDICT=NAO_APTO.
- Governance compiles the gate and executes tests/test_audit_ui_evidence_gate.py including intentionally invalid artifacts (RED) and a complete fixture (GREEN).
- New false-negative auditor escapes must generate a regression test and propagate to every governed repository.
- APTO is a computed, verified scope/release verdict, never an agent opinion.

Required marker: AUDIT_UI_EVIDENCE_INTEGRITY_V2.
