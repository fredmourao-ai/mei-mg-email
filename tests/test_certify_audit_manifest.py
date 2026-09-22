#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("certifier", ROOT / "scripts" / "certify-audit-manifest.py")
certifier = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(certifier)

REQ_FINGERPRINT = "d" * 64


def base_requirements():
    return {
        "schema": certifier.PROJECT_REQUIREMENTS_SCHEMA,
        "project": "Vivaliz-site/-shopvivaliz-pipeline",
        "policy_version": certifier.POLICY_VERSION,
        "required_invariants": [
            {
                "id": "TEST_INVARIANT_V1",
                "type": "evidence",
                "description": "test invariant",
            }
        ],
    }


def valid_manifest():
    return {
        "schema": certifier.SCHEMA,
        "policy_version": certifier.POLICY_VERSION,
        "identity": {
            "audit_id": "AUD-1",
            "repository": "Vivaliz-site/-shopvivaliz-pipeline",
            "commit_sha": "a" * 40,
            "build_digest": "sha256:" + "b" * 64,
            "release": "release-1",
            "environment": "production",
            "timestamp_utc": "2026-09-21T23:59:00Z",
            "certified_scope": "all material user journeys",
            "scope_is_explicit": True,
            "primary_auditor": "agent-a",
        },
        "fingerprint": {
            "complete": True,
            "schema_version": "schema-1",
            "config_fingerprint": "cfg-1",
            "feature_flags_fingerprint": "flags-1",
            "provider_versions": {"provider": "v1"},
            "material_change_invalidation_checked": True,
        },
        "evidence": {
            "fresh": True,
            "same_sha_build": True,
            "same_environment": True,
            "provenance_complete": True,
            "artifact_hashes_verified": True,
            "debt_count": 0,
            "artifacts": [
                {
                    "id": "trace",
                    "path": "trace.zip",
                    "kind": "trace",
                    "sha256": "c" * 64,
                    "sha_release_environment": "a" * 40 + "|release-1|production",
                }
            ],
        },
        "coverage": {
            "inventory_complete": True,
            "all_material_journeys_enumerated": True,
            "all_material_states_enumerated": True,
            "all_material_controls_classified": True,
            "negative_paths_complete": True,
            "boundaries_complete": True,
            "environment_matrix_complete": True,
            "not_validated_count": 0,
            "routes_discovered": 1,
            "interactive_controls_discovered": 1,
            "material_journeys": 1,
            "covered_controls": 1,
            "unmapped_surfaces": 0,
            "untested_material_controls": 0,
            "uncovered_material_journeys": 0,
        },
        "taxonomy": {"complete": True, "no_material_not_validated": True},
        "browser": {
            "required": True,
            "real_browser": True,
            "graphical_session": True,
            "agent_executed": True,
            "same_release": True,
            "full_user_path": True,
            "reload_revisit": True,
            "persistence_checked": True,
            "console_checked": True,
            "network_checked": True,
            "visual_evidence": True,
            "no_user_delegation": True,
            "not_headless_only": True,
            "clean_context_exercised_when_material": True,
            "mobile_desktop_exercised_when_material": True,
            "navigation_variants_exercised_when_material": True,
        },
        "clean_room": {
            "required": True,
            "completed_or_not_material": True,
            "clean_storage": True,
            "cold_cache": True,
            "auth_states_exercised": True,
            "cache_service_worker_checked": True,
            "navigation_reality_checked": True,
            "concurrency_checked": True,
            "partial_failure_recovery_checked": True,
            "cold_start_checked": True,
            "temporal_edges_checked": True,
            "soak_leak_checked_or_not_material": True,
        },
        "chaos_recovery": {
            "required": True,
            "completed_or_not_material": True,
            "timeout_checked": True,
            "rate_limit_checked": True,
            "server_error_checked": True,
            "partial_failure_checked": True,
            "retry_idempotency_checked": True,
            "alert_recovery_checked": True,
        },
        "authorization": {"matrix_complete_or_not_material": True},
        "visual": {"interaction_regression_complete_or_not_material": True},
        "auth_discovery": {
            "required": False,
            "complete_or_not_material": True,
            "repositories_expected": [],
            "repositories_scanned": [],
            "repositories_expected_count": 0,
            "repositories_scanned_count": 0,
            "all_repositories_scanned": False,
            "repo_secret_references_checked": False,
            "runtime_secret_stores_checked": False,
            "canonical_profiles_checked": False,
            "oauth_cli_sessions_checked": False,
            "alternative_transports_checked": False,
            "safe_probe_attempted": False,
            "exhausted": False,
            "no_secret_exposure": True,
        },
        "project_invariants": {
            "complete": True,
            "requirements_fingerprint": REQ_FINGERPRINT,
            "failed_required_count": 0,
            "missing_required_count": 0,
            "results": [
                {
                    "id": "TEST_INVARIANT_V1",
                    "status": "COMPROVADO",
                    "evidence_refs": ["trace"],
                }
            ],
        },
        "data": {
            "reconciliation_complete": True,
            "orphan_scan_complete": True,
            "no_unexplained_difference": True,
            "unexplained_difference_count": 0,
        },
        "runtime": {
            "no_unresolved_5xx": True,
            "no_unresolved_pageerror": True,
            "no_unresolved_requestfailed": True,
            "no_unresolved_console_error": True,
            "no_silent_failure": True,
            "unresolved_error_count": 0,
        },
        "external_effects": {"reconciled": True},
        "async_runtime": {"observed": True, "settlement_complete": True},
        "observability": {"proven": True},
        "recovery": {"proven_or_not_material": True},
        "architecture": {"complete": True},
        "legacy_duplication": {"checked": True},
        "baseline": {"acceptable_or_not_material": True},
        "tests": {
            "no_flaky_false_green": True,
            "self_test_complete_when_applicable": True,
            "certifier_mutation_self_test_passed": True,
        },
        "unknown_unknowns": {"completed": True},
        "audit_escape": {
            "pending_count": 0,
            "historical_classes_reaudited": True,
            "regression_tests_added_for_new_escapes": True,
            "certification_invalidation_checked": True,
        },
        "contradictory_review": {
            "completed": True,
            "reviewer_distinct": True,
            "no_open_findings": True,
            "reviewer": "agent-b",
        },
        "remediation": {
            "loop_completed": True,
            "no_gate_weakening": True,
            "no_executable_issue_deferred": True,
            "open_blockers": 0,
            "executable_blockers": 0,
            "blocked_external_count": 0,
            "blocked_external_proven": False,
            "blocked_external_category": "",
        },
        "findings": {
            "p0": 0,
            "p1": 0,
            "p2": 0,
            "p3": 0,
            "open_defects_total": 0,
            "improvement_required_open": 0,
            "preexisting_active_defects": 0,
        },
        "deploy": {
            "required": True,
            "same_sha_active": True,
            "post_deploy_validation_complete": True,
            "post_deploy_browser_e2e_complete_or_not_material": True,
            "post_deploy_async_observation_complete": True,
            "release_fingerprint_matches": True,
        },
        "certification": {"scope_label_exact": True, "no_self_attestation": True},
        "journeys": [
            {
                "id": "critical-ui-flow",
                "material": True,
                "critical": True,
                "ui": True,
                "status": "COMPROVADO",
                "contradictory_reaudit": True,
                "evidence_refs": ["trace"],
                "browser_e2e": {
                    "real_browser": True,
                    "graphical_session": True,
                    "agent_executed": True,
                    "same_release": True,
                    "full_user_path": True,
                    "reload_revisit": True,
                    "persistence_checked": True,
                    "console_checked": True,
                    "network_checked": True,
                    "visual_evidence": True,
                    "no_user_delegation": True,
                    "not_headless_only": True,
                },
            }
        ],
    }


