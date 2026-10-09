from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from scripts.validate import parse_record, validate_records


VALID = """subdomain: ivan
type: CNAME
target: ivan123.github.io
repository: https://github.com/ivan123/my-lab-site
"""


class ParseRecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ivan.yaml"

    def parse(self, content: str):
        self.path.write_text(content, encoding="utf-8")
        return parse_record(self.path)

    def test_valid_record(self):
        record, errors = self.parse(VALID)
        self.assertEqual(errors, [])
        self.assertEqual(record["subdomain"], "ivan")

    def test_malformed_yaml(self):
        record, errors = self.parse("subdomain: [unterminated")
        self.assertIsNone(record)
        self.assertTrue(errors)

    def test_duplicate_key(self):
        record, errors = self.parse(VALID + "subdomain: stolen\n")
        self.assertIsNone(record)
        self.assertIn("duplicate", " ".join(errors).lower())

    def test_multiple_documents(self):
        record, errors = self.parse(VALID + "---\nsubdomain: other\n")
        self.assertIsNone(record)
        self.assertTrue(errors)

    def test_unknown_and_missing_fields(self):
        content = VALID.replace("repository: https://github.com/ivan123/my-lab-site\n", "extra: value\n")
        record, errors = self.parse(content)
        self.assertIsNone(record)
        self.assertIn("repository", " ".join(errors))
        self.assertIn("extra", " ".join(errors))

    def test_non_string_field(self):
        record, errors = self.parse(VALID.replace("type: CNAME", "type: [CNAME]"))
        self.assertIsNone(record)
        self.assertIn("type", " ".join(errors))

    def test_alias_is_rejected(self):
        content = VALID.replace("subdomain: ivan", "subdomain: &name ivan").replace(
            "type: CNAME", "type: *name"
        )
        record, errors = self.parse(content)
        self.assertIsNone(record)
        self.assertIn("alias", " ".join(errors).lower())

    def test_oversized_file(self):
        record, errors = self.parse(VALID + " " * 8192)
        self.assertIsNone(record)
        self.assertIn("size", " ".join(errors).lower())


class ValidateRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "records").mkdir()
        (self.root / "config").mkdir()
        (self.root / "config" / "reserved-names.txt").write_text(
            "# Teacher-owned names\nwww\nadmin\n", encoding="utf-8"
        )

    def write(self, filename: str, content: str = VALID):
        (self.root / "records" / filename).write_text(content, encoding="utf-8")

    def test_valid_tree_and_empty_tree(self):
        self.assertEqual(validate_records(self.root), [])
        self.write("ivan.yaml")
        self.assertEqual(validate_records(self.root), [])

    def test_reserved_name(self):
        self.write("www.yaml", VALID.replace("subdomain: ivan", "subdomain: www"))
        self.assertIn("reserved", " ".join(validate_records(self.root)).lower())

    def test_invalid_subdomain(self):
        self.write("bad.yaml", VALID.replace("subdomain: ivan", "subdomain: a.b"))
        self.assertIn("subdomain", " ".join(validate_records(self.root)))

    def test_subdomain_fits_github_pages_https_name_limit(self):
        allowed = "a" * 47  # 47 + len(".softdevtools.ru") == 63
        rejected = "a" * 48
        self.write(f"{allowed}.yaml", VALID.replace("subdomain: ivan", f"subdomain: {allowed}"))
        self.assertEqual(validate_records(self.root), [])
        (self.root / "records" / f"{allowed}.yaml").unlink()
        self.write(f"{rejected}.yaml", VALID.replace("subdomain: ivan", f"subdomain: {rejected}"))
        self.assertIn("47", " ".join(validate_records(self.root)))

    def test_uppercase_subdomain(self):
        self.write("ivan.yaml", VALID.replace("subdomain: ivan", "subdomain: Ivan"))
        self.assertIn("lowercase", " ".join(validate_records(self.root)).lower())

    def test_invalid_target(self):
        self.write("ivan.yaml", VALID.replace("ivan123.github.io", "example.com"))
        self.assertIn("target", " ".join(validate_records(self.root)))

    def test_github_username_length_limit(self):
        for length in (39, 40):
            with self.subTest(length=length):
                username = "a" * length
                content = VALID.replace("ivan123.github.io", f"{username}.github.io").replace(
                    "github.com/ivan123/", f"github.com/{username}/"
                )
                self.write("ivan.yaml", content)
                errors = validate_records(self.root)
                if length == 39:
                    self.assertEqual(errors, [])
                else:
                    self.assertIn("target", " ".join(errors))

    def test_repository_owner_must_match_target(self):
        self.write("ivan.yaml", VALID.replace("github.com/ivan123/", "github.com/other/"))
        self.assertIn("owner", " ".join(validate_records(self.root)).lower())

    def test_duplicate_subdomain(self):
        self.write("ivan.yaml")
        self.write("other.yaml")
        self.assertIn("duplicate", " ".join(validate_records(self.root)).lower())

    def test_filename_must_match_subdomain(self):
        self.write("other.yaml")
        self.assertIn("filename", " ".join(validate_records(self.root)).lower())

    def test_missing_reserved_names_configuration(self):
        (self.root / "config" / "reserved-names.txt").unlink()
        self.write("ivan.yaml")
        self.assertIn("reserved-names.txt", " ".join(validate_records(self.root)))

    def test_unexpected_file_in_records(self):
        self.write("notes.txt", "hello")
        self.assertIn("notes.txt", " ".join(validate_records(self.root)))

    def test_symlink_is_rejected(self):
        source = self.root / "outside.yaml"
        source.write_text(VALID, encoding="utf-8")
        (self.root / "records" / "ivan.yaml").symlink_to(source)
        self.assertIn("symlink", " ".join(validate_records(self.root)).lower())

    def test_records_directory_symlink_is_rejected(self):
        (self.root / "records").rmdir()
        outside = self.root / "outside"
        outside.mkdir()
        (self.root / "records").symlink_to(outside, target_is_directory=True)
        self.assertIn("symlink", " ".join(validate_records(self.root)).lower())

    def test_cli_reports_success_and_failure(self):
        project = Path(__file__).resolve().parents[1]
        command = [sys.executable, "-m", "scripts.validate", str(self.root)]
        success = subprocess.run(command, cwd=project, capture_output=True, text=True)
        self.assertEqual(success.returncode, 0)
        self.assertIn("valid", success.stdout.lower())

        self.write("ivan.yaml", VALID.replace("type: CNAME", "type: TXT"))
        failure = subprocess.run(command, cwd=project, capture_output=True, text=True)
        self.assertEqual(failure.returncode, 1)
        self.assertIn("records/ivan.yaml", failure.stdout)
        self.assertIn("CNAME", failure.stdout)


if __name__ == "__main__":
    unittest.main()
