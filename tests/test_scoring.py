import unittest

from repo_scout.models import Finding, RepoSignals, RepoSummary
from repo_scout.scoring import score_repository


def repo(**overrides):
    data = {
        "full_name": "owner/ai-agent-tool",
        "description": "AI agent automation for Codex plugins",
        "url": "https://github.com/owner/ai-agent-tool",
        "stars": 500,
        "forks": 50,
        "open_issues": 5,
        "pushed_at": "2026-07-01T00:00:00Z",
    }
    data.update(overrides)
    return RepoSummary(**data)


class ScoringTests(unittest.TestCase):
    def test_use_for_relevant_healthy_low_risk_repo(self):
        signals = RepoSignals(
            has_readme="present",
            has_license="present",
            has_tests="present",
            has_ci="present",
            has_releases="present",
            has_package_metadata="present",
            contributor_count=4,
        )

        score = score_repository(repo(), signals, [], "ai agent codex")

        self.assertGreaterEqual(score.usefulness, 75)
        self.assertLess(score.risk, 30)
        self.assertEqual(score.verdict, "USE")

    def test_avoid_for_critical_risk(self):
        finding = Finding(
            severity="critical",
            rule="remote-shell",
            path="install.sh",
            message="Remote shell execution",
        )

        score = score_repository(repo(stars=3, forks=0), RepoSignals(), [finding], "ai")

        self.assertGreaterEqual(score.risk, 70)
        self.assertEqual(score.verdict, "AVOID")

    def test_inspect_first_for_middle_score(self):
        signals = RepoSignals(has_readme="present", has_package_metadata="present")

        score = score_repository(repo(stars=20, forks=2), signals, [], "automation")

        self.assertEqual(score.verdict, "INSPECT FIRST")

    def test_unknown_evidence_is_not_penalized_as_absent(self):
        score = score_repository(repo(pushed_at=""), RepoSignals(), [], "automation")

        self.assertNotIn("No license observed", score.reasons)
        self.assertNotIn("No README observed", score.reasons)
        self.assertNotIn("Repository has not been updated in 365 days", score.reasons)


    def test_avoid_fires_on_low_usefulness_even_when_risk_is_low(self):
        # The README tells a reader AVOID means "usefulness is low OR static risk
        # crossed the threshold". Without this, `or` could become `and` and the
        # worked example would still pass, because there both conditions hold.
        repo = RepoSummary("owner/quiet", "", "", stars=0, forks=0)
        signals = RepoSignals(has_readme="present")

        score = score_repository(repo, signals, [], "quiet")

        self.assertLess(score.usefulness, 50)
        self.assertLess(score.risk, 70)
        self.assertEqual(score.verdict, "AVOID")


if __name__ == "__main__":
    unittest.main()