def set_path(data, path, value):
    target = data
    parts = path.split(".")
    for part in parts[:-1]:
        target = target[part]
    target[parts[-1]] = value


def certify(data, requirements=None, fingerprint=REQ_FINGERPRINT):
    return certifier.certify(data, requirements or base_requirements(), fingerprint)


class CertifierTests(unittest.TestCase):
    def test_valid_manifest_is_apto(self):
        verdict, failures = certify(valid_manifest())
        self.assertEqual("APTO", verdict, failures)
        self.assertEqual([], failures)

    def test_every_boolean_gate_blocks_when_false(self):
        all_paths = (
            certifier.REQUIRED_TRUE
            + certifier.BROWSER_REQUIRED_TRUE
            + certifier.DEPLOY_REQUIRED_TRUE
            + certifier.CLEAN_ROOM_REQUIRED_TRUE
            + certifier.CHAOS_REQUIRED_TRUE
        )
        for path in all_paths:
            with self.subTest(path=path):
                data = valid_manifest()
                set_path(data, path, False)
                verdict, _ = certify(data)
                self.assertNotEqual("APTO", verdict)

    def test_every_zero_gate_blocks_when_nonzero(self):
        for path in certifier.REQUIRED_ZERO:
            with self.subTest(path=path):
                data = valid_manifest()
                set_path(data, path, 1)
                verdict, _ = certify(data)
                self.assertNotEqual("APTO", verdict)

    def test_ui_journey_cannot_be_headless_only(self):
        data = valid_manifest()
        data["journeys"][0]["browser_e2e"]["not_headless_only"] = False
        self.assertEqual("NAO_APTO", certify(data)[0])

    def test_user_delegated_browser_cannot_certify(self):
        data = valid_manifest()
        data["browser"]["no_user_delegation"] = False
        self.assertEqual("NAO_APTO", certify(data)[0])

    def test_preexisting_defect_blocks(self):
        data = valid_manifest()
        data["findings"]["preexisting_active_defects"] = 1
        self.assertEqual("NAO_APTO", certify(data)[0])

    def test_unmapped_surface_blocks(self):
        data = valid_manifest()
        data["coverage"]["unmapped_surfaces"] = 1
        self.assertEqual("NAO_APTO", certify(data)[0])

    def test_evidence_hash_is_required(self):
        data = valid_manifest()
        data["evidence"]["artifacts"][0]["sha256"] = "bad"
        self.assertEqual("NAO_APTO", certify(data)[0])

    def test_unknown_evidence_reference_blocks(self):
        data = valid_manifest()
        data["journeys"][0]["evidence_refs"] = ["missing"]
        self.assertEqual("NAO_APTO", certify(data)[0])

    def test_self_attested_verdict_blocks(self):
        data = valid_manifest()
        data["verdict"] = "APTO"
        self.assertEqual("NAO_APTO", certify(data)[0])

    def test_same_auditor_and_reviewer_blocks(self):
        data = valid_manifest()
        data["contradictory_review"]["reviewer"] = "agent-a"
        self.assertEqual("NAO_APTO", certify(data)[0])

    def test_missing_local_requirement_blocks(self):
        data = valid_manifest()
        data["project_invariants"]["results"] = []
        self.assertEqual("NAO_APTO", certify(data)[0])

    def test_requirements_fingerprint_mismatch_blocks(self):
        data = valid_manifest()
        data["project_invariants"]["requirements_fingerprint"] = "e" * 64
        self.assertEqual("NAO_APTO", certify(data)[0])

    def test_provider_chat_requires_all_three_real_responses(self):
        requirements = {
            "schema": certifier.PROJECT_REQUIREMENTS_SCHEMA,
            "project": "Vivaliz-site/-shopvivaliz-pipeline",
            "required_invariants": [
                {
                    "id": "THREE_AI_V1",
                    "type": "provider_chat",
                    "providers": ["openai", "anthropic", "gemini"],
                    "phases": ["research", "critique", "converge"],
                    "consensus_required": True,
                }
            ],
        }
        data = valid_manifest()
        data["project_invariants"]["results"] = [
            {
                "id": "THREE_AI_V1",
                "status": "COMPROVADO",
                "evidence_refs": ["trace"],
                "details": {
                    "provider_chat": {
                        "same_cycle": True,
                        "ui_visible": True,
                        "cycle_finished_ok": True,
                        "health_verified": True,
                        "consensus_emitted": True,
                        "providers": {
                            provider: {
                                "active": True,
                                "responded": True,
                                "nonempty_response": True,
                                "visible": True,
                                "phases": {
                                    "research": True,
                                    "critique": True,
                                    "converge": True,
                                },
                            }
                            for provider in ["openai", "anthropic", "gemini"]
                        },
                    }
                },
            }
        ]
        verdict, failures = certifier.certify(data, requirements, REQ_FINGERPRINT)
        self.assertEqual("APTO", verdict, failures)

        data["project_invariants"]["results"][0]["details"]["provider_chat"]["providers"]["gemini"]["responded"] = False
        verdict, failures = certifier.certify(data, requirements, REQ_FINGERPRINT)
        self.assertEqual("NAO_APTO", verdict)
        self.assertTrue(any("gemini.responded" in item for item in failures))

    def test_auth_external_blocker_requires_all_repositories_scanned(self):
        data = valid_manifest()
        data["remediation"]["blocked_external_count"] = 1
        data["remediation"]["blocked_external_proven"] = True
        data["remediation"]["blocked_external_category"] = "AUTH"
        data["auth_discovery"]["required"] = True
        for path in certifier.AUTH_DISCOVERY_REQUIRED_TRUE:
            set_path(data, path, True)
        data["auth_discovery"]["repositories_expected"] = list(certifier.REQUIRED_REPOSITORIES)
        data["auth_discovery"]["repositories_expected_count"] = len(certifier.REQUIRED_REPOSITORIES)
        data["auth_discovery"]["repositories_scanned"] = list(certifier.REQUIRED_REPOSITORIES[:-1])
        data["auth_discovery"]["repositories_scanned_count"] = len(certifier.REQUIRED_REPOSITORIES) - 1
        verdict, failures = certify(data)
        self.assertEqual("NAO_APTO", verdict)
        self.assertTrue(any("repositories_scanned" in item for item in failures))

    def test_auth_external_blocker_is_allowed_only_after_exhaustive_discovery(self):
        data = valid_manifest()
        data["remediation"]["blocked_external_count"] = 1
        data["remediation"]["blocked_external_proven"] = True
        data["remediation"]["blocked_external_category"] = "AUTH"
        data["auth_discovery"]["required"] = True
        for path in certifier.AUTH_DISCOVERY_REQUIRED_TRUE:
            set_path(data, path, True)
        data["auth_discovery"]["repositories_expected"] = list(certifier.REQUIRED_REPOSITORIES)
        data["auth_discovery"]["repositories_scanned"] = list(certifier.REQUIRED_REPOSITORIES)
        data["auth_discovery"]["repositories_expected_count"] = len(certifier.REQUIRED_REPOSITORIES)
        data["auth_discovery"]["repositories_scanned_count"] = len(certifier.REQUIRED_REPOSITORIES)
        verdict, failures = certify(data)
        self.assertEqual("BLOCKED_EXTERNAL", verdict, failures)

    def test_generic_external_blocker_stays_blocked_only_when_clean(self):
        data = valid_manifest()
        data["remediation"]["blocked_external_count"] = 1
        data["remediation"]["blocked_external_proven"] = True
        data["remediation"]["blocked_external_category"] = "THIRD_PARTY_OUTAGE"
        verdict, failures = certify(data)
        self.assertEqual("BLOCKED_EXTERNAL", verdict, failures)

        data["remediation"]["executable_blockers"] = 1
        verdict, failures = certify(data)
        self.assertEqual("NAO_APTO", verdict)
        self.assertTrue(any("executable blockers remain" in item for item in failures))

    def test_wrong_policy_version_blocks(self):
        data = valid_manifest()
        data["policy_version"] = "old"
        self.assertEqual("NAO_APTO", certify(data)[0])


if __name__ == "__main__":
    unittest.main()
