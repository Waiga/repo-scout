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
6. **A local scan claims a query match when no query was given.** `scan` and `report`
   take no query, but `repo_scout/cli.py:158` passes the scanned directory's name to
   `score_repository` as the search query. `repo_scout/scoring.py:106` then matches that
   name against the repository name it was taken from, relevance comes out at 1.0, and
   every local scan opens its evidence list with `Matches query terms in name or
   description` and collects the relevance points behind it. The line appears in the
   README's offline worked example, which is the first output a new user sees. Deciding
   what an unqueried scan should score is the substance of the fix; the reported evidence
   line and the score must agree with whatever is chosen.

## Closed in V0.1

These were listed above and have since been fixed. They are kept so the record is
honest rather than silently tidied.

- **Automated checks tested the working tree, not the installed package.**
  `.github/workflows/ci.yml` now runs the installed console script from a neutral
  working directory after installing. That workflow has not run, so this is a
  change to the definition rather than a demonstrated result.
- **The packaging ignore test covered only three of the eight ignore patterns.**
  `tests/test_package_metadata.py` now asserts all eight by asking `git check-ignore`
  rather than matching strings, so an appended negation cannot weaken the contract.
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
