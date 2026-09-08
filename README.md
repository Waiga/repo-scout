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

A report ends in one of three labels, or in no label at all. The labels are
prioritization labels for human review, not safety judgments.

- `USE`: useful signals are strong and static risk signals are low.
- `INSPECT FIRST`: promising, but something needs a person to look at it.
- `AVOID`: usefulness is low or static risk crossed the threshold.
- `not established`: the evidence gathered does not single out any of the three. The
  report names the parts of the scale that were missing for that run, and the Signals
  and Evidence sections are what to read instead.

A label is a claim about the repository, so one is printed only when the evidence
leaves no room for a different one. Usefulness is reported as a confirmed figure and a
ceiling: the confirmed figure counts established evidence, and the ceiling adds
everything that was looked for and could not be established. Both ends have to fall
under the same label, otherwise no label is printed.

Both figures are percentages of **the part of the scale that run could observe**, not of
a fixed 100, and the report says which part that was. This matters because the commands
observe different things. `search` takes a query and scores relevance; `scan` and
`report` take a path and score neither relevance nor the published metadata a directory
does not carry. Scoring every run out of the same fixed 100 charged each command for the
axes it structurally cannot read, which is the run's own blind spot reported as a
shortfall of the repository.

In v0.1 it did exactly that, and the consequence was not a rounding error. A local scan
could confirm at most 36 of 100 points however good the repository was, so the confirmed
end was permanently below the `AVOID` threshold, and `USE` and `INSPECT FIRST` were
unreachable from every command in the tool. Enumerating 3,359,232 input combinations
across all three commands produced `AVOID` and `not established` and nothing else. The
v0.1 README disclosed that `USE` was unreachable; it did not disclose that
`INSPECT FIRST` was, and listed it as a live label. Both are reachable now, and
`tests/test_scoring.py` asserts that each of the three can actually be produced.

## What it reads, and what it does not

A scanner that opens 8% of a repository has a low finding rate for a reason that has
nothing to do with the repository, so the report states the coverage rather than
leaving the reader to assume it.

Text files are read by extension, by a small set of conventional extensionless names
(`Makefile`, `Dockerfile`, `install`, `configure`), and by shebang. Binary files are not
read; the first 2 KB decides, and a byte-order mark is honoured so a UTF-16 file saved
by a Windows editor is read as the text it is rather than skipped as binary. Directories
holding code the repository did not write — `node_modules`, `vendor`, `third_party`,
`target`, build output and virtual environments — are skipped, so findings in a copied
dependency are not reported against the repository that vendored it.

Each pattern is matched against a window of one line plus the next, never against a
whole file, and at most three findings per rule per file are reported. Every finding
carries the line it was found on and the text that actually matched.

Structurally out of reach, and reported as such rather than as a clean result:
compiled binaries, encrypted or generated payloads, anything a shallow clone omits
(submodule contents, and history beyond the tip), and any behaviour that only appears
at runtime. Static patterns produce false positives and false negatives in both
directions, and a report is a list of things to look at, not a verdict on the code.

## Evidence states

Repository signals are `present`, `absent`, or `unknown`. `absent` means the tool looked
and the thing was not there. `unknown` means it could not be established, and is never
silently converted into absence — including when a directory could not be read, which
in v0.1 was reported as `absent`.

Where a signal can legitimately live varies by ecosystem, and looking in one place is
how a search too narrow to be honest ends up printing `absent`. Tests are looked for as
a directory, as a path such as `src/test/java`, and as files named the way Go, Rust and
JavaScript name them beside the code they test. Continuous integration is looked for
beyond GitHub Actions. Package metadata is looked for in about twenty forms and below
the top level, so a monorepo's `packages/*/package.json` counts. `README` and `LICENSE`
are matched without regard to case, and `LICENCE` and `COPYING` count as licences.

The two scores follow the same rule. Usefulness counts confirmed evidence only, so when
something could not be established the report also prints the figure it would produce if
it turned out present: a repository whose evidence could not be fetched therefore reads
differently from one confirmed to lack the same files.

Risk counts findings from a static file scan, so it is a number only when a scan ran.
`scan` and `report` run one. `search` and `inspect` read published metadata and open no
file, so their reports give risk as `unknown` and say that no scan was performed, rather
than reporting no findings.

## Measured against real repositories

