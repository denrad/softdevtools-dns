from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from scripts.validate_pr import validate_pr_changes


class ValidatePullRequestChangesTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test")
        (self.root / "records").mkdir()
        (self.root / "records" / "existing.yaml").write_text("existing\n", encoding="utf-8")
        (self.root / "README.md").write_text("readme\n", encoding="utf-8")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=self.root, text=True, capture_output=True, check=True
        )

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "-qm", "test")

    def check(self):
        return validate_pr_changes(self.root, self.base, self.git("rev-parse", "HEAD").stdout.strip())

    def test_new_record_is_allowed(self):
        (self.root / "records" / "ivan.yaml").write_text("new\n", encoding="utf-8")
        self.commit()
        self.assertEqual(self.check(), [])

    def test_existing_record_cannot_be_modified(self):
        (self.root / "records" / "existing.yaml").write_text("changed\n", encoding="utf-8")
        self.commit()
        self.assertIn("existing.yaml", " ".join(self.check()))

    def test_existing_record_cannot_be_deleted(self):
        (self.root / "records" / "existing.yaml").unlink()
        self.commit()
        self.assertIn("existing.yaml", " ".join(self.check()))

    def test_other_paths_are_rejected(self):
        (self.root / "README.md").write_text("changed\n", encoding="utf-8")
        (self.root / "records" / "ivan.yaml").write_text("new\n", encoding="utf-8")
        self.commit()
        self.assertIn("README.md", " ".join(self.check()))

    def test_nested_record_is_rejected(self):
        (self.root / "records" / "nested").mkdir()
        (self.root / "records" / "nested" / "ivan.yaml").write_text("new\n", encoding="utf-8")
        self.commit()
        self.assertIn("nested", " ".join(self.check()))

    def test_at_least_one_record_is_required(self):
        self.assertIn("at least one", " ".join(self.check()))


if __name__ == "__main__":
    unittest.main()
