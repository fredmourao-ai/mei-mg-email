#!/usr/bin/env python3
"""Fail-closed self-test for the ShopVivaliz extreme-audit governance contract."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_MARKERS = {
    "AUDIT_POLICY.md": [
        "2026-09-19-universal-architecture-v5",
        "AUDIT_UNIVERSAL_COVERAGE_V1",
        "AUDIT_SELF_TEST_V1",
        "ARCHITECTURE_DEPLOY_AUDIT_V1",
        "AUDIT_DEFINITION_OF_DONE_V1",
    ],
    "docs/quality/EXTREME_AUDIT_PROTOCOL.md": [
        "MAPEAR → IMPACTAR",
        "Caça a unknown unknowns",
        "AUDIT_SELF_TEST_V1",
    ],
    "docs/quality/AUDIT_RUNTIME_PARITY_V1.md": [
        "Falha silenciosa",
        "evidência crítica stale",
        "self-test obrigatório",
    ],
    "docs/quality/AUDIT_UNIVERSAL_COVERAGE_V1.md": [
        "AUDIT_ERROR_TAXONOMY_V1",
        "AUDIT_UNKNOWN_UNKNOWNS_V1",
        "AUDIT_SILENT_FAILURE_V1",
        "AUDIT_DIFFERENTIAL_METAMORPHIC_V1",
        "AUDIT_EVIDENCE_ARTIFACT_V1",
        "AUDIT_SELF_TEST_V1",
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
        "Marker de governança",
    ],
    "docs/quality/AUDIT_EVIDENCE_MANIFEST_TEMPLATE.md": [
        "Mapa de impacto",
        "Taxonomia universal",
        "Falhas silenciosas",
        "Self-test dos gates",
        "Unknown unknowns",
    ],
    "AGENTS.override.md": [
        "AUDIT_UNIVERSAL_COVERAGE_V1.md",
        "AUDIT_SELF_TEST_V1.md",
    ],
}


@dataclass(frozen=True)
class AuditState:
    p0: int = 0
    p1: int = 0
    p2_critical: int = 0
    critical_not_validated: bool = False
    audit_escape_pending: bool = False
    critical_improvement_required: bool = False
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
    production_runner_pure_ci_bottleneck: bool = False


def allows_apto(state: AuditState) -> bool:
    """Reference fail-closed model derived from AUDIT_POLICY.md."""
    return not any(
        [
            state.p0 > 0,
            state.p1 > 0,
            state.p2_critical > 0,
            state.critical_not_validated,
            state.audit_escape_pending,
            state.critical_improvement_required,
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
            state.production_runner_pure_ci_bottleneck,
        ]
    )


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

    optional_entrypoints = {
        "AGENTS.md": "ARCHITECTURE_DEPLOY_AUDIT_V1.md",
        "CLAUDE.md": "ARCHITECTURE_DEPLOY_AUDIT_V1.md",
        "REGRAS-AGENTES-CENTRALIZADAS.md": "AUDITORIA_EXTREMA_UNIVERSAL_V4",
    }
    for relative, marker in optional_entrypoints.items():
        path = ROOT / relative
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        results.append(
            {"file": relative, "ok": marker in content, "missing": [] if marker in content else [marker]}
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
        "p2_critical": {"p2_critical": 1},
        "critical_not_validated": {"critical_not_validated": True},
        "audit_escape_pending": {"audit_escape_pending": True},
        "critical_improvement_required": {"critical_improvement_required": True},
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
        "production_runner_pure_ci_bottleneck": {"production_runner_pure_ci_bottleneck": True},
    }
    for name, mutation in blockers.items():
        state = replace(baseline, **mutation)
        results.append(
            {"scenario": name, "expected_apto": False, "actual_apto": allows_apto(state)}
        )

    combined = replace(
        baseline,
        stale_evidence=True,
        reconciliation_gap=True,
        silent_failure=True,
        flaky_or_false_green_evidence=True,
    )
    results.append(
        {
            "scenario": "combined_hidden_failures",
            "expected_apto": False,
            "actual_apto": allows_apto(combined),
        }
    )
    return results


def write_report(output_dir: Path, marker_results: list[dict[str, object]], gate_results: list[dict[str, object]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "AUDIT_SELF_TEST_V1",
        "policy_version": "2026-09-19-universal-architecture-v5",
        "marker_results": marker_results,
        "gate_results": gate_results,
    }
    (output_dir / "report.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Audit Governance Self-Test",
        "",
        f"- policy_version: {payload['policy_version']}",
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
            f"- {'PASS' if ok else 'FAIL'} {item['scenario']}: expected_apto={item['expected_apto']} actual_apto={item['actual_apto']}"
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
