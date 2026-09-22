#!/usr/bin/env python3
"""Fail-closed self-test for the ShopVivaliz Extreme Audit V5 absolute governance."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_VERSION = "2026-09-21-absolute-v5"
PROJECT_REQUIREMENTS_SCHEMA = "AUDIT_PROJECT_REQUIREMENTS_V1"

REQUIRED_MARKERS = {
    "AUDIT_POLICY.md": [
        POLICY_VERSION,
        "AUDIT_UNIVERSAL_COVERAGE_V1",
        "AUDIT_SELF_TEST_V1",
        "ARCHITECTURE_DEPLOY_AUDIT_V1",
        "AUDIT_ABSOLUTE_GATE_V1",
        "AUDIT_AUTH_CREDENTIAL_DISCOVERY_V1",
        "AUDIT_MERGE_ENFORCEMENT_V1",
        "AUDIT_PROJECT_REQUIREMENTS_V1",
    ],
    "docs/quality/EXTREME_AUDIT_PROTOCOL.md": [
        "MAPEAR → IMPACTAR",
        "Caça a unknown unknowns",
        "AUDIT_BROWSER_E2E_REAL_V1",
        "AUDIT_APTO_REMEDIATION_LOOP_V1",
        "AUDIT_MERGE_ENFORCEMENT_V1",
    ],
    "docs/quality/AUDIT_RUNTIME_PARITY_V1.md": [
        "Falha silenciosa",
        "evidência crítica stale",
        "Gate de browser E2E absoluto",
    ],
    "docs/quality/AUDIT_UNIVERSAL_COVERAGE_V1.md": [
        "AUDIT_ERROR_TAXONOMY_V1",
        "AUDIT_UNKNOWN_UNKNOWNS_V1",
        "AUDIT_JOURNEY_INVENTORY_V1",
        "AUDIT_BROWSER_E2E_REAL_V1",
        "AUDIT_CLEAN_ROOM_REALITY_V1",
        "AUDIT_ESCAPE_INVALIDATION_V1",
        "AUDIT_ABSOLUTE_GATE_V1",
    ],
    "docs/quality/ARCHITECTURE_DEPLOY_AUDIT_V1.md": [
        "RUNNER_ISOLATION_V1",
        "BUILD_ONCE_PROMOTE_V1",
        "WORKFLOW_SPRAWL_BUDGET_V1",
        "CROSS_REPO_CONTRACTS_V1",
        "DEPLOYMENT_PERFORMANCE_BUDGET_V1",
        "ARCHITECTURE_UNKNOWN_UNKNOWNS_V1",
    ],
    "docs/quality/AUDIT_SELF_TEST_V1.md": [
        "Teste de sensibilidade",
        "Mutation testing da governança",
        "Self-test do certifier absoluto",
    ],
    "docs/quality/AUDIT_EVIDENCE_MANIFEST_TEMPLATE.md": [
        "Fingerprint do ambiente",
        "Inventário de superfície e jornadas",
        "Browser E2E real",
        "Integridade de evidência",
        "Veredito determinístico",
    ],
    "docs/quality/AUDIT_BROWSER_E2E_REAL_V1.md": [
        "E2E real obrigatório",
        "Responsabilidade do agente",
        "Gate fatal",
    ],
    "docs/quality/AUDIT_APTO_REMEDIATION_LOOP_V1.md": [
        "Remediação autônoma até APTO",
        "Loop obrigatório",
        "BLOCKED_EXTERNAL",
    ],
    "docs/quality/AUDIT_JOURNEY_INVENTORY_V1.md": [
        "Inventário exaustivo",
        "UNMAPPED_SURFACE",
        "untested_material_controls",
    ],
    "docs/quality/AUDIT_ESCAPE_INVALIDATION_V1.md": [
        "invalida certificação",
        "INVALIDATED_BY_AUDIT_ESCAPE",
        "Aprendizado obrigatório",
    ],
    "docs/quality/AUDIT_HARDENING_MAX_V1.md": [
        "CONFIG_RELEASE_FINGERPRINT_V1",
        "DUAL_ORACLE_RECONCILIATION_V1",
        "CERTIFICATION_INVALIDATION_V1",
        "EVIDENCE_INTEGRITY_V1",
    ],
    "docs/quality/AUDIT_CLEAN_ROOM_REALITY_V1.md": [
        "CLEAN_ROOM_SESSION_V1",
        "CONCURRENCY_REALITY_V1",
        "PARTIAL_FAILURE_RECOVERY_V1",
        "COLD_START_RUNTIME_V1",
    ],
    "docs/quality/AUDIT_ABSOLUTE_GATE_V1.md": [
        "Certificação fail-closed máxima",
        "Veredito calculado",
        "Invariantes locais obrigatórios",
        "Auth/login não vira bloqueio cedo",
    ],
    "docs/quality/AUDIT_AUTH_CREDENTIAL_DISCOVERY_V1.md": [
        "Descoberta exaustiva antes de bloquear por login",
        "todos os repositórios governados",
        "no_secret_exposure=true",
    ],
    "docs/quality/AUDIT_PROJECT_REQUIREMENTS_V1.md": [
        "Invariantes locais machine-readable",
        "provider_chat",
        "Requisito local ausente",
    ],
    "docs/quality/AUDIT_MERGE_ENFORCEMENT_V1.md": [
        "Enforcement de merge",
        "Governance bridge obrigatório",
        "Main Guard",
        "ENFORCEMENT_PLATFORM_LIMITATION",
    ],
    "scripts/absolute-audit-governance-validate.sh": [
        "ABSOLUTE_AUDIT_GOVERNANCE_BRIDGE=PASS",
        "test_certify_audit_manifest.py",
        "validate-global-audit-policy.py",
    ],
    "scripts/validate-main-merge-provenance.py": [
        "AUDIT_MAIN_PROVENANCE=",
        "no associated pull request",
        "merged pull request",
    ],
    ".github/workflows/absolute-audit-main-guard.yml": [
        "Absolute Audit Main Guard",
        "Validate Absolute Audit V5 on published main",
        "Verify merged-PR provenance",
    ],
    "docs/quality/AUDIT_CERTIFICATION_MANIFEST_TEMPLATE.json": [
        "AUDIT_CERTIFICATION_MANIFEST_V1",
        "unmapped_surfaces",
        "project_invariants",
        "auth_discovery",
    ],
    "scripts/certify-audit-manifest.py": [
        POLICY_VERSION,
        "REQUIRED_REPOSITORIES",
        "AUTH_DISCOVERY_REQUIRED_TRUE",
        "AUDIT_VERDICT=",
        "provider_chat",
    ],
    "AGENTS.override.md": [
        "AUDIT_ABSOLUTE_GATE_V1.md",
        "AUDIT_BROWSER_E2E_REAL_V1.md",
        "certify-audit-manifest.py",
        "AUDIT_MERGE_ENFORCEMENT_V1.md",
        "absolute-audit-governance-validate.sh",
    ],
    ".github/workflows/absolute-audit-governance.yml": [
        "Self-test absolute certifier",
        "Self-test audit governance",
        "Verify global policy parity",
    ],
}

REQUIRED_ENTRYPOINT_MARKERS = {
    "AGENTS.md": [
        "AUDIT_ABSOLUTE_GATE_V1.md",
        "AUDIT_BROWSER_E2E_REAL_V1.md",
        "AUDIT_APTO_REMEDIATION_LOOP_V1.md",
        "AUDIT_MERGE_ENFORCEMENT_V1",
    ],
    "CLAUDE.md": [
        "AUDIT_ABSOLUTE_GATE_V1.md",
        "AUDIT_BROWSER_E2E_REAL_V1.md",
    ],
    "scripts/repository-governance-validate.sh": [
        "absolute-audit-governance-validate.sh",
    ],
    ".github/workflows/repository-governance.yml": [
        "repository-governance-validate.sh",
    ],
}


@dataclass(frozen=True)
class AuditState:
    p0: int = 0
    p1: int = 0
    p2: int = 0
    p3: int = 0
    open_defects: int = 0
    improvement_required: int = 0
    critical_not_validated: bool = False
    audit_escape_pending: bool = False
    runtime_error_unresolved: bool = False
    published_evidence_missing: bool = False
    stale_evidence: bool = False
    negative_or_boundary_gap: bool = False
    reconciliation_gap: bool = False
    critical_orphan: bool = False
    silent_failure: bool = False
    flaky_or_false_green_evidence: bool = False
    taxonomy_material_not_validated: bool = False
    unknown_unknowns_not_run: bool = False
    effect_unreconciled: bool = False
    observability_unproven: bool = False
    rollback_required_unproven: bool = False
    legacy_duplication_unresolved: bool = False
    baseline_regression_uninvestigated: bool = False
    pending_without_owner_or_deadline: bool = False
    self_test_required_and_failed: bool = False
    architecture_material_not_validated: bool = False
    deployment_provenance_missing: bool = False
    browser_e2e_missing: bool = False
    unmapped_surface: bool = False
    untested_material_control: bool = False
    evidence_debt: bool = False
    contradictory_review_missing: bool = False
    remediation_blocker: bool = False
    clean_room_gap: bool = False
    auth_discovery_gap: bool = False
    project_invariant_gap: bool = False
    merge_enforcement_gap: bool = False


def allows_apto(state: AuditState) -> bool:
    return not any(
        [
            state.p0 > 0,
            state.p1 > 0,
            state.p2 > 0,
            state.p3 > 0,
            state.open_defects > 0,
            state.improvement_required > 0,
            state.critical_not_validated,
            state.audit_escape_pending,
            state.runtime_error_unresolved,
            state.published_evidence_missing,
            state.stale_evidence,
            state.negative_or_boundary_gap,
            state.reconciliation_gap,
            state.critical_orphan,
            state.silent_failure,
            state.flaky_or_false_green_evidence,
            state.taxonomy_material_not_validated,
            state.unknown_unknowns_not_run,
            state.effect_unreconciled,
            state.observability_unproven,
            state.rollback_required_unproven,
            state.legacy_duplication_unresolved,
            state.baseline_regression_uninvestigated,
            state.pending_without_owner_or_deadline,
            state.self_test_required_and_failed,
            state.architecture_material_not_validated,
            state.deployment_provenance_missing,
            state.browser_e2e_missing,
            state.unmapped_surface,
            state.untested_material_control,
            state.evidence_debt,
            state.contradictory_review_missing,
            state.remediation_blocker,
            state.clean_room_gap,
            state.auth_discovery_gap,
            state.project_invariant_gap,
            state.merge_enforcement_gap,
        ]
    )


def validate_project_requirements_file() -> dict[str, object]:
    relative = "docs/quality/AUDIT_PROJECT_REQUIREMENTS.json"
    path = ROOT / relative
    if not path.is_file():
        return {"file": relative, "ok": False, "missing": ["<file missing>"]}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"file": relative, "ok": False, "missing": [f"invalid json: {type(exc).__name__}"]}

    missing: list[str] = []
    if data.get("schema") != PROJECT_REQUIREMENTS_SCHEMA:
        missing.append(PROJECT_REQUIREMENTS_SCHEMA)
    if data.get("policy_version") != POLICY_VERSION:
        missing.append(POLICY_VERSION)

    project = data.get("project")
    if not isinstance(project, str) or not project.strip():
        missing.append("project")
    current_repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if current_repo and project != current_repo:
        missing.append(f"project must equal {current_repo}")

    invariants = data.get("required_invariants")
    if not isinstance(invariants, list) or not invariants:
        missing.append("required_invariants non-empty")

    return {"file": relative, "ok": not missing, "missing": missing}


def validate_markers() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []

    for relative, markers in REQUIRED_MARKERS.items():
        path = ROOT / relative
        if not path.is_file():
            results.append({"file": relative, "ok": False, "missing": ["<file missing>"]})
            continue
        content = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in content]
        results.append({"file": relative, "ok": not missing, "missing": missing})

    for relative, markers in REQUIRED_ENTRYPOINT_MARKERS.items():
        path = ROOT / relative
        if not path.is_file():
            results.append({"file": relative, "ok": False, "missing": ["<file missing>"]})
            continue
        content = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in content]
        results.append({"file": relative, "ok": not missing, "missing": missing})

    results.append(validate_project_requirements_file())

    central = ROOT / "REGRAS-AGENTES-CENTRALIZADAS.md"
    if central.is_file():
        content = central.read_text(encoding="utf-8")
        marker = "AUDITORIA_EXTREMA_ABSOLUTA_V5"
        results.append(
            {
                "file": "REGRAS-AGENTES-CENTRALIZADAS.md",
                "ok": marker in content,
                "missing": [] if marker in content else [marker],
            }
        )
    return results


def self_test_gate() -> list[dict[str, object]]:
    baseline = AuditState()
    results: list[dict[str, object]] = [
        {"scenario": "clean_baseline", "expected_apto": True, "actual_apto": allows_apto(baseline)}
    ]

    blockers = {
        "p0": {"p0": 1},
        "p1": {"p1": 1},
        "p2": {"p2": 1},
        "p3": {"p3": 1},
        "open_defects": {"open_defects": 1},
        "improvement_required": {"improvement_required": 1},
        "critical_not_validated": {"critical_not_validated": True},
        "audit_escape_pending": {"audit_escape_pending": True},
        "runtime_error_unresolved": {"runtime_error_unresolved": True},
        "published_evidence_missing": {"published_evidence_missing": True},
        "stale_evidence": {"stale_evidence": True},
        "negative_or_boundary_gap": {"negative_or_boundary_gap": True},
        "reconciliation_gap": {"reconciliation_gap": True},
        "critical_orphan": {"critical_orphan": True},
        "silent_failure": {"silent_failure": True},
        "flaky_or_false_green_evidence": {"flaky_or_false_green_evidence": True},
        "taxonomy_material_not_validated": {"taxonomy_material_not_validated": True},
        "unknown_unknowns_not_run": {"unknown_unknowns_not_run": True},
        "effect_unreconciled": {"effect_unreconciled": True},
        "observability_unproven": {"observability_unproven": True},
        "rollback_required_unproven": {"rollback_required_unproven": True},
        "legacy_duplication_unresolved": {"legacy_duplication_unresolved": True},
        "baseline_regression_uninvestigated": {"baseline_regression_uninvestigated": True},
        "pending_without_owner_or_deadline": {"pending_without_owner_or_deadline": True},
        "self_test_required_and_failed": {"self_test_required_and_failed": True},
        "architecture_material_not_validated": {"architecture_material_not_validated": True},
        "deployment_provenance_missing": {"deployment_provenance_missing": True},
        "browser_e2e_missing": {"browser_e2e_missing": True},
        "unmapped_surface": {"unmapped_surface": True},
        "untested_material_control": {"untested_material_control": True},
        "evidence_debt": {"evidence_debt": True},
        "contradictory_review_missing": {"contradictory_review_missing": True},
        "remediation_blocker": {"remediation_blocker": True},
        "clean_room_gap": {"clean_room_gap": True},
        "auth_discovery_gap": {"auth_discovery_gap": True},
        "project_invariant_gap": {"project_invariant_gap": True},
        "merge_enforcement_gap": {"merge_enforcement_gap": True},
    }

    for name, mutation in blockers.items():
        state = replace(baseline, **mutation)
        results.append(
            {"scenario": name, "expected_apto": False, "actual_apto": allows_apto(state)}
        )
    return results


def write_report(
    output_dir: Path,
    marker_results: list[dict[str, object]],
    gate_results: list[dict[str, object]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "AUDIT_SELF_TEST_V1",
        "policy_version": POLICY_VERSION,
        "marker_results": marker_results,
        "gate_results": gate_results,
    }
    (output_dir / "report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    lines = [
        "# Audit Governance Self-Test",
        "",
        f"- policy_version: {POLICY_VERSION}",
        f"- marker_checks: {len(marker_results)}",
        f"- synthetic_gate_scenarios: {len(gate_results)}",
        "",
        "## Marker checks",
    ]
    for item in marker_results:
        lines.append(f"- {'PASS' if item['ok'] else 'FAIL'} {item['file']}")
    lines += ["", "## Synthetic gate scenarios"]
    for item in gate_results:
        ok = item["expected_apto"] == item["actual_apto"]
        lines.append(
            f"- {'PASS' if ok else 'FAIL'} {item['scenario']}: "
            f"expected_apto={item['expected_apto']} actual_apto={item['actual_apto']}"
        )
    (output_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    marker_results = validate_markers()
    gate_results = self_test_gate()

    marker_ok = all(bool(item["ok"]) for item in marker_results)
    gate_ok = all(item["expected_apto"] == item["actual_apto"] for item in gate_results)

    if args.output_dir:
        write_report(args.output_dir, marker_results, gate_results)

    for item in marker_results:
        print(f"MARKER {'PASS' if item['ok'] else 'FAIL'} {item['file']}")
        if item["missing"]:
            print("  missing=" + ", ".join(str(x) for x in item["missing"]))
    for item in gate_results:
        ok = item["expected_apto"] == item["actual_apto"]
        print(
            f"GATE {'PASS' if ok else 'FAIL'} {item['scenario']} "
            f"expected={item['expected_apto']} actual={item['actual_apto']}"
        )

    if not marker_ok or not gate_ok:
        return 1
    print("AUDIT_GOVERNANCE_SELF_TEST=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
