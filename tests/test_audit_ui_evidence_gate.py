#!/usr/bin/env python3
"""Regression and adversarial tests for the fail-closed real-UI evidence gate."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import struct
import zlib
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("audit_ui_evidence_gate", ROOT / "scripts" / "audit_ui_evidence_gate.py")
gate = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(gate)

SHA = "a" * 40
IDENTITY = SHA + "|release-1|production"
CASE = "b" * 64
CAPTURED = "2026-10-13T14:04:00Z"
EVENTS = [
    {"action": action, "control_id": "button-save" if action == "interact" else "",
     "observed": "saved state persisted" if action in ("assert_postcondition", "assert_persistence") else ""}
    for action in gate.UI_ACTIONS
]


def capture(auditor, session, captured=CAPTURED, cases=None):
    media = {
        "session-1": ["trace-primary", "screenshot-primary"],
        "session-2": ["trace-review", "screenshot-review"],
        "session-3": ["trace-post", "screenshot-post"],
    }.get(session, ["trace-review", "screenshot-review"])
    return {
        "schema": gate.UI_EXECUTION_SCHEMA,
        "sha_release_environment": IDENTITY,
        "journey_id": "case-review",
        "auditor": auditor,
        "session_id": session,
        "captured_at_utc": captured,
        "events": copy.deepcopy(EVENTS),
        "interacted_control_ids": ["button-save"],
        "media_refs": media,
        "case_sha256_ids": list(cases if cases is not None else [CASE]),
    }


def playwright_trace_bytes(run_id):
    """Synthetic structural fixture; never usable as a production UI attestation."""
    events = [
        {"type": "context-options", "browserName": "chromium", "runId": run_id},
        {"type": "before", "callId": f"{run_id}-goto", "apiName": "Page.goto"},
        {"type": "after", "callId": f"{run_id}-goto"},
        {"type": "before", "callId": f"{run_id}-click", "apiName": "Locator.click"},
        {"type": "after", "callId": f"{run_id}-click"},
    ]
    content = "\n".join(json.dumps(event) for event in events).encode()
    with io.BytesIO() as output:
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("trace.trace", content)
        return output.getvalue()


def png_bytes(run_id):
    """Actual PNG bytes with valid IHDR/IDAT/IEND and CRCs (synthetic test pixels)."""
    def chunk(kind, content):
        return struct.pack(">I", len(content)) + kind + content + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF)
    pixel = hashlib.sha256(run_id.encode()).digest()[:4]
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00" + pixel))
        + chunk(b"IEND", b"")
    )

def base_manifest():
    return {
        "identity": {"commit_sha": SHA, "release": "release-1", "environment": "production"},
        "evidence": {"artifacts": []},
        "browser": {"required": True, "ui_inventory_ref": "inventory"},
        "coverage": {"routes_discovered": 1, "interactive_controls_discovered": 1},
        "case_coverage": {"required": True, "inventory_ref": "cases"},
        "deploy": {"required": True, "activated_at_utc": "2026-10-13T14:00:00Z"},
        "contradictory_review": {"reviewer": "auditor-b"},
        "findings": {"discovered_total": 0},
        "remediation": {"fixed_findings": []},
        "journeys": [{
            "id": "case-review",
            "ui": True,
            "execution_ref": "primary",
            "contradictory_execution_ref": "review",
            "post_deploy_execution_ref": "post",
        }],
    }


class RealEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = base_manifest()
        self.put("inventory", "ui_inventory", {
            "schema": gate.UI_INVENTORY_SCHEMA, "sha_release_environment": IDENTITY,
            "ui_surface_present": True,
            "routes": [{"url": "https://example.test/cases", "control_ids": ["button-save"]}],
            "material_journey_ids": ["case-review"],
            "stateful_cases": True,
            "inspection_sources": ["browser-dom", "repo-routes"],
        })
        self.put("cases", "case_inventory", {
            "schema": gate.CASE_INVENTORY_SCHEMA, "sha_release_environment": IDENTITY,
            "case_sha256_ids": [CASE],
        })
        for run in ("primary", "review", "post"):
            self.put("trace-" + run, "playwright_trace", playwright_trace_bytes(run), suffix=".zip")
            self.put("screenshot-" + run, "screenshot", png_bytes(run), suffix=".png")
        self.put("primary", "ui_execution", capture("auditor-a", "session-1"))
        self.put("review", "ui_execution", capture("auditor-b", "session-2"))
        self.put("post", "ui_execution", capture("auditor-a", "session-3", captured="2026-10-13T14:05:00Z"))

    def put(self, name, kind, content, suffix=".json"):
        raw = (
            json.dumps(content, sort_keys=True).encode()
            if isinstance(content, (dict, list)) else content
        )
        filename = name + suffix
        (self.root / filename).write_bytes(raw)
        self.data["evidence"]["artifacts"].append({
            "id": name,
            "path": filename,
            "kind": kind,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "sha_release_environment": IDENTITY,
        })

    def verdict(self):
        return gate.validate_bundle(self.data, self.root)

    def test_complete_synthetic_structural_fixture_passes(self):
        self.assertEqual([], self.verdict())

    def test_false_sha_fails(self):
        self.data["evidence"]["artifacts"][0]["sha256"] = "0" * 64
        self.assertTrue(any("sha256 does not match real bytes" in x for x in self.verdict()))

    def test_missing_file_fails(self):
        (self.root / "trace-primary.zip").unlink()
        self.assertTrue(any("missing/unsafe" in x for x in self.verdict()))

    def test_path_escape_fails(self):
        self.data["evidence"]["artifacts"][0]["path"] = "../external.json"
        self.assertTrue(any("missing/unsafe" in x for x in self.verdict()))

    def test_fake_trace_fails(self):
        raw = b"dummy trace is not a browser run"
        (self.root / "trace-primary.zip").write_bytes(raw)
        trace = next(x for x in self.data["evidence"]["artifacts"] if x["id"] == "trace-primary")
        trace["sha256"] = hashlib.sha256(raw).hexdigest()
        self.assertTrue(any("Playwright" in x for x in self.verdict()))

    def test_self_review_does_not_pass(self):
        doc = self.root / "review.json"
        updated = capture("auditor-a", "session-1")
        raw = json.dumps(updated, sort_keys=True).encode()
        doc.write_bytes(raw)
        artifact = next(x for x in self.data["evidence"]["artifacts"] if x["id"] == "review")
        artifact["sha256"] = hashlib.sha256(raw).hexdigest()
        self.assertTrue(any("different auditor AND session" in x for x in self.verdict()))

    def test_uninventoried_control_fails(self):
        self.data["coverage"]["interactive_controls_discovered"] = 0
        self.assertTrue(any("control count disagrees" in x for x in self.verdict()))

    def test_unvisited_control_fails(self):
        doc = self.root / "inventory.json"
        inventory = json.loads(doc.read_text())
        inventory["routes"][0]["control_ids"].append("unknown-button")
        self.data["coverage"]["interactive_controls_discovered"] = 2
        raw = json.dumps(inventory, sort_keys=True).encode()
        doc.write_bytes(raw)
        artifact = next(x for x in self.data["evidence"]["artifacts"] if x["id"] == "inventory")
        artifact["sha256"] = hashlib.sha256(raw).hexdigest()
        self.assertTrue(any("UI controls not exercised" in x for x in self.verdict()))

    def test_missing_case_blocks(self):
        doc = self.root / "primary.json"
        updated = capture("auditor-a", "session-1", cases=[])
        raw = json.dumps(updated, sort_keys=True).encode()
        doc.write_bytes(raw)
        artifact = next(x for x in self.data["evidence"]["artifacts"] if x["id"] == "primary")
        artifact["sha256"] = hashlib.sha256(raw).hexdigest()
        self.assertTrue(any("real cases not exercised" in x for x in self.verdict()))

    def test_postdeploy_predeployment_proof_fails(self):
        self.data["deploy"]["activated_at_utc"] = "2026-10-13T14:06:00Z"
        self.assertTrue(any("after actual deployment" in x for x in self.verdict()))

    def test_red_green_reaudit_required_for_defect(self):
        self.data["findings"]["discovered_total"] = 1
        self.assertTrue(any("every discovered finding" in x for x in self.verdict()))

    def test_fixed_defect_requires_four_distinct_real_artifacts(self):
        self.data["findings"]["discovered_total"] = 1
        self.data["remediation"]["fixed_findings"] = [{
            "id": "defect-1",
            "root_cause": "broken state transition after save",
            "fix_sha": SHA,
            "red_ref": "primary",
            "green_ref": "primary",
            "regression_ref": "review",
            "reaudit_ref": "post",
        }]
        self.assertTrue(any("distinct verified RED/GREEN" in x for x in self.verdict()))

    def test_no_ui_opt_out_requires_negative_inventory(self):
        self.data["browser"]["required"] = False
        self.assertTrue(any("disagrees with runtime UI inventory" in x for x in self.verdict()))


    def rewrite_json(self, name, value):
        path = self.root / (name + ".json")
        raw = json.dumps(value, sort_keys=True).encode()
        path.write_bytes(raw)
        for artifact in self.data["evidence"]["artifacts"]:
            if artifact["id"] == name:
                artifact["sha256"] = hashlib.sha256(raw).hexdigest()
                return
        raise AssertionError("missing artifact fixture")

    def test_magic_bytes_without_complete_png_are_rejected(self):
        raw = b"\x89PNG\r\n\x1a\n" + b"placeholder is not an image"
        (self.root / "screenshot-primary.png").write_bytes(raw)
        for artifact in self.data["evidence"]["artifacts"]:
            if artifact["id"] == "screenshot-primary":
                artifact["sha256"] = hashlib.sha256(raw).hexdigest()
        self.assertTrue(any("complete PNG" in x for x in self.verdict()))

    def test_click_only_trace_cannot_prove_real_navigation(self):
        records = [
            {"type": "context-options", "browserName": "chromium"},
            {"type": "before", "callId": "click", "apiName": "Locator.click"},
            {"type": "after", "callId": "click"},
        ]
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("trace.trace", "\n".join(json.dumps(r) for r in records))
        raw = output.getvalue()
        (self.root / "trace-primary.zip").write_bytes(raw)
        for artifact in self.data["evidence"]["artifacts"]:
            if artifact["id"] == "trace-primary":
                artifact["sha256"] = hashlib.sha256(raw).hexdigest()
        self.assertTrue(any("Playwright" in x for x in self.verdict()))

    def test_standard_playwright_method_trace_proves_navigation_and_interaction(self):
        records = [
            {"type": "context-options", "browserName": "chromium"},
            {"type": "before", "callId": "goto", "method": "goto"},
            {"type": "after", "callId": "goto"},
            {"type": "before", "callId": "fill", "method": "fill"},
            {"type": "after", "callId": "fill"},
        ]
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("trace.trace", "\n".join(json.dumps(r) for r in records))
        raw = output.getvalue()
        (self.root / "trace-primary.zip").write_bytes(raw)
        for artifact in self.data["evidence"]["artifacts"]:
            if artifact["id"] == "trace-primary":
                artifact["sha256"] = hashlib.sha256(raw).hexdigest()
        self.assertFalse(any("lacks real Playwright" in x for x in self.verdict()))

    def test_review_must_not_reuse_primary_capture(self):
        review = capture("auditor-b", "session-2")
        review["media_refs"] = ["trace-primary", "screenshot-primary"]
        self.rewrite_json("review", review)
        self.assertTrue(any("media is reused" in x for x in self.verdict()))

    def test_review_must_reexecute_every_real_case(self):
        self.rewrite_json("review", capture("auditor-b", "session-2", cases=[]))
        self.assertTrue(any("real cases not exercised" in x and "independent" in x for x in self.verdict()))

    def test_postdeploy_must_reexecute_every_real_case(self):
        self.rewrite_json("post", capture("auditor-a", "session-3", cases=[]))
        self.assertTrue(any("real cases not exercised" in x and "post-deploy" in x for x in self.verdict()))

    def test_reviewer_must_actually_interact_with_each_control(self):
        review = capture("auditor-b", "session-2")
        review["interacted_control_ids"] = []
        review["events"] = [e for e in review["events"] if e["action"] != "interact"]
        self.rewrite_json("review", review)
        self.assertTrue(any("UI controls not exercised" in x and "independent" in x for x in self.verdict()))

    def test_assertion_requires_observed_ui_state(self):
        primary = capture("auditor-a", "session-1")
        for e in primary["events"]:
            if e["action"] == "assert_persistence":
                e["observed"] = ""
        self.rewrite_json("primary", primary)
        self.assertTrue(any("assert_persistence needs an observed UI state" in x for x in self.verdict()))


if __name__ == "__main__":
    unittest.main()
