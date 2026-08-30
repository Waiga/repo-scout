import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from repo_scout.models import Finding, RepoReport, RepoSignals, RepoSummary, ScoreResult
from repo_scout.report import render_html, render_markdown, write_report


def sample_report():
    return RepoReport(
        repo=RepoSummary(
            full_name="owner/repo",
            description="<script>alert(1)</script>",
            url="https://github.com/owner/repo",
            stars=10,
            forks=1,
        ),
        signals=RepoSignals(has_readme="present"),
        findings=[
            Finding(
                severity="critical",
                rule="remote-shell",
                path="install.sh",
                message="Remote shell execution",
                evidence="curl x | bash",
            )
        ],
        score=ScoreResult(usefulness=70, risk=80, verdict="AVOID", reasons=["critical risk"]),
    )


class ReportTests(unittest.TestCase):
    def test_markdown_contains_verdict_and_findings(self):
        text = render_markdown(sample_report())

        self.assertIn("# Repo Scout Report: owner/repo", text)
        self.assertIn("Verdict:** AVOID", text)
        self.assertIn("README: present", text)
        self.assertIn("remote-shell", text)

    def test_html_escapes_description(self):
        text = render_html(sample_report())

        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", text)
        self.assertNotIn("<script>alert(1)</script>", text)
        self.assertIn("README: present", text)

    def test_write_report_creates_markdown_and_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path, html_path = write_report(sample_report(), Path(tmp))

            self.assertTrue(md_path.exists())
            self.assertTrue(html_path.exists())

    def test_report_without_a_url_says_so_and_links_nowhere(self):
        # A local scan has no published URL. The row stays, so the reader is
        # told the field is empty rather than left to wonder, and the HTML emits
        # no anchor at all rather than one pointing at nothing.
        base = sample_report()
        report = RepoReport(
            repo=replace(base.repo, url=""),
            signals=base.signals,
            findings=base.findings,
            score=base.score,
        )

        markdown = render_markdown(report)
        html_text = render_html(report)

        self.assertIn("- **URL:** none recorded", markdown)
        self.assertIn("<li>URL: none recorded</li>", html_text)
        self.assertNotIn("href", html_text)


    def test_html_escapes_every_field_taken_from_a_scanned_repository(self):
        # docs/architecture.md promises escaped HTML reports. Findings carry text
        # lifted verbatim from a third party's files, so each field that reaches
        # the HTML must be escaped, not only the ones the sample happens to use.
        hostile = "<img src=x onerror=alert(1)>"
        report = replace(
            sample_report(),
            score=replace(sample_report().score, reasons=[hostile]),
            findings=[
                Finding(
                    rule=hostile,
                    severity="critical",
                    path=hostile,
                    message=hostile,
                    evidence=hostile,
                )
            ],
        )

        html_text = render_html(report)

        self.assertNotIn("<img src=x", html_text)
        self.assertGreaterEqual(html_text.count("&lt;img src=x onerror=alert(1)&gt;"), 5)


if __name__ == "__main__":
    unittest.main()
