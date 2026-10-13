#!/usr/bin/env python3
"""Verify concrete UI evidence for Extreme Audit V5; never trust boolean attestations alone.

This module validates artifacts collected by an authorized browser/desktop runner.
It does not click a UI, infer authentication, or bypass approval requirements.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

UI_INVENTORY_SCHEMA = "AUDIT_UI_INVENTORY_V2"
UI_EXECUTION_SCHEMA = "AUDIT_UI_EXECUTION_V2"
CASE_INVENTORY_SCHEMA = "AUDIT_CASE_INVENTORY_V2"
HEX64 = re.compile(r"^[a-fA-F0-9]{64}$")
HEX40 = re.compile(r"^[a-fA-F0-9]{40}$")
MAX_JSON_SIZE = 8 * 1024 * 1024
UI_ACTIONS = ("navigate", "interact", "assert_postcondition", "reload", "revisit", "assert_persistence")


def _utc(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, OverflowError):
        return None


def _digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _safe_file(root, name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("artifact path missing")
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts or rel == Path("."):
        raise ValueError("artifact path escapes evidence root")
    file = root / rel
    if any(part.is_symlink() for part in [root, *list(file.parents)[:len(rel.parts)], file]):
        raise ValueError("artifact path uses symlink")
    resolved = file.resolve(strict=True)
    if not resolved.is_relative_to(root.resolve(strict=True)) or not resolved.is_file():
        raise ValueError("artifact is not a regular file under evidence root")
    if resolved.stat().st_size == 0:
        raise ValueError("artifact is empty")
    return resolved


def _load_json(path):
    if path.stat().st_size > MAX_JSON_SIZE:
        raise ValueError("JSON artifact exceeds safety limit")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON evidence must be an object")
    return value


def _check_playwright_trace(path):
    if not zipfile.is_zipfile(path):
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            entries = [x for x in archive.namelist() if x.endswith(".trace")]
            if not entries:
                return False
            for name in entries:
                if archive.getinfo(name).file_size > 40 * 1024 * 1024:
                    continue
                before, after, actions = set(), set(), 0
                with archive.open(name) as handle:
                    for line in handle:
                        try:
                            event = json.loads(line)
                        except (ValueError, UnicodeDecodeError):
                            continue
                        if not isinstance(event, dict):
                            continue
                        call_id = event.get("callId")
                        if event.get("type") == "before" and call_id:
                            before.add(call_id)
                            api = str(event.get("apiName", "")).lower()
                            if any(a in api for a in (".click", ".fill", ".press", ".goto", ".check", ".select")):
                                actions += 1
                        elif event.get("type") == "after" and call_id:
                            after.add(call_id)
                if (before & after) and actions >= 1:
                    return True
    except (OSError, ValueError, zipfile.BadZipFile):
        return False
    return False


def validate_bundle(data: dict, evidence_root: Path) -> list[str]:
    """Return fail-closed blockers for a real on-disk certification bundle."""
    failures = []
    if not isinstance(data, dict):
        return ["certification manifest must be a JSON object"]
    identity = data.get("identity") or {}
    evidence = data.get("evidence") or {}
    browser = data.get("browser") or {}
    coverage = data.get("coverage") or {}
    deploy = data.get("deploy") or {}
    findings = data.get("findings") or {}
    remediation = data.get("remediation") or {}
    expected = "|".join(str(identity.get(key, "")) for key in ("commit_sha", "release", "environment"))
    items = evidence.get("artifacts")
    if not isinstance(items, list) or not items:
        return ["evidence.artifacts must contain actual files"]

    artifacts, paths, json_cache = {}, {}, {}
    for index, artifact in enumerate(items):
        prefix = f"evidence.artifacts[{index}]"
        if not isinstance(artifact, dict):
            failures.append(f"{prefix} must be an object")
            continue
        aid = artifact.get("id")
        if not isinstance(aid, str) or not aid or aid in artifacts:
            failures.append(f"{prefix}.id is missing/duplicate")
            continue
        artifacts[aid] = artifact
        if artifact.get("sha_release_environment") != expected:
            failures.append(f"{prefix} does not match certified SHA/release/environment")
        try:
            candidate = _safe_file(evidence_root, artifact.get("path"))
            digest = artifact.get("sha256")
            if not isinstance(digest, str) or not HEX64.fullmatch(digest) or _digest(candidate) != digest.lower():
                failures.append(f"{prefix}.sha256 does not match real bytes")
                continue
            paths[aid] = candidate
            kind = artifact.get("kind")
            if kind == "screenshot":
                with candidate.open("rb") as handle:
                    if handle.read(8) != b"\x89PNG\r\n\x1a\n":
                        failures.append(f"{prefix} screenshot must be a real PNG")
            if kind == "playwright_trace" and not _check_playwright_trace(candidate):
                failures.append(f"{prefix} lacks real Playwright before/after interaction events")
            if kind == "video":
                with candidate.open("rb") as handle:
                    if b"ftyp" not in handle.read(16):
                        failures.append(f"{prefix} video must be an MP4 recording")
        except (OSError, ValueError) as exc:
            failures.append(f"{prefix} missing/unsafe file: {type(exc).__name__}")

    def document(ref, kind):
        if not isinstance(ref, str) or ref not in artifacts or ref not in paths:
            failures.append(f"missing verified {kind} evidence ref: {ref!r}")
            return None
        if artifacts[ref].get("kind") != kind:
            failures.append(f"evidence {ref!r} must be kind={kind}")
            return None
        if ref in json_cache:
            return json_cache[ref]
        try:
            result = _load_json(paths[ref])
            json_cache[ref] = result
            return result
        except (ValueError, UnicodeError, OSError):
            failures.append(f"evidence {ref!r} is not valid JSON")
            return None

    inventory = document(browser.get("ui_inventory_ref"), "ui_inventory")
    journeys = data.get("journeys") or []
    ui_journeys = [x for x in journeys if isinstance(x, dict) and x.get("ui") is True]
    controls = set()
    discovered_journeys = set()
    stateful_cases = False
    if inventory is not None:
        if inventory.get("schema") != UI_INVENTORY_SCHEMA:
            failures.append("UI inventory schema invalid")
        if inventory.get("sha_release_environment") != expected:
            failures.append("UI inventory from wrong release/environment")
        if type(inventory.get("ui_surface_present")) is not bool:
            failures.append("UI inventory must explicitly prove ui_surface_present true/false")
        if inventory.get("ui_surface_present") != (browser.get("required") is True):
            failures.append("browser.required disagrees with runtime UI inventory")
        routes = inventory.get("routes")
        if not isinstance(routes, list):
            failures.append("UI inventory routes missing")
        else:
            if coverage.get("routes_discovered") != len(routes):
                failures.append("route count disagrees with observed UI inventory")
            for route in routes:
                if not isinstance(route, dict) or not isinstance(route.get("url"), str):
                    failures.append("UI inventory contains invalid route")
                    continue
                route_controls = route.get("control_ids")
                if not isinstance(route_controls, list) or any(not isinstance(x, str) or not x for x in route_controls):
                    failures.append("UI inventory route has invalid control_ids")
                    continue
                controls.update(route_controls)
            if coverage.get("interactive_controls_discovered") != len(controls):
                failures.append("control count disagrees with observed UI inventory")
        declared = inventory.get("material_journey_ids")
        if not isinstance(declared, list) or any(not isinstance(x, str) for x in declared):
            failures.append("UI inventory material_journey_ids invalid")
        else:
            discovered_journeys = set(declared)
            if len(discovered_journeys) != len(declared):
                failures.append("UI inventory duplicate material journey")
            if {x.get("id") for x in ui_journeys} != discovered_journeys:
                failures.append("material UI journey inventory does not match tested journeys")
        stateful_cases = inventory.get("stateful_cases") is True
        if browser.get("required") is False:
            sources = inventory.get("inspection_sources")
            if inventory.get("ui_surface_present") is not False or not isinstance(sources, list) or len(set(map(str, sources))) < 2:
                failures.append("no-UI exemption lacks independent negative inventory sources")
        elif not routes or not ui_journeys:
            failures.append("UI present but route/journey inventory empty")

    seen_controls = set()
    case_ids = set()
    if stateful_cases:
        case_inventory = document(data.get("case_coverage", {}).get("inventory_ref"), "case_inventory")
        if case_inventory is not None:
            if case_inventory.get("schema") != CASE_INVENTORY_SCHEMA or case_inventory.get("sha_release_environment") != expected:
                failures.append("case inventory schema or release mismatch")
            values = case_inventory.get("case_sha256_ids")
            if not isinstance(values, list) or not values or any(not isinstance(x, str) or not HEX64.fullmatch(x) for x in values):
                failures.append("case inventory must enumerate hashed real case IDs")
            else:
                case_ids = set(values)
                if len(case_ids) != len(values):
                    failures.append("case inventory has duplicate case IDs")
        if data.get("case_coverage", {}).get("required") is not True:
            failures.append("stateful cases cannot opt out of case-by-case UI coverage")

    def execution(ref, journey_id, role):
        log = document(ref, "ui_execution")
        if log is None:
            return None
        if log.get("schema") != UI_EXECUTION_SCHEMA or log.get("sha_release_environment") != expected:
            failures.append(f"{role} UI execution from wrong schema/release")
        if log.get("journey_id") != journey_id:
            failures.append(f"{role} UI execution mismatches journey {journey_id}")
        if not isinstance(log.get("auditor"), str) or not log.get("auditor") or not log.get("session_id"):
            failures.append(f"{role} UI execution lacks auditor and session provenance")
        if _utc(log.get("captured_at_utc")) is None:
            failures.append(f"{role} UI execution lacks UTC capture time")
        events = log.get("events")
        if not isinstance(events, list) or len(events) < len(UI_ACTIONS):
            failures.append(f"{role} UI execution missing real interaction sequence")
            return log
        actions = [e.get("action") for e in events if isinstance(e, dict)]
        position = -1
        for action in UI_ACTIONS:
            try:
                position = actions.index(action, position + 1)
            except ValueError:
                failures.append(f"{role} UI execution missing ordered step {action}")
                break
        ids = log.get("interacted_control_ids")
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
            failures.append(f"{role} UI execution lacks interacted_control_ids")
        elif role == "primary":
            seen_controls.update(ids)
        media = log.get("media_refs")
        if not isinstance(media, list) or not media:
            failures.append(f"{role} UI execution lacks visual media")
        else:
            media_kinds = {artifacts.get(r, {}).get("kind") for r in media if r in paths}
            if not ("playwright_trace" in media_kinds or "video" in media_kinds):
                failures.append(f"{role} UI execution lacks verified real browser trace or video")
            if not ("screenshot" in media_kinds or "video" in media_kinds):
                failures.append(f"{role} UI execution lacks verified visual capture")
        return log

    for journey in ui_journeys:
        jid = journey.get("id")
        primary = execution(journey.get("execution_ref"), jid, "primary")
        review = execution(journey.get("contradictory_execution_ref"), jid, "independent")
        if primary and review:
            if primary.get("auditor") == review.get("auditor") or primary.get("session_id") == review.get("session_id"):
                failures.append(f"journey {jid} independent review must use different auditor AND session")
            reviewer = (data.get("contradictory_review") or {}).get("reviewer")
            if review.get("auditor") != reviewer:
                failures.append(f"journey {jid} independent execution auditor disagrees with reviewer")
        if stateful_cases and primary:
            values = primary.get("case_sha256_ids")
            if isinstance(values, list):
                seen_ids = set(values)
                if not seen_ids.issubset(case_ids):
                    failures.append(f"journey {jid} exercised case absent from inventory")
                case_ids.difference_update(seen_ids)
            else:
                failures.append(f"journey {jid} lacks real case-by-case IDs")
        if deploy.get("required") is True:
            post = execution(journey.get("post_deploy_execution_ref"), jid, "post-deploy")
            activated = _utc(deploy.get("activated_at_utc"))
            captured = _utc(post.get("captured_at_utc")) if post else None
            if activated is None or captured is None or captured < activated:
                failures.append(f"journey {jid} lacks UI evidence after actual deployment")
            if primary and post and primary.get("session_id") == post.get("session_id") and journey.get("execution_ref") == journey.get("post_deploy_execution_ref"):
                failures.append(f"journey {jid} post-deploy must be a fresh execution")

    if controls and controls != seen_controls:
        failures.append(f"UI controls not exercised by real captured journeys: {len(controls - seen_controls)}")
    if stateful_cases and case_ids:
        failures.append(f"real cases not exercised case-by-case in UI: {len(case_ids)}")

    total = findings.get("discovered_total")
    fixes = remediation.get("fixed_findings")
    if type(total) is not int or total < 0 or not isinstance(fixes, list):
        failures.append("findings.discovered_total and remediation.fixed_findings required")
    elif len(fixes) != total:
        failures.append("every discovered finding requires a full RED/GREEN/reaudit record")
    else:
        seen_findings = set()
        for fix in fixes:
            if not isinstance(fix, dict):
                failures.append("fixed finding must be an object")
                continue
            fid = fix.get("id")
            if not isinstance(fid, str) or not fid or fid in seen_findings:
                failures.append("fixed finding ID missing/duplicate")
            seen_findings.add(fid)
            if not isinstance(fix.get("root_cause"), str) or len(fix["root_cause"].strip()) < 15:
                failures.append(f"finding {fid} missing concrete root cause")
            if not isinstance(fix.get("fix_sha"), str) or not HEX40.fullmatch(fix["fix_sha"]):
                failures.append(f"finding {fid} lacks fix commit SHA")
            refs = [fix.get(k) for k in ("red_ref", "green_ref", "regression_ref", "reaudit_ref")]
            if len(set(refs)) != 4 or any(not isinstance(r, str) or r not in paths for r in refs):
                failures.append(f"finding {fid} missing distinct verified RED/GREEN/regression/reaudit artifacts")

    return failures
