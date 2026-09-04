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

# The public prose documents plus the community-health templates and
# `.gitignore`. This is NOT every tracked file: the source, the tests, the
# packaging metadata, `LICENSE` and the workflow definition are out of scope for
# this check. The templates are included because they are the likeliest place
# for a reproduction path or a contact address to be pasted in later.
# `.gitignore` is included because it is a tracked file whose comments describe
# what is being kept out of the repository, which is a description of private
# material sitting on the public surface.
PUBLIC_SURFACE = PUBLIC_DOCS + (
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/pull_request_template.md",
    ".gitignore",
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# A sentence denying that the CI workflow ran. Kept deliberately loose about
# the wording and strict about the shape: something naming the workflow, the
# matrix or CI, followed closely by a negated past tense of running.
#
# This is a tripwire for the one regression already seen (`cd264db`), not a
# proof that every CI claim in the docs is true and not a parser of English.
# It is stricter than the two literal strings it replaced, but a denial
# phrased around it -- "did not run", "has never happened", "remains
# unexecuted" -- passes unflagged, and `COMMIT_RE` below accepts any
# backticked a-f hex-looking word as a commit anchor. Widening the regex to
# close those gaps is not the goal: a regex cannot own English, and each
# earlier attempt to make this kind of check exhaustive (see the Task 4b
# lesson) was defeated by a phrasing the previous version had not imagined.
# This catches the known regression shape and says nothing stronger.
CI_RUN_DENIAL_RE = re.compile(
    r"\b(workflow|matrix|CI)\b[^.]{0,60}?\b(has|have|had|was|were|is|are)\s+"
    r"(not|never)\s+(yet\s+)?(been\s+)?(run|ran|executed|exercised)\b",
    re.IGNORECASE,
)

# A commit named the way these documents name one: seven to forty hex digits in
# backticks. Requiring the backticks fails closed, since a commit written
# without them reads as an ordinary word and would silently satisfy the check.
COMMIT_RE = re.compile(r"`[0-9a-f]{7,40}`")


def unanchored_ci_run_denials(text):
    """Sentences that deny CI ran without saying what it has not run against.

    The matrix did run, against the published v0.1 tree, so an unqualified
    denial is false. A denial is not false in itself, though: edit `ci.yml` and
    "that workflow has not run" becomes the honest disclosure for the new
    definition. What distinguishes the two is whether the sentence says which
    commit it is about, so that is what is required -- the claim, rather than a
    list of forbidden strings that any rewording steps around and that bans a
    future true sentence along with the false one.

    This still forbids only the shapes `CI_RUN_DENIAL_RE` recognises, not
    every way of writing an unqualified denial in English; see the comment on
    that pattern above.
    """
    flat = " ".join(text.split())
    return [
        sentence
        for sentence in re.split(r"(?<=\.)\s+", flat)
        if CI_RUN_DENIAL_RE.search(sentence) and not COMMIT_RE.search(sentence)
    ]


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

    def test_readme_documents_the_outcome_where_no_label_is_established(self):
        # A reader who sees "not established" in a report has to be able to find
        # out what it means, and a reader deciding whether to run the tool has to
        # know it is a normal outcome rather than a failure. The README is the
        # only place that can say so.
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        limitations = (ROOT / "docs" / "limitations.md").read_text(encoding="utf-8")

        self.assertIn("not established", readme)
        self.assertIn("not established", limitations)

    def test_readme_keeps_its_verification_and_adoption_disclosures(self):
        # This test exists so an honest limitation cannot be quietly dropped. A
        # limitation that stops being true is REPLACED here by its successor,
        # never simply deleted. Three have now been replaced: "Python 3.14
        # only", "has not run", and "this development tree is ahead of the
        # published one and has not itself been through CI".
        #
        # The third is the reason for this revision. It was true when written,
        # but it is a claim about how this tree stands relative to the published
        # one, and publishing this tree falsifies it: the tree stops being ahead
        # of the published one because it becomes the published one, and the
        # workflow runs on the push. Pinning it here guaranteed the README would
        # be wrong the moment a push succeeded, which is the same shape as the
        # earlier two -- a statement true at one moment pinned as if it were
        # true in general.
        #
        # What is pinned now is what does not vary with a commit: the matrix
        # covers 3.11 through 3.14 on Linux, `requires-python = ">=3.11"` has no
        # upper bound so anything above 3.14 is unexercised, the workflow's only
        # `runs-on` is `ubuntu-latest` so Windows is untested, and the authority
        # for whether CI passed is the repository's Actions history, per commit,
        # rather than this file. The README asserts no CI result other than the
        # recorded v0.1 run, which is a dated past event and cannot go stale.
        # Flattened the way `unanchored_ci_run_denials` flattens its input: a
        # phrase that happens to straddle a line wrap is still the same claim,
        # and the negative assertion below would otherwise be silently
        # satisfied by a reflow rather than by a removal.
        readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())

        self.assertIn("no upper bound", readme)
        self.assertIn("unexercised", readme)
        self.assertIn("Windows is untested", readme)
        self.assertIn("Actions history", readme)
        self.assertIn("no adoption or contribution history", readme)

        # A tripwire for the one wording this revision removed, not a parser of
        # English: a reworded comparison between this tree and the published one
        # passes unflagged. It is here because that comparison is the thing that
        # keeps going stale, and the README is meant to make none.
        self.assertNotIn("ahead of the published", readme)

    def test_roadmap_records_the_unreachable_use_label(self):
        # A known structural gap gets fixed or gets a roadmap line. `USE` cannot
        # be reached by any V0.1 command, which the README states; the roadmap
        # is where the gap is owned, and where the decision not to close it by
        # moving the thresholds is recorded so a later contributor does not
        # quietly do it.
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        self.assertIn("`USE` is unreachable through any V0.1 command", roadmap)
        self.assertIn("not re-tuned", roadmap)

    def test_a_denial_that_ci_ran_is_recognised_only_when_it_names_no_commit(self):
        # The detector itself, on fixtures, so the check over the real
        # documents below cannot pass merely because it recognises nothing.
        unqualified = "The workflow has not run."
        anchored = "That workflow has not run against `b1c2d3e`."
        unrelated = (
            "This development tree is ahead of the published one and has not "
            "itself been through CI, so nothing here is matrix-tested."
        )

        self.assertEqual(unanchored_ci_run_denials(unqualified), [unqualified])
        self.assertEqual(unanchored_ci_run_denials(anchored), [])
        self.assertEqual(unanchored_ci_run_denials(unrelated), [])

    def test_public_docs_anchor_any_denial_that_ci_ran_to_a_commit(self):
        # The matrix did run, against the published v0.1 tree. When the README
        # briefly said otherwise, two other documents said it too, so the claim
        # is guarded across the public surface rather than in the README alone.
        for relative in PUBLIC_DOCS:
            text = (ROOT / relative).read_text(encoding="utf-8")
            with self.subTest(relative=relative):
                self.assertEqual(
                    unanchored_ci_run_denials(text),
                    [],
                    "a statement that CI has not run must name the commit it "
                    "has not run against; unqualified, it contradicts the "
                    "matrix run recorded in the published repository",
                )


if __name__ == "__main__":
    unittest.main()
