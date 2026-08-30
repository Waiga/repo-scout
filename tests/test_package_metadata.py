import subprocess
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

WORKFLOW = Path(".github") / "workflows" / "ci.yml"

# The entire workflow, verbatim. Pinning the whole file rather than a few lines
# inside it is the only version of this check with no heuristic left: it cannot
# be defeated by a condition on the job, a changed trigger, an alternative
# spelling of a key, or anything else, because every difference in content
# fails. The single exception is the line ending, which `read_text` normalises,
# so a CRLF checkout passes; that difference cannot change what a runner does.
#
# Five rounds of review established why it has to be this blunt. Each earlier
# version inferred the property - first by matching a line, then by parsing the
# YAML and the shell, then by scanning for an `if:` key - and each was defeated
# by a formulation the previous round had not imagined, twice in the direction
# of passing a workflow that had been silently disabled.
EXPECTED_WORKFLOW = """\
name: CI

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: python -m pip install --no-deps .
      - run: cd "$RUNNER_TEMP" && repo-scout --help
      - run: PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
"""

# Every pattern `.gitignore` declares, paired with a path that only that pattern
# can ignore. The first five keep scan output, cached API responses and cloned
# third-party code out of a repository being prepared for publication; the last
# three keep local build artifacts out. Order matches the file, because the
# completeness check below compares the two directly.
IGNORE_CONTRACT = (
    (".repo-scout-cache/", ".repo-scout-cache/probe.json"),
    ("downloads/", "downloads/probe-repo/README.md"),
    ("reports/", "reports/probe-report.md"),
    ("__pycache__/", "repo_scout/__pycache__/probe.txt"),
    ("*.pyc", "probe.pyc"),
    ("build/", "build/probe.txt"),
    ("dist/", "dist/probe.txt"),
    ("*.egg-info/", "repo_scout.egg-info/PKG-INFO"),
)


def working_tree_skip_reason():
    """Why the ignore behaviour cannot be checked here, or `None` when it can.

    The behaviour check below asks `git check-ignore`, which needs a Git working
    tree and exits 128 without one. An extracted source tarball or sdist carries
    no Git data, so the honest answer there is that the contract went unchecked,
    not that it was broken. Git is asked the question directly: a reason is
    returned only when Git cannot be run at all, or when Git does not answer
    `true`. Nothing here reads or parses anything, and every failure of
    `check-ignore` itself still reaches `check_ignore`, which raises.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return (
            f"git could not be run ({exc}), so the .gitignore contract is "
            "unchecked here; run the suite from a Git checkout to check it"
        )
    if result.returncode != 0 or result.stdout.strip() != "true":
        return (
            "this checkout is not a Git working tree, so git check-ignore cannot "
            "answer and the .gitignore contract is unchecked here; run the suite "
            "from a Git checkout to check it"
        )
    return None


def check_ignore(probe):
    """Ask git which ignore rule covers `probe`, if any.

    Returns `(returncode, source, pattern)`. `git check-ignore -v` prints
    `<source>:<line>:<pattern>` and the pathname, tab separated; a non-zero
    return code means the path is not ignored at all.
    """
    result = subprocess.run(
        ["git", "check-ignore", "-v", "--no-index", "--", probe],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode not in (0, 1):
        raise AssertionError(
            f"git check-ignore could not answer for {probe!r} "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )
    if result.returncode != 0:
        return result.returncode, "", ""
    source, _line, pattern = result.stdout.split("\t", 1)[0].split(":", 2)
    return result.returncode, source, pattern


class PackageMetadataTests(unittest.TestCase):
    # unittest truncates a diff over 640 characters, and the workflow contract
    # below produces a longer one for most real edits, so the failure would say
    # only "Diff is N characters long" exactly when a contributor needs to see
    # what moved. The comments here promise a diff; this is what delivers it.
    maxDiff = None

    def test_public_package_contract_is_complete(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(data["build-system"]["build-backend"], "setuptools.build_meta")
        self.assertEqual(data["project"]["readme"], "README.md")
        self.assertEqual(data["project"]["license"], "MIT")
        self.assertEqual(data["project"]["requires-python"], ">=3.11")
        self.assertEqual(data["project"]["scripts"]["repo-scout"], "repo_scout.cli:main")
        self.assertTrue((ROOT / "LICENSE").is_file())

    def test_every_declared_ignore_pattern_is_guarded(self):
        # Completeness only: a pattern added to `.gitignore` without a probe
        # here, or a negation line such as `!reports/` appended to the end,
        # fails this before it can quietly weaken the contract below.
        declared = [
            line.strip()
            for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        self.assertEqual(declared, [pattern for pattern, _probe in IGNORE_CONTRACT])

    def test_scan_output_and_build_artifacts_are_ignored(self):
        # Skips, rather than failing, where there is no Git to ask. It never
        # skips because a pattern is missing: with a working tree present every
        # subtest below runs, and any unguarded pattern fails.
        reason = working_tree_skip_reason()
        if reason is not None:
            self.skipTest(reason)

        # Behaviour, asked of git rather than matched against the file text: a
        # trailing negation would satisfy a string search while un-ignoring the
        # path, and a pattern inherited from the user's global excludes file
        # would ignore the path without the repository guaranteeing anything.
        for pattern, probe in IGNORE_CONTRACT:
            with self.subTest(pattern=pattern):
                returncode, source, matched = check_ignore(probe)

                self.assertEqual(returncode, 0, f"{probe} is not ignored by anything")
                self.assertEqual(source, ".gitignore", f"{probe} ignored by {source!r}")
                self.assertEqual(matched, pattern)

    def test_ci_workflow_matches_the_pinned_contract(self):
        # `python -m unittest` puts the process working directory at
        # `sys.path[0]`, so a suite run from the checkout imports the working
        # tree and never touches the installed wheel. CI must additionally run
        # the generated console script from somewhere the source is not, which
        # `EXPECTED_WORKFLOW` does at the step after the install.
        #
        # This is a tripwire, not a workflow analyser. ANY edit to the workflow
        # fails it on purpose, including a correct one: the fix is to update
        # `EXPECTED_WORKFLOW` in the same commit, and the failure prints the
        # diff. It cannot see anything that happens on a runner, because this
        # workflow has never run.
        actual = (ROOT / WORKFLOW).read_text(encoding="utf-8")

        self.assertEqual(
            actual,
            EXPECTED_WORKFLOW,
            f"{WORKFLOW} differs from the pinned contract; if the change is "
            "intended, update EXPECTED_WORKFLOW in this test in the same commit",
        )


if __name__ == "__main__":
    unittest.main()
