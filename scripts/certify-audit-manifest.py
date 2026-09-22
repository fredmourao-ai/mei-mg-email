#!/usr/bin/env python3
"""Absolute fail-closed certifier for Extreme Audit V5 evidence manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SCHEMA = "AUDIT_CERTIFICATION_MANIFEST_V1"
PROJECT_REQUIREMENTS_SCHEMA = "AUDIT_PROJECT_REQUIREMENTS_V1"
POLICY_VERSION = "2026-09-21-absolute-v5"
SHA40 = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")

REQUIRED_REPOSITORIES = [
    "Vivaliz-site/site-shopvivaliz",
    "Vivaliz-site/-shopvivaliz-pipeline",
    "Vivaliz-site/amazon-returns-safet",
    "Vivaliz-site/ml-pricing-api",
    "Vivaliz-site/mercadolivre-returns-recovery",
    "Vivaliz-site/shopvivaliz-m365",
    "Vivaliz-site/buscador",
    "fredmourao-ai/mei-mg-email",
    "fredmourao-ai/solange-rolla-consultorio",
    "fredmourao-ai/solange-rolla",
]

REQUIRED_NONEMPTY = [
    "identity.audit_id",
    "identity.repository",
    "identity.commit_sha",
    "identity.build_digest",
    "identity.release",
    "identity.environment",
    "identity.timestamp_utc",
    "identity.certified_scope",
    "identity.primary_auditor",
    "fingerprint.schema_version",
    "fingerprint.config_fingerprint",
    "fingerprint.feature_flags_fingerprint",
    "project_invariants.requirements_fingerprint",
]

REQUIRED_TRUE = [
    "identity.scope_is_explicit",
    "fingerprint.complete",
    "fingerprint.material_change_invalidation_checked",
    "evidence.fresh",
    "evidence.same_sha_build",
    "evidence.same_environment",
    "evidence.provenance_complete",
    "evidence.artifact_hashes_verified",
    "coverage.inventory_complete",
    "coverage.all_material_journeys_enumerated",
    "coverage.all_material_states_enumerated",
    "coverage.all_material_controls_classified",
    "coverage.negative_paths_complete",
    "coverage.boundaries_complete",
    "coverage.environment_matrix_complete",
    "taxonomy.complete",
    "taxonomy.no_material_not_validated",
    "data.reconciliation_complete",
    "data.orphan_scan_complete",
    "data.no_unexplained_difference",
    "runtime.no_unresolved_5xx",
    "runtime.no_unresolved_pageerror",
    "runtime.no_unresolved_requestfailed",
    "runtime.no_unresolved_console_error",
    "runtime.no_silent_failure",
    "external_effects.reconciled",
    "async_runtime.observed",
    "async_runtime.settlement_complete",
    "observability.proven",
    "recovery.proven_or_not_material",
    "architecture.complete",
    "legacy_duplication.checked",
    "baseline.acceptable_or_not_material",
    "authorization.matrix_complete_or_not_material",
    "clean_room.completed_or_not_material",
    "chaos_recovery.completed_or_not_material",
    "visual.interaction_regression_complete_or_not_material",
    "auth_discovery.complete_or_not_material",
    "project_invariants.complete",
    "tests.no_flaky_false_green",
    "tests.self_test_complete_when_applicable",
    "tests.certifier_mutation_self_test_passed",
    "unknown_unknowns.completed",
    "audit_escape.historical_classes_reaudited",
    "audit_escape.regression_tests_added_for_new_escapes",
    "audit_escape.certification_invalidation_checked",
    "contradictory_review.completed",
    "contradictory_review.reviewer_distinct",
    "contradictory_review.no_open_findings",
    "remediation.loop_completed",
    "remediation.no_gate_weakening",
    "remediation.no_executable_issue_deferred",
    "certification.scope_label_exact",
    "certification.no_self_attestation",
]

REQUIRED_ZERO = [
    "findings.p0",
    "findings.p1",
    "findings.p2",
    "findings.p3",
    "findings.open_defects_total",
    "findings.improvement_required_open",
    "findings.preexisting_active_defects",
    "audit_escape.pending_count",
    "remediation.open_blockers",
    "remediation.executable_blockers",
    "evidence.debt_count",
    "coverage.not_validated_count",
    "coverage.unmapped_surfaces",
    "coverage.untested_material_controls",
    "coverage.uncovered_material_journeys",
    "data.unexplained_difference_count",
    "runtime.unresolved_error_count",
    "project_invariants.failed_required_count",
    "project_invariants.missing_required_count",
]

DEPLOY_REQUIRED_TRUE = [
    "deploy.same_sha_active",
    "deploy.post_deploy_validation_complete",
    "deploy.post_deploy_browser_e2e_complete_or_not_material",
    "deploy.post_deploy_async_observation_complete",
    "deploy.release_fingerprint_matches",
]

BROWSER_REQUIRED_TRUE = [
    "browser.real_browser",
    "browser.graphical_session",
    "browser.agent_executed",
    "browser.same_release",
    "browser.full_user_path",
    "browser.reload_revisit",
    "browser.persistence_checked",
    "browser.console_checked",
    "browser.network_checked",
    "browser.visual_evidence",
    "browser.no_user_delegation",
    "browser.not_headless_only",
    "browser.clean_context_exercised_when_material",
    "browser.mobile_desktop_exercised_when_material",
    "browser.navigation_variants_exercised_when_material",
]

CLEAN_ROOM_REQUIRED_TRUE = [
    "clean_room.clean_storage",
    "clean_room.cold_cache",
    "clean_room.auth_states_exercised",
    "clean_room.cache_service_worker_checked",
    "clean_room.navigation_reality_checked",
    "clean_room.concurrency_checked",
    "clean_room.partial_failure_recovery_checked",
    "clean_room.cold_start_checked",
    "clean_room.temporal_edges_checked",
    "clean_room.soak_leak_checked_or_not_material",
]

CHAOS_REQUIRED_TRUE = [
    "chaos_recovery.timeout_checked",
    "chaos_recovery.rate_limit_checked",
    "chaos_recovery.server_error_checked",
    "chaos_recovery.partial_failure_checked",
    "chaos_recovery.retry_idempotency_checked",
    "chaos_recovery.alert_recovery_checked",
]

AUTH_DISCOVERY_REQUIRED_TRUE = [
    "auth_discovery.all_repositories_scanned",
    "auth_discovery.repo_secret_references_checked",
    "auth_discovery.runtime_secret_stores_checked",
    "auth_discovery.canonical_profiles_checked",
    "auth_discovery.oauth_cli_sessions_checked",
    "auth_discovery.alternative_transports_checked",
    "auth_discovery.safe_probe_attempted",
    "auth_discovery.exhausted",
    "auth_discovery.no_secret_exposure",
]

AUTH_BLOCKER_CATEGORIES = {"AUTH", "LOGIN", "CREDENTIAL", "OAUTH", "SESSION"}


def get_path(data: dict, dotted: str):
    value = data
    for part in dotted.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def add_bool_failures(data: dict, paths: list[str], failures: list[str]) -> None:
    for path in paths:
        if get_path(data, path) is not True:
            failures.append(f"{path} must be true")


def add_zero_failures(data: dict, paths: list[str], failures: list[str]) -> None:
    for path in paths:
        value = get_path(data, path)
        if type(value) is not int or value != 0:
            failures.append(f"{path} must be integer 0")


def validate_identity(data: dict, failures: list[str]) -> None:
    if data.get("policy_version") != POLICY_VERSION:
        failures.append(f"policy_version must be {POLICY_VERSION}")

    for path in REQUIRED_NONEMPTY:
        value = get_path(data, path)
        if not isinstance(value, str) or not value.strip():
            failures.append(f"{path} must be non-empty")

    sha = get_path(data, "identity.commit_sha")
    if isinstance(sha, str) and sha and not SHA40.match(sha):
        failures.append("identity.commit_sha must be a full 40-char Git SHA")

    repository = get_path(data, "identity.repository")
    if repository not in REQUIRED_REPOSITORIES:
        failures.append("identity.repository is not in the governed repository set")

    primary = get_path(data, "identity.primary_auditor")
    reviewer = get_path(data, "contradictory_review.reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        failures.append("contradictory_review.reviewer must be non-empty")
    elif isinstance(primary, str) and reviewer.strip() == primary.strip():
        failures.append("contradictory reviewer must differ from primary auditor")


def validate_evidence(data: dict, failures: list[str]) -> set[str]:
    evidence = data.get("evidence")
    if not isinstance(evidence, dict):
        failures.append("evidence must be an object")
        return set()

    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        failures.append("evidence.artifacts must contain at least one hashed artifact")
        return set()

    ids: set[str] = set()
    for index, artifact in enumerate(artifacts):
        prefix = f"evidence.artifacts[{index}]"
        if not isinstance(artifact, dict):
            failures.append(f"{prefix} must be an object")
            continue
        aid = artifact.get("id")
        if not isinstance(aid, str) or not aid.strip():
            failures.append(f"{prefix}.id must be non-empty")
        elif aid in ids:
            failures.append(f"{prefix}.id duplicate: {aid}")
        else:
            ids.add(aid)
        for field in ["path", "kind", "sha_release_environment"]:
            value = artifact.get(field)
            if not isinstance(value, str) or not value.strip():
                failures.append(f"{prefix}.{field} must be non-empty")
        digest = artifact.get("sha256")
        if not isinstance(digest, str) or not SHA256.match(digest):
            failures.append(f"{prefix}.sha256 must be a 64-char SHA-256 hex digest")
    return ids


def validate_journeys(data: dict, artifact_ids: set[str], failures: list[str]) -> set[str]:
    journeys = data.get("journeys")
    if not isinstance(journeys, list) or not journeys:
        failures.append("journeys must contain at least one enumerated journey")
        return set()

    seen: set[str] = set()
    for index, journey in enumerate(journeys):
        prefix = f"journeys[{index}]"
        if not isinstance(journey, dict):
            failures.append(f"{prefix} must be an object")
            continue

        jid = journey.get("id")
        if not isinstance(jid, str) or not jid.strip():
            failures.append(f"{prefix}.id must be non-empty")
        elif jid in seen:
            failures.append(f"{prefix}.id duplicate: {jid}")
        else:
            seen.add(jid)

        if journey.get("material") is not True:
            failures.append(f"{prefix}.material must be true for certification journeys")
        if journey.get("status") != "COMPROVADO":
            failures.append(f"{prefix}.status must be COMPROVADO")
        if journey.get("contradictory_reaudit") is not True:
            failures.append(f"{prefix}.contradictory_reaudit must be true")

        refs = journey.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            failures.append(f"{prefix}.evidence_refs must contain evidence artifact ids")
        else:
            for ref in refs:
                if not isinstance(ref, str) or ref not in artifact_ids:
                    failures.append(f"{prefix}.evidence_refs contains unknown artifact id: {ref!r}")

        if journey.get("ui") is True:
            browser = journey.get("browser_e2e")
            if not isinstance(browser, dict):
                failures.append(f"{prefix}.browser_e2e required for UI journey")
                continue
            for field in [
                "real_browser",
                "graphical_session",
                "agent_executed",
                "same_release",
                "full_user_path",
                "reload_revisit",
                "persistence_checked",
                "console_checked",
                "network_checked",
                "visual_evidence",
                "no_user_delegation",
                "not_headless_only",
            ]:
                if browser.get(field) is not True:
                    failures.append(f"{prefix}.browser_e2e.{field} must be true")
    return seen


def validate_auth_discovery(data: dict, failures: list[str]) -> None:
    auth = data.get("auth_discovery")
    if not isinstance(auth, dict):
        failures.append("auth_discovery must be an object")
        return

    required = auth.get("required")
    if required not in (True, False):
        failures.append("auth_discovery.required must be boolean")
        return
    if not required:
        return

    add_bool_failures(data, AUTH_DISCOVERY_REQUIRED_TRUE, failures)

    expected = auth.get("repositories_expected")
    scanned = auth.get("repositories_scanned")
    if expected != REQUIRED_REPOSITORIES:
        failures.append("auth_discovery.repositories_expected must exactly match governed repositories")
    if not isinstance(scanned, list) or set(scanned) != set(REQUIRED_REPOSITORIES) or len(scanned) != len(REQUIRED_REPOSITORIES):
        failures.append("auth_discovery.repositories_scanned must cover every governed repository exactly once")
    if auth.get("repositories_expected_count") != len(REQUIRED_REPOSITORIES):
        failures.append("auth_discovery.repositories_expected_count mismatch")
    if auth.get("repositories_scanned_count") != len(REQUIRED_REPOSITORIES):
        failures.append("auth_discovery.repositories_scanned_count mismatch")


def load_project_requirements(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    return data, hashlib.sha256(raw).hexdigest()


def validate_project_requirements(
    data: dict,
    requirements: dict | None,
    requirements_fingerprint: str | None,
    artifact_ids: set[str],
    journey_ids: set[str],
    failures: list[str],
) -> None:
    if not isinstance(requirements, dict):
        failures.append("project requirements file is required")
        return
    if requirements.get("schema") != PROJECT_REQUIREMENTS_SCHEMA:
        failures.append(f"project requirements schema must be {PROJECT_REQUIREMENTS_SCHEMA}")

    repository = get_path(data, "identity.repository")
    if requirements.get("project") != repository:
        failures.append("project requirements project must match identity.repository")

    if requirements_fingerprint is None or get_path(data, "project_invariants.requirements_fingerprint") != requirements_fingerprint:
        failures.append("project_invariants.requirements_fingerprint does not match requirements file")

    required = requirements.get("required_invariants")
    if not isinstance(required, list):
        failures.append("project requirements required_invariants must be a list")
        return

    project_inv = data.get("project_invariants")
    if not isinstance(project_inv, dict):
        failures.append("project_invariants must be an object")
        return
    results = project_inv.get("results")
    if not isinstance(results, list):
        failures.append("project_invariants.results must be a list")
        return

    by_id: dict[str, dict] = {}
    for result in results:
        if isinstance(result, dict) and isinstance(result.get("id"), str):
            by_id[result["id"]] = result

    for req in required:
        if not isinstance(req, dict) or not isinstance(req.get("id"), str):
            failures.append("each project requirement must have a string id")
            continue
        rid = req["id"]
        result = by_id.get(rid)
        if not isinstance(result, dict):
            failures.append(f"missing project invariant result: {rid}")
            continue
        if result.get("status") != "COMPROVADO":
            failures.append(f"project invariant {rid} must be COMPROVADO")

        refs = result.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            failures.append(f"project invariant {rid} requires evidence_refs")
        else:
            for ref in refs:
                if not isinstance(ref, str) or ref not in artifact_ids:
                    failures.append(f"project invariant {rid} references unknown artifact: {ref!r}")

        rtype = req.get("type", "evidence")
        if rtype == "journey_ids":
            for jid in req.get("required_journey_ids", []):
                if jid not in journey_ids:
                    failures.append(f"project invariant {rid} missing required journey: {jid}")
        elif rtype == "provider_chat":
            details = result.get("details")
            chat = details.get("provider_chat") if isinstance(details, dict) else None
            if not isinstance(chat, dict):
                failures.append(f"project invariant {rid} requires details.provider_chat")
                continue
            for flag in ["same_cycle", "ui_visible", "cycle_finished_ok", "health_verified"]:
                if chat.get(flag) is not True:
                    failures.append(f"project invariant {rid} provider_chat.{flag} must be true")
            if req.get("consensus_required") is True and chat.get("consensus_emitted") is not True:
                failures.append(f"project invariant {rid} consensus must be emitted")
            provider_results = chat.get("providers")
            if not isinstance(provider_results, dict):
                failures.append(f"project invariant {rid} provider results missing")
                continue
            phases = req.get("phases", [])
            for provider in req.get("providers", []):
                state = provider_results.get(provider)
                if not isinstance(state, dict):
                    failures.append(f"project invariant {rid} provider missing: {provider}")
                    continue
                for flag in ["active", "responded", "nonempty_response", "visible"]:
                    if state.get(flag) is not True:
                        failures.append(f"project invariant {rid} {provider}.{flag} must be true")
                phase_results = state.get("phases")
                if phases:
                    if not isinstance(phase_results, dict):
                        failures.append(f"project invariant {rid} {provider}.phases missing")
                    else:
                        for phase in phases:
                            if phase_results.get(phase) is not True:
                                failures.append(f"project invariant {rid} {provider}.phases.{phase} must be true")
        elif rtype != "evidence":
            failures.append(f"unsupported project invariant type: {rtype}")


def certify(
    data: dict,
    project_requirements: dict | None = None,
    project_requirements_fingerprint: str | None = None,
) -> tuple[str, list[str]]:
    failures: list[str] = []

    if data.get("schema") != SCHEMA:
        failures.append(f"schema must be {SCHEMA}")

    validate_identity(data, failures)
    add_bool_failures(data, REQUIRED_TRUE, failures)
    add_zero_failures(data, REQUIRED_ZERO, failures)

    artifact_ids = validate_evidence(data, failures)
    journey_ids = validate_journeys(data, artifact_ids, failures)
    validate_auth_discovery(data, failures)
    validate_project_requirements(
        data,
        project_requirements,
        project_requirements_fingerprint,
        artifact_ids,
        journey_ids,
        failures,
    )

    browser_required = get_path(data, "browser.required")
    if browser_required not in (True, False):
        failures.append("browser.required must be boolean")
    elif browser_required:
        add_bool_failures(data, BROWSER_REQUIRED_TRUE, failures)

    deploy_required = get_path(data, "deploy.required")
    if deploy_required not in (True, False):
        failures.append("deploy.required must be boolean")
    elif deploy_required:
        add_bool_failures(data, DEPLOY_REQUIRED_TRUE, failures)

    clean_required = get_path(data, "clean_room.required")
    if clean_required not in (True, False):
        failures.append("clean_room.required must be boolean")
    elif clean_required:
        add_bool_failures(data, CLEAN_ROOM_REQUIRED_TRUE, failures)

    chaos_required = get_path(data, "chaos_recovery.required")
    if chaos_required not in (True, False):
        failures.append("chaos_recovery.required must be boolean")
    elif chaos_required:
        add_bool_failures(data, CHAOS_REQUIRED_TRUE, failures)

    if "verdict" in data or "apto" in data:
        failures.append("manifest must not self-attest a verdict; verdict is derived by certifier")

    external = get_path(data, "remediation.blocked_external_count")
    external_proven = get_path(data, "remediation.blocked_external_proven")
    executable = get_path(data, "remediation.executable_blockers")
    category = str(get_path(data, "remediation.blocked_external_category") or "").upper()

    if type(external) is not int or external < 0:
        failures.append("remediation.blocked_external_count must be a non-negative integer")
        external = 0

    if external > 0:
        if external_proven is not True:
            failures.append("remediation.blocked_external_proven must be true for BLOCKED_EXTERNAL")
        if executable != 0:
            failures.append("cannot claim BLOCKED_EXTERNAL while executable blockers remain")
        if category in AUTH_BLOCKER_CATEGORIES and get_path(data, "auth_discovery.required") is not True:
            failures.append("auth/login BLOCKED_EXTERNAL requires exhaustive auth discovery")
        if failures:
            return "NAO_APTO", failures
        return "BLOCKED_EXTERNAL", ["external blocker remains and is fully evidenced"]

    return ("APTO" if not failures else "NAO_APTO"), failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument(
        "--project-requirements",
        type=Path,
        default=Path("docs/quality/AUDIT_PROJECT_REQUIREMENTS.json"),
    )
    args = parser.parse_args()

    try:
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"AUDIT_CERTIFIER_ERROR={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    try:
        requirements, requirements_fingerprint = load_project_requirements(args.project_requirements)
    except Exception as exc:
        print(f"AUDIT_PROJECT_REQUIREMENTS_ERROR={type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    verdict, failures = certify(data, requirements, requirements_fingerprint)
    report = {
        "schema": SCHEMA,
        "policy_version": POLICY_VERSION,
        "verdict": verdict,
        "failures": failures,
    }

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"AUDIT_POLICY_VERSION={POLICY_VERSION}")
    print(f"AUDIT_VERDICT={verdict}")
    for item in failures:
        print(f"AUDIT_BLOCKER={item}")

    return 0 if verdict == "APTO" else (2 if verdict == "BLOCKED_EXTERNAL" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
