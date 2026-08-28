import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).parents[1] / ".github" / "scripts" / "ai_conflict_resolver.py"
spec = importlib.util.spec_from_file_location("ai_conflict_resolver", MODULE_PATH)
resolver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolver)


class ConflictResolverSafetyTests(unittest.TestCase):
    def test_protected_paths_are_blocked(self):
        blocked = [
            ".env",
            ".github/workflows/send-production.yml",
            "migrations/20260827_drop.sql",
            "certs/private.key",
            "src/auth/token.py",
        ]
        for path in blocked:
            with self.subTest(path=path):
                self.assertTrue(resolver.is_protected_path(path))

    def test_regular_source_path_is_allowed(self):
        self.assertFalse(resolver.is_protected_path("src/reporting/formatter.py"))

    def test_conflict_markers_are_rejected(self):
        self.assertTrue(resolver.has_conflict_markers("a\n<<<<<<< ours\nb\n=======\nc\n>>>>>>> theirs\n"))
        self.assertFalse(resolver.has_conflict_markers("a\nb\nc\n"))

    def test_model_json_requires_matching_path_and_content(self):
        raw = '{"path":"src/a.py","content":"print(1)\\n"}'
        self.assertEqual("print(1)\n", resolver.parse_model_content(raw, "src/a.py"))
        with self.assertRaises(ValueError):
            resolver.parse_model_content(raw, "src/b.py")

    def test_candidate_rejects_empty_or_large_deletion(self):
        original = "\n".join(str(i) for i in range(100)) + "\n"
        with self.assertRaises(ValueError):
            resolver.validate_candidate("src/a.py", original, "")
        with self.assertRaises(ValueError):
            resolver.validate_candidate("src/a.py", original, "1\n")

    def test_candidate_accepts_small_safe_resolution(self):
        original = "a\nb\nc\n"
        candidate = "a\nb2\nc\n"
        self.assertEqual(candidate, resolver.validate_candidate("src/a.py", original, candidate))


if __name__ == "__main__":
    unittest.main()