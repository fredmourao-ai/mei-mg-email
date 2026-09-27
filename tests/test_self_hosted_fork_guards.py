from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = (
    ".github/workflows/email-safety-ci.yml",
    ".github/workflows/repo-policy-guard.yml",
    ".github/workflows/repository-governance.yml",
    ".github/workflows/ai-conflict-resolver.yml",
)


class SelfHostedForkGuardRegressionTests(unittest.TestCase):
    def test_direct_pull_request_jobs_on_self_hosted_are_same_repo_guarded(self) -> None:
        for relative in WORKFLOWS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("pull_request:", text, relative)
            self.assertIn("self-hosted", text, relative)
            self.assertIn(
                "github.event.pull_request.head.repo.full_name == github.repository",
                text,
                relative,
            )

    def test_read_only_validation_checkouts_do_not_persist_credentials(self) -> None:
        for relative in (
            ".github/workflows/email-safety-ci.yml",
            ".github/workflows/repo-policy-guard.yml",
            ".github/workflows/repository-governance.yml",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("persist-credentials: false", text, relative)


if __name__ == "__main__":
    unittest.main()
