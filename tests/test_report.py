import re
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from repo_scout.models import Finding, RepoReport, RepoSignals, RepoSummary, ScoreResult
from repo_scout.report import render_html, render_markdown, verdict_text, write_report


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
        score=ScoreResult(
            usefulness=70,
            risk=80,
            verdict="AVOID",
            reasons=["critical risk"],
            static_scan=True,
            usefulness_ceiling=70,
        ),
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


    def test_report_without_a_static_scan_reports_unknown_not_absence(self):
        # `inspect` never opens a file, so its findings list is empty because
        # nothing was examined, not because nothing was found. Rendering that as
        # "No static risk findings." and "Risk: 0/100" turns unknown evidence
        # into a confirmed absence in the artifact the README says is shared.
        report = replace(
            sample_report(),
            findings=[],
            score=replace(sample_report().score, risk=0, static_scan=False),
        )

        markdown = render_markdown(report)
        html_text = render_html(report)

        for text in (markdown, html_text):
            with self.subTest(rendered=text[:20]):
                self.assertNotIn("No static risk findings", text)
                self.assertIsNone(re.search(r"Risk:(\*\*)? \d+/100", text))
                self.assertIn("No static scan was performed", text)
                self.assertIn("Risk:", text)

    def test_report_with_a_scan_and_no_findings_still_says_it_found_none(self):
        # The opposite case must keep its plain meaning: a scan ran and turned
        # nothing up.
        report = replace(
            sample_report(),
            findings=[],
            score=replace(sample_report().score, risk=0, static_scan=True),
        )

        markdown = render_markdown(report)
        html_text = render_html(report)

        for text in (markdown, html_text):
            with self.subTest(rendered=text[:20]):
                self.assertIn("No static risk findings", text)
                self.assertNotIn("No static scan was performed", text)

    def test_unknown_evidence_widens_the_usefulness_figure(self):
        # A confirmed 70 and a 70 that could still be an 88 are different
        # readings. The report must not print them the same way.
        report = replace(
            sample_report(),
            score=replace(sample_report().score, usefulness=70, usefulness_ceiling=88),
        )

        markdown = render_markdown(report)
        html_text = render_html(report)

        for text in (markdown, html_text):
            with self.subTest(rendered=text[:20]):
                self.assertIn("70/100", text)
                self.assertIn("88/100", text)

    def test_every_report_carries_the_limitation_it_is_shared_with(self):
        # README says a report is written to be shared. The recipient sees a bold
        # verdict and two scores; the framing that makes them readable lives in
        # the README, which does not travel with the file. It travels here.
        for text in (render_markdown(sample_report()), render_html(sample_report())):
            with self.subTest(rendered=text[:20]):
                self.assertIn("does not prove", text)
                self.assertIn("docs/limitations.md", text)

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


    def test_a_report_without_a_verdict_says_so_and_gives_the_reasons(self):
        # A withheld verdict must not leave the row blank or fall back to the
        # most negative label. The row stays, says the verdict is not
        # established, and carries the reasons that applied to this run.
        report = replace(
            sample_report(),
            score=replace(
                sample_report().score,
                verdict=None,
                verdict_blockers=["no query was given", "repository metadata is unavailable"],
            ),
        )

        for text in (render_markdown(report), render_html(report)):
            with self.subTest(rendered=text[:20]):
                self.assertIn("not established", text)
                self.assertIn("no query was given", text)
                self.assertIn("repository metadata is unavailable", text)
                self.assertNotIn("AVOID", text)

    def test_verdict_text_passes_an_established_label_through_unchanged(self):
        self.assertEqual(verdict_text(sample_report().score), "AVOID")


if __name__ == "__main__":
    unittest.main()
