# Roadmap

The next contribution areas come from observed V0.1 limits. Nothing here is a
commitment to a date.

## Known gaps with a clear fix

These are specific defects and shortfalls found during internal review of V0.1. Each is
small, self-contained, and a reasonable first contribution.

1. **Repository names may start with a non-alphanumeric character.** `repo_scout.cli`
   accepts any component matching `[A-Za-z0-9_.-]+`, while GitHub requires a name to
   begin with an alphanumeric character. Enforcing the real rule also rejects
   option-shaped input such as `--upload-pack/x` before it reaches the Git command line.
2. **Clone failures other than `CalledProcessError` are unhandled.** `download` catches
   only a non-zero Git exit status. Preparing the destination raises an uncaught
   `OSError` and exits with a traceback instead of the controlled exit code 1 that the
   other failure paths use: `PermissionError` on an unwritable destination,
   `FileExistsError` when the downloads directory is itself a file, and
   `NotADirectoryError` when a parent component is a file.
3. **Repository component length is unbounded.** GitHub limits an owner name to 39
   characters and a repository name to 100. Repo Scout accepts arbitrarily long
   components and only discovers the problem when the request fails.
4. **The workflow definition uses floating action tags and no run controls.**
   `.github/workflows/ci.yml` references mutable major version tags rather than commit
   SHAs, and it has no `concurrency` group or trigger path filters, so superseded runs
   are never canceled and every push runs the full matrix.
5. **The declared Python range is wider than the tested one.** `pyproject.toml` declares
   `requires-python = ">=3.11"` with no upper bound, while the classifiers and the
   workflow matrix stop at 3.14. The project therefore advertises support for versions
   nothing exercises.
6. **`contributor_count` is never populated.** `RepoSignals` carries the field and
   `repo_scout.scoring` gives it a fifth of the credibility component, but no V0.1
   command fetches it: `search` builds an empty `RepoSignals`, `_fetch_signals` does not
   set it, and a local scan has no contributor list to read. It is therefore always
   unknown, which now widens the usefulness ceiling instead of silently subtracting
   points, but the underlying gap is that the GitHub contributors endpoint is not
   called. Populating it where the data is genuinely available is a self-contained
   change.
7. **`USE` is unreachable through any V0.1 command.** The label needs a query, which
   only `search` takes, and an established low risk, which only a static scan produces.
   No command does both: `search` and `inspect` open no file, so risk stays unknown,
   while `scan` and `report` take no query, so relevance is not scored and the confirmed
   figure tops out at the remaining 70. The README states this under Verdicts. The
   thresholds are deliberately **not re-tuned** to make the label reachable: lowering the
   bar would award `USE` on evidence no command gathered, which is the defect the
   withheld verdict was added to remove. The fix is a command that runs a query and a
   static scan over the same repository, so the label rests on more evidence rather than
   on a shorter scale.

## Closed in V0.1

These were listed above and have since been fixed. They are kept so the record is
honest rather than silently tidied.

- **A local scan claimed a query match when no query was given.** `scan`, `report` and
  `inspect` take no query, yet each passed a name back into `score_repository` as one, so
  relevance came out at 1.0 and every report opened its evidence list with `Matches query
  terms in name or description`. Relevance is now skipped, not scored, when there is no
  query, and the line is gone. The 30 relevance points are unavailable to those commands
  as a result: an unqueried report is scored out of the remaining 70, which is under the
  75 `USE` requires. The README no longer quotes that ceiling; it explains the verdict
  gate under Verdicts, and gap 7 above owns the unreachable label.
- **Every local scan returned `AVOID`.** `scan` and `report` could produce no other
  verdict for any input, including a directory with a README, a LICENSE, package
  metadata, tests and a CI workflow and no static findings. Relevance needs a query,
  credibility needs published repository metadata, and freshness and releases need a
  push date and a release list, so the reachable local total sat under the 50-point
  `AVOID` threshold. A local scan is no longer scored on axes only GitHub can answer,
  and a verdict is now emitted only when the confirmed usefulness figure and the ceiling
  fall under the same label. Where they do not, the report says the verdict is not
  established and names the reasons for that run, in the Markdown file, the HTML file
  and the terminal.
- **Automated checks tested the working tree, not the installed package.**
  `.github/workflows/ci.yml` now runs the installed console script from a neutral
  working directory after installing. That workflow ran on GitHub Actions against the
  published v0.1 tree, commit `a14de73` of 30 August 2026, and passed on Python 3.11,
  3.12, 3.13 and 3.14 on Linux. That run, and the result for any later commit, is
  recorded in the repository's Actions history rather than in a checkout, which carries
  the workflow definition and not its results.
- **The packaging ignore test covered the rules and never the index.** It began by
  matching three of the ignore patterns as strings;
  `tests/test_package_metadata.py` now asks `git check-ignore` about every pattern
  `.gitignore` declares, so an appended negation cannot weaken the contract. That is
  still only the rule, and a rule does not untrack a file already in the index: four
  private local planning files were tracked from before the pattern existed, and the
  pattern probe could not see them. They are untracked, and a second check asks
  `git ls-files` directly whether anything under a private-material pattern is
  tracked in the current index, which is the outcome rather than the rule. That
  check answers for the index only, at the moment it runs: the four documents it was
  written after finding remain, permanently, in the ancestor commits that first
  tracked them, and passing it never means this history is safe to push. Publishing
  this project assembles a fresh clean tree instead of pushing this history.
- **The suite failed outside a Git working tree.** Running it from a repository archive
  gave eight errors, because the ignore contract asks `git check-ignore` and there is no
  working tree to answer. It now skips that one check with a reason, and still fails when
  Git is present and a pattern is unguarded.
- **Reports embedded the scanned absolute path.** Markdown and HTML output recorded the
  full local path of the scanned directory, which a shared report would disclose. The
  target is now identified by name.
- **The global and subcommand options had no `--help` text.** `--reports-dir`, `--limit`
  and `--downloads-dir` now describe themselves and show their defaults.

## Larger areas

1. Add fixture-aware evidence so reports distinguish test examples from likely runtime paths.
2. Add an optional authenticated GitHub client without making tokens mandatory.
3. Add history-aware provenance and secret review as a separate, explicit command.
4. Add signed machine-readable report output with a stable schema.
5. Benchmark false-positive and false-negative behavior on a documented public corpus.

Each area requires an issue with a user problem, acceptance criteria, tests, and an
explicit statement of what remains outside scope.