Version 0.1 had never been run against a repository it did not author. Version 0.2 was
run against **385 real public repositories**, cloned on 8 September 2026 and held frozen,
across eleven primary languages plus security-research, malware-analysis,
documentation-only, monorepo, dotfile and non-English strata. Both versions were run over
the same frozen corpus with the same script, so every figure below is a before and after
of the same measurement, not two different ones.

| | v0.1 | v0.2 |
|---|---|---|
| Bytes of the median repository opened | 8.3% | **66.8%** |
| Files of the median repository opened | 23.5% | **86.8%** |
| Repositories where it opened nothing at all | 15 | **0** |
| Verdicts it could produce | `AVOID`, or none | **all four** |
| `obfuscated-execution` findings | 98, in 44 repositories | **6, in 4** |
| `possible-exfiltration` findings | 210, in 58 repositories | **19, in 6** |
| Repositories reported as having no tests | 230 | **154** |
| Repositories reported as having no package metadata | 230 | **105** |
| Crashes, hangs, timeouts | 0 | 0 |
| Slowest single repository | 31.8 s | 25.5 s |

Two rules went the other way, and that is the point of them: `remote-shell` rose from 79
findings to 329 and `secret-like-string` from 42 to 273, because v0.1 did not open the
files those patterns live in. Sampling them showed most of the new ones are real matches
in documentation and test fixtures — a project's own `curl … | bash` install line in its
README, Amazon's own published example access key in a guide, a scanner's own
rule fixtures. **66% of all
findings now sit in documentation or a test fixture**, and those are reported at a lower
severity that says so, because a documented installer scored `critical` drives `AVOID` on
its own and that is the tool reporting the genre of a file rather than the risk of a
repository.

After that weighting: 69% of the 385 repositories produce no findings at all, the median
repository produces none, and the verdicts fall 50.6% `USE`, 20.0% `INSPECT FIRST`,
29.4% `AVOID`. The security-research and malware-analysis strata skew hardest towards
`AVOID`, which is the expected result for repositories that contain attack strings on
purpose, and the reason `AVOID` is a prioritization label rather than an accusation.

### What it misses

The corpus measures what the tool says about ordinary repositories. It cannot measure
what the tool fails to say, because none of those 385 repositories is known to contain
anything hostile. That was measured separately, by planting payloads whose detection is
known in advance into 48 different file containers and 11 different positions in a file
— ground truth by construction, so a miss is a false negative and not a judgement call.

**v0.1 detected 17 of 48 containers. v0.2 detects 48 of 48.** The 31 it missed included
every compiled language, `.tsx` and `.jsx`, notebooks, Markdown, extensionless shell
scripts named `install` or `configure`, and shell dotfiles. It also missed any UTF-16
file entirely, and missed `requests.post(url, data=os.environ)` — the idiomatic Python
form — because the rule required the credential to appear before the network call.

This says nothing about patterns the rules were never written to catch, and it is not a
claim that the tool finds a determined attacker's code. No claim is made that a reader
who runs this tool makes a better adoption decision; that has not been measured, and
there is no oracle here that could measure it.

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

Repo Scout is version 0.2.0 and early alpha. Commands, scoring weights, and report
output can change without a deprecation period.

The test matrix in `.github/workflows/ci.yml` covers Python 3.11, 3.12, 3.13 and 3.14 on
Linux, and the workflow is triggered on every push and pull request. Whether it passed
for the commit you are reading is answered per commit by the repository's GitHub
Actions history, which is the authority for that question. A checkout carries the
workflow definition and not its results, so this file reports no outcome for the commit
it sits in. One run is on record here: on 30 August 2026 the matrix ran against the
published v0.1 tree, commit `a14de73`, and passed on all four versions.

What the matrix leaves uncovered is fixed by the workflow and by `pyproject.toml`, and
does not vary from commit to commit. The declared range is Python 3.11 or newer with
no upper bound, so anything above 3.14 is unexercised, including versions that do not
exist yet. The workflow's only runner is Linux, so Windows is untested; development and
manual verification are on macOS. Treat any version or platform the matrix does not
cover as unverified, and read the Actions history for the commit in hand rather than
assuming an earlier result carries forward.

There is no adoption or contribution history to report. Maintenance is best effort by a
single maintainer working in a weekly review block, with AI assistance used and reviewed
during development. Issues and pull requests may wait
days for a response.

## Project boundaries

- Public repositories only for network-backed commands.
- No GitHub token is required.
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

## Author

[Waiga Arya](https://www.linkedin.com/in/waigaarya/), Director of Business Strategy and
Innovation at Sadaway Pvt. Ltd. These tools were built for my own operating problems first.
