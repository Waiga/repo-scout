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
        # `scanned=True` is not decoration. `USE` claims static risk is low, and
        # the only thing that can establish a low risk figure is a scan that ran
        # and found little. Without one the same inputs must not reach `USE`,
        # which the second half of this test pins.
        signals = RepoSignals(
            has_readme="present",
            has_license="present",
            has_tests="present",
            has_ci="present",
            has_releases="present",
            has_package_metadata="present",
            contributor_count=4,
        )

        score = score_repository(repo(), signals, [], "ai agent codex", scanned=True)

        self.assertGreaterEqual(score.usefulness, 75)
        self.assertLess(score.risk, 30)
        self.assertEqual(score.verdict, "USE")

        unscanned = score_repository(repo(), signals, [], "ai agent codex")

        self.assertIsNone(unscanned.verdict)

    def test_avoid_for_critical_risk(self):
        finding = Finding(
            severity="critical",
            rule="remote-shell",
            path="install.sh",
            message="Remote shell execution",
        )

        # A findings list is a scan result, so the caller that has one ran a
        # scan and says so. Handing findings over with `scanned` left False
        # describes a risk figure nothing produced.
        score = score_repository(repo(stars=3, forks=0), RepoSignals(), [finding], "ai", scanned=True)

        self.assertGreaterEqual(score.risk, 70)
        self.assertEqual(score.verdict, "AVOID")

    def test_inspect_first_for_middle_score(self):
        # Every signal is stated here, and a scan ran. A label is a claim about
        # the repository, so it is only reachable when the evidence leaves no
        # room for a different one: an unknown signal that could still turn out
        # present is room for a different one.
        signals = RepoSignals(
            has_readme="present",
            has_license="absent",
            has_tests="absent",
            has_ci="absent",
            has_releases="absent",
            has_package_metadata="present",
            contributor_count=1,
        )

        score = score_repository(repo(stars=20, forks=2), signals, [], "automation", scanned=True)

        self.assertEqual(score.verdict, "INSPECT FIRST")

    def test_unknown_evidence_is_not_penalized_as_absent(self):
        score = score_repository(repo(pushed_at=""), RepoSignals(), [], "automation")

        self.assertNotIn("No license observed", score.reasons)
        self.assertNotIn("No README observed", score.reasons)
        self.assertNotIn("Repository has not been updated in 365 days", score.reasons)


    def test_no_query_earns_no_relevance_and_claims_no_match(self):
        # `scan`, `report` and `inspect` take no query. A relevance figure for a
        # question nobody asked is an observation nobody made, and it was worth
        # up to 30 usefulness points.
        signals = RepoSignals(has_readme="present")

        unqueried = score_repository(repo(), signals, [], "")
        queried = score_repository(repo(), signals, [], "ai agent")
        unmatched = score_repository(repo(), signals, [], "zzzzqqqq")

        self.assertNotIn("Matches query terms in name or description", unqueried.reasons)
        self.assertIn("Matches query terms in name or description", queried.reasons)
        self.assertLess(unqueried.usefulness, queried.usefulness)
        # No query must earn exactly what a query that matched nothing earns:
        # nothing. Half credit for a question nobody asked was worth 15 points.
        self.assertEqual(unqueried.usefulness, unmatched.usefulness)

    def test_unknown_signals_are_not_scored_as_a_confirmed_absence(self):
        # A repository whose evidence could not be fetched and one confirmed to
        # lack those files earn the same confirmed points, because neither has
        # shown the file. What separates them is the ceiling: unknown evidence
        # could still turn out present, confirmed absence never can. Without the
        # ceiling the number reports the two as the same repository.
        unknown = RepoSignals()
        absent = RepoSignals(
            has_readme="absent",
            has_license="absent",
            has_tests="absent",
            has_ci="absent",
            has_releases="absent",
            has_package_metadata="absent",
            # Stated, because `None` means the contributor count was never
            # established and confirmed absence is the case under test here.
            contributor_count=0,
        )

        unknown_score = score_repository(repo(), unknown, [], "ai agent")
        absent_score = score_repository(repo(), absent, [], "ai agent")

        self.assertEqual(unknown_score.usefulness, absent_score.usefulness)
        self.assertGreater(unknown_score.usefulness_ceiling, unknown_score.usefulness)
        self.assertEqual(absent_score.usefulness_ceiling, absent_score.usefulness)

    def test_score_records_whether_a_static_scan_contributed_to_risk(self):
        # `risk` counts findings a static scan produced. A caller that ran no
        # scan produces the same zero as a scan that found nothing, so the score
        # has to carry which of the two happened.
        self.assertFalse(score_repository(repo(), RepoSignals(), [], "ai").static_scan)
        self.assertTrue(
            score_repository(repo(), RepoSignals(), [], "ai", scanned=True).static_scan
        )

    def test_avoid_fires_on_low_usefulness_even_when_risk_is_low(self):
        # The README tells a reader AVOID means "usefulness is low OR static risk
        # crossed the threshold". Without this, `or` could become `and` and the
        # worked example would still pass, because there both conditions hold.
        repo = RepoSummary("owner/quiet", "", "", stars=0, forks=0, pushed_at="2026-08-01T00:00:00Z")
        signals = RepoSignals(
            has_readme="present",
            has_license="absent",
            has_tests="absent",
            has_ci="absent",
            has_releases="absent",
            has_package_metadata="absent",
            contributor_count=0,
        )

        score = score_repository(repo, signals, [], "quiet package", scanned=True)

        self.assertLess(score.usefulness, 50)
        self.assertLess(score.risk, 70)
        self.assertEqual(score.verdict, "AVOID")


    def test_a_local_scan_is_not_scored_on_axes_only_github_can_answer(self):
        # `scan` and `report` build a RepoSummary from a directory on disk. It
        # has no stars, no forks, no open issue count and no push date, so those
        # fields carry placeholder zeros. Scoring the placeholders reports a
        # deficit the tool never measured as a property of the repository, and
        # it is what held every local scan below the AVOID threshold.
        signals = RepoSignals(
            has_readme="present",
            has_license="present",
            has_tests="present",
            has_ci="present",
            has_package_metadata="present",
        )
        placeholder = RepoSummary("dir", "Local repository scan", "")
        populated = RepoSummary(
            "dir", "Local repository scan", "", stars=9000, forks=900, open_issues=1,
            pushed_at="2026-09-01T00:00:00Z",
        )

        blank = score_repository(placeholder, signals, [], scanned=True, metadata=False)
        rich = score_repository(populated, signals, [], scanned=True, metadata=False)

        self.assertEqual(blank.usefulness, rich.usefulness)
        self.assertEqual(blank.usefulness_ceiling, rich.usefulness_ceiling)
        self.assertEqual(blank.risk, rich.risk)
        self.assertNotIn("Meaningful star count", rich.reasons)

    def test_no_verdict_when_the_reachable_range_spans_more_than_one_label(self):
        # The confirmed figure and the ceiling bound what usefulness could still
        # turn out to be. When those two ends fall under different labels, no
        # label is established, and printing the lower one states a negative the
        # evidence does not carry.
        signals = RepoSignals(
            has_readme="present",
            has_license="present",
            has_tests="present",
            has_ci="present",
            has_package_metadata="present",
        )

        score = score_repository(
            RepoSummary("dir", "Local repository scan", ""), signals, [], scanned=True, metadata=False
        )

        self.assertLess(score.usefulness, 50)
        self.assertGreaterEqual(score.usefulness_ceiling, 50)
        self.assertIsNone(score.verdict)

    def test_a_withheld_verdict_names_why_for_the_run_that_produced_it(self):
        # "not established" on its own is as opaque as a wrong label. The reasons
        # are read off the run, so a local scan and an unscanned lookup do not
        # give the same explanation.
        local = score_repository(
            RepoSummary("dir", "Local repository scan", ""),
            RepoSignals(has_readme="present"),
            [],
            scanned=True,
            metadata=False,
        )
        remote = score_repository(repo(), RepoSignals(), [], "ai agent")

        self.assertIsNone(local.verdict)
        self.assertTrue(any("metadata" in reason for reason in local.verdict_blockers))
        self.assertTrue(any("query" in reason for reason in local.verdict_blockers))
        self.assertFalse(any("static scan" in reason for reason in local.verdict_blockers))

        self.assertIsNone(remote.verdict)
        self.assertTrue(any("static scan" in reason for reason in remote.verdict_blockers))
        self.assertFalse(any("query" in reason for reason in remote.verdict_blockers))

    def test_an_established_verdict_carries_no_blockers(self):
        signals = RepoSignals(
            has_readme="present",
            has_license="present",
            has_tests="present",
            has_ci="present",
            has_releases="present",
            has_package_metadata="present",
            contributor_count=4,
        )

        score = score_repository(repo(), signals, [], "ai agent codex", scanned=True)

        self.assertEqual(score.verdict, "USE")
        self.assertEqual(score.verdict_blockers, [])


if __name__ == "__main__":
    unittest.main()
