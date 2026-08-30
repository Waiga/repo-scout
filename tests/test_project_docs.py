import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_DOCS = (
    "README.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "docs/architecture.md",
    "docs/limitations.md",
    "docs/roadmap.md",
)

# The public prose documents plus the community-health templates. This is NOT
# every tracked file: the source, the tests, the packaging metadata, `LICENSE`,
# `.gitignore` and the workflow definition are out of scope for this check. The
# templates are included because they are the likeliest place for a reproduction
# path or a contact address to be pasted in later.
PUBLIC_SURFACE = PUBLIC_DOCS + (
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/pull_request_template.md",
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class ProjectDocsTests(unittest.TestCase):
    def test_required_public_documents_exist(self):
        required = [
            "README.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md", "SUPPORT.md",
            "docs/architecture.md", "docs/limitations.md", "docs/roadmap.md",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
            ".github/ISSUE_TEMPLATE/feature_request.yml",
            ".github/pull_request_template.md",
        ]
        for relative in required:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_readme_and_contributing_use_verified_commands(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("python3 -m pip install --no-deps .", readme)
        self.assertIn("python3 -m unittest discover -s tests -v", readme)
        self.assertIn("python3 -m unittest discover -s tests -v", contributing)
        self.assertIn("static evidence", readme.lower())
        self.assertIn("does not prove", readme.lower())

    def test_public_docs_have_no_unresolved_markers(self):
        forbidden = ("TB" + "D", "TO" + "DO", "FIX" + "ME", "your-email", "example.com")
        for relative in PUBLIC_SURFACE:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertFalse(any(marker in text for marker in forbidden))

    def test_public_docs_leak_no_local_paths_or_addresses(self):
        for relative in PUBLIC_SURFACE:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertNotIn("/Users/", text)
                self.assertNotIn("/home/", text)
                self.assertIsNone(EMAIL_RE.search(text))

    def test_readme_defines_every_verdict_label(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for label in ("USE", "INSPECT FIRST", "AVOID"):
            with self.subTest(label=label):
                self.assertIn(f"`{label}`", readme)

    def test_readme_keeps_its_verification_and_adoption_disclosures(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        # The point of this test is that honest limitations cannot be quietly
        # deleted. When a limitation stops being true it is REPLACED here by the
        # one that succeeded it, never simply dropped. The matrix has now run, so
        # "Python 3.14 only" and "has not run" are gone; what remains unverified
        # is everything the matrix does not cover.
        self.assertIn("no upper", readme)
        self.assertIn("Windows is untested", readme)
        self.assertIn("no adoption or contribution history", readme)


if __name__ == "__main__":
    unittest.main()
