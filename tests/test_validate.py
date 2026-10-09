from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scripts.validate import parse_record


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


if __name__ == "__main__":
    unittest.main()
