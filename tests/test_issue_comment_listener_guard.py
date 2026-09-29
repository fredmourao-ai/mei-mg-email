import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "scripts" / "check_issue_comment_listeners.py"


def load_guard():
    spec = importlib.util.spec_from_file_location(
        "check_issue_comment_listeners_under_test", GUARD_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


DIRECT_LISTENER_WORKFLOW = """\
name: Direct listener
on:
  issue_comment:
    types: [created]
jobs:
  respond:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
"""

PUSH_ONLY_WORKFLOW = """\
name: Push only
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo build
"""

SHORTHAND_LIST_LISTENER_WORKFLOW = """\
name: Shorthand list listener
on: [push, issue_comment]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo build
"""

SINGLE_SCALAR_TRIGGER_WORKFLOW = """\
name: Single scalar trigger
on: workflow_dispatch
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: echo build
"""

FALSE_POSITIVE_MENTION_WORKFLOW = """\
name: Mentions issue_comment only in a step
on:
  push:
    branches: [main]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Not a trigger
        run: |
          # this script explains issue_comment: handling elsewhere
          echo "issue_comment: not a real trigger here"
"""


def test_detects_direct_block_form_issue_comment_trigger():
    guard = load_guard()
    assert guard.has_direct_issue_comment_trigger(DIRECT_LISTENER_WORKFLOW) is True


def test_detects_direct_shorthand_list_issue_comment_trigger():
    guard = load_guard()
    assert (
        guard.has_direct_issue_comment_trigger(SHORTHAND_LIST_LISTENER_WORKFLOW)
        is True
    )


def test_push_only_workflow_is_not_a_listener():
    guard = load_guard()
    assert guard.has_direct_issue_comment_trigger(PUSH_ONLY_WORKFLOW) is False


def test_single_scalar_trigger_workflow_is_not_a_listener():
    guard = load_guard()
    assert (
        guard.has_direct_issue_comment_trigger(SINGLE_SCALAR_TRIGGER_WORKFLOW)
        is False
    )


def test_mention_of_issue_comment_outside_on_block_is_not_a_false_positive():
    guard = load_guard()
    assert (
        guard.has_direct_issue_comment_trigger(FALSE_POSITIVE_MENTION_WORKFLOW)
        is False
    )


def test_iter_workflow_files_skips_disabled_and_archive_paths(tmp_path):
    guard = load_guard()
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "active.yml").write_text(PUSH_ONLY_WORKFLOW, encoding="utf-8")
    (workflows / "old.yml.disabled").write_text(
        DIRECT_LISTENER_WORKFLOW, encoding="utf-8"
    )
    archive_dir = workflows / "archive"
    archive_dir.mkdir()
    (archive_dir / "legacy.yml").write_text(
        DIRECT_LISTENER_WORKFLOW, encoding="utf-8"
    )
    historical_dir = workflows / "historical"
    historical_dir.mkdir()
    (historical_dir / "legacy2.yaml").write_text(
        DIRECT_LISTENER_WORKFLOW, encoding="utf-8"
    )

    found = {p.name for p in guard.iter_workflow_files(workflows)}

    assert found == {"active.yml"}


def test_count_listeners_reports_two_when_two_files_declare_the_trigger(tmp_path):
    guard = load_guard()
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "listener-a.yml").write_text(
        DIRECT_LISTENER_WORKFLOW, encoding="utf-8"
    )
    (workflows / "listener-b.yml").write_text(
        SHORTHAND_LIST_LISTENER_WORKFLOW, encoding="utf-8"
    )
    (workflows / "safe.yml").write_text(PUSH_ONLY_WORKFLOW, encoding="utf-8")

    count, matches = guard.count_listeners(workflows)

    assert count == 2
    assert {p.name for p in matches} == {"listener-a.yml", "listener-b.yml"}


@pytest.mark.parametrize(
    "extra_files",
    [
        {},
        {"listener-a.yml": DIRECT_LISTENER_WORKFLOW},
    ],
)
def test_main_exits_zero_when_at_most_one_listener(tmp_path, extra_files):
    guard = load_guard()
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "safe.yml").write_text(PUSH_ONLY_WORKFLOW, encoding="utf-8")
    for name, content in extra_files.items():
        (workflows / name).write_text(content, encoding="utf-8")

    exit_code = guard.main(["--workflows-dir", str(workflows)])

    assert exit_code == 0


def test_main_exits_nonzero_when_more_than_one_listener(tmp_path):
    guard = load_guard()
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "listener-a.yml").write_text(
        DIRECT_LISTENER_WORKFLOW, encoding="utf-8"
    )
    (workflows / "listener-b.yml").write_text(
        SHORTHAND_LIST_LISTENER_WORKFLOW, encoding="utf-8"
    )

    exit_code = guard.main(["--workflows-dir", str(workflows)])

    assert exit_code == 1


def test_real_repository_workflows_have_at_most_one_direct_listener():
    guard = load_guard()
    count, matches = guard.count_listeners(ROOT / ".github" / "workflows")

    assert count <= 1, f"unexpected direct issue_comment listeners: {matches}"
