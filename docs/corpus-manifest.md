# Corpus manifest

Every number in the README's "Measured against real repositories" section was
produced against the material described here. This document exists so that a
stranger can obtain the same material and check.

Where something was not recorded at the time, this document says so rather than
reconstructing it. An entry that says a figure cannot be reproduced is a real
answer, not a gap waiting to be filled in.

## 1. The corpus: 385 public GitHub repositories

**What it is.** 385 repositories, selected by stratified search against the
public GitHub search API and cloned to disk on **8 September 2026**.

**The list.** [`docs/corpus/repositories.tsv`](corpus/repositories.tsv) — 385
rows plus a header, one per repository:

| column | meaning |
|---|---|
| `stratum` | which query family selected it |
| `repository` | `owner/name`, the identifier a stranger can follow |
| `stars` | `stargazers_count` at selection time |
| `size_kb` | GitHub's reported repository size, in KB, at selection time |
| `language` | GitHub's reported primary language, or `none` |
| `fork` | GitHub's fork flag |

`https://github.com/<repository>` resolves for every row. Star counts and sizes
are as GitHub reported them on 8 September 2026 and will have moved since; they
are recorded because they are what the selection queries filtered on.

**Selection rule, exactly.** Each line below is one `GET /search/repositories`
call with `sort=stars`, `order=desc`, and the stated `per_page`. The results of
all twenty-one calls were concatenated and then deduplicated on the repository
name with `sort -u -k2,2`, which is why the strata do not sum to their requested
sizes — a repository matching two queries is kept once, under whichever stratum
sorted first.

| stratum | query | per_page |
|---|---|---|
| `general` | `language:<L> stars:>800 size:<25000 archived:false` for `L` in Python, JavaScript, TypeScript, Go, Rust, Java, C, C++, Ruby, PHP, Shell | 18 each |
| `security` | `topic:security-tools stars:>150 size:<25000` | 20 |
| `security` | `topic:pentesting stars:>150 size:<25000` | 15 |
| `malware-analysis` | `topic:malware-analysis stars:>80 size:<25000` | 15 |
| `docs-only` | `topic:awesome stars:>2000 size:<25000` | 20 |
| `docs-only` | `topic:documentation stars:>300 size:<25000` | 15 |
| `small` | `stars:5..60 size:<8000 pushed:>2026-06-01` | 40 |
| `non-english` | `language:Python stars:>300 size:<25000 topic:chinese` | 12 |
| `non-english` | `stars:>500 size:<25000 topic:japanese` | 12 |
| `dotfiles` | `topic:dotfiles stars:>200 size:<25000` | 15 |
| `installer` | `topic:cli stars:>500 size:<25000` | 18 |
| `large` | `language:Python stars:>3000 size:60000..200000 archived:false` | 10 |
| `testfixtures` | `topic:testing stars:>300 size:<25000` | 18 |

**Strata as they came out**, after deduplication — these are counts from the
committed file, not from the requested sizes:

| stratum | repositories |
|---|---|
| general | 198 |
| small | 40 |
| security | 32 |
| docs-only | 31 |
| non-english | 22 |
| testfixtures | 18 |
| malware-analysis | 15 |
| dotfiles | 14 |
| large | 10 |
| installer | 5 |
| **total** | **385** |

27 distinct primary languages are represented, the eleven queried for plus
sixteen that arrived through the topic-based strata; 34 repositories have no
primary language at all. The README describes the strata as "eleven primary
languages plus security-research, malware-analysis, documentation-only,
monorepo, dotfile and non-English strata". The table above is the authority on
what the strata actually are. There is no stratum named `monorepo`; the strata
the README's list does not name are `small`, `large`, `installer` and
`testfixtures`.

**How they were fetched.** `git clone --depth 1 --no-tags` per repository, run
eight at a time. All 385 clones succeeded; the clone status log recorded `OK`
for 385 of 385 and no failures.

**⚠️ What is not pinned: the commit.** The clone script deleted each `.git`
directory immediately after cloning, so **no commit SHA was recorded for any of
the 385 repositories**. The consequence is concrete and worth stating plainly: a
stranger who clones this list today gets each repository's current tip, not the
tree these numbers were measured on. Coverage percentages, finding counts and
verdicts will therefore not reproduce exactly. The repository list is exact; the
snapshot is not. Recording `git rev-parse HEAD` before deleting `.git` would
have closed this, and did not happen.

**Redistribution.** No repository content is redistributed here. The file lists
names and public metadata only. Each repository carries its own licence.

## 2. What was run, and where each README figure comes from

Two measurement arms over the same frozen clones, using the same script:

- **v0.1 arm** — the published v0.1 tree, results in `baseline_v01.ndjson`.
- **v0.2 arm** — the current tree, results in `fixed.ndjson`.

Both are NDJSON, one record per repository, 385 records each, carrying the
per-repository byte and file counts, every finding with its rule, path and
matched text, both usefulness figures, the risk score, the verdict and the
elapsed time.

The measurement script reproduces exactly what `repo-scout scan <dir>` does —
`_local_repo_summary`, `_local_signals`, `scan_path`, `score_repository` — minus
report writing.

Every figure in the README's before-and-after table is a direct read of those
two files:

| README figure | v0.1 | v0.2 | derived from |
|---|---|---|---|
| Bytes of the median repository opened | 8.3% | 66.8% | median of `bytes_read / bytes_on_disk` |
| Files of the median repository opened | 23.5% | 86.8% | median of `files_read / files_on_disk` |
| Repositories where it opened nothing | 15 | 0 | count of `files_read == 0` |
| Verdicts across the 385 | AVOID 132, no label 253 | USE 179, AVOID 122, INSPECT FIRST 84 | `verdict` counts |
| `obfuscated-execution` findings | 98 in 44 | 11 in 5 | findings and distinct repositories by rule |
| `possible-exfiltration` findings | 210 in 58 | 42 in 11 | same |
| `remote-shell` findings | 79 | 365 | same |
| `secret-like-string` findings | 42 | 273 | same |
| No tests reported | 230 | 147 | `signals.has_tests != "present"` |
| No package metadata reported | 230 | 100 | `signals.has_package_metadata != "present"` |
| Slowest single repository | 31.8 s | 25.4 s | `max(seconds)` — 31.767 and 25.378 |
| Crashes, hangs, timeouts | 0 | 0 | `ok == false` count |

The figures that follow that table come from the v0.2 arm alone: 740 findings in
total, of which 469 (63.4%) carry a reduced severity; 262 of 385 repositories
(68.1%) produce no findings at all; the median repository produces none; and the
verdict split is 46.5% `USE`, 21.8% `INSPECT FIRST`, 31.7% `AVOID`.

**⚠️ Where the result files live, and what that means.** Both NDJSON files, the
clone tree and the measurement script are in a scratch directory on the author's
machine, not in this repository and not published anywhere. They are working
files from the session that produced v0.2. **They are not redistributed, and a
third party cannot obtain them.** What a third party can do is re-run the
measurement from the repository list above against fresh clones, accepting the
snapshot drift described in section 1.

The measurement script is likewise not in this repository. The README's claim
that "both versions were run over the same frozen corpus with the same script"
is true of what happened and is not currently checkable by a reader. Shipping
the harness would close that; it has not been done.

## 3. The planted-payload measurement

Separate from the corpus run, and the one measurement with ground truth by
construction. The corpus can only measure what the tool *says* about ordinary
repositories, because none of the 385 is known to contain anything hostile. This
measurement plants payloads whose detection is known in advance, so a miss is a
false negative rather than a judgement call.

**Method.** One payload per rule the scanner declares, each a literal the rule's
own regex matches, planted into copies of corpus repositories along three axes:

| axis | variants | what it varies |
|---|---|---|
| extension | 48 containers | the file the payload sits in — `.sh`, `.py`, `.tsx`, `.ipynb`, `.md`, `Dockerfile`, `Makefile`, `install`, `configure`, `.env` and 38 more |
| position | 11 positions | where in the file the payload sits |
| location | 11 directories | which directory the file sits in |

**Results, from `plant_results.ndjson`** — 280 records, one per (axis, rule,
container) trial:

- extension axis: 192 trials, 48 distinct containers × 4 rules, **192 detected**.
  Every one of the 48 containers is detected. This is the README's "v0.2 detects
  48 of 48".
- position axis: 44 trials, 11 positions × 4 rules, 44 detected.
- location axis: 44 trials, 11 directories × 4 rules, **20 detected**. 5 of the
  11 directories are scanned; **6 are not scanned at all**, which is the
  README's statement and is the ignore list working as designed.

**⚠️ The v0.1 side of this measurement is not reproducible from a file.** The
README's "v0.1 detected 17 of the 48 containers" is real and was measured — the
v0.1 arm printed `17/48` for every one of the four rules — but the results file
was overwritten by the v0.2 run and only the printed summary survives, in the
harness transcript of the session that produced it. There is no artefact a third
party could be given. The 48-of-48 figure for v0.2 is backed by a surviving
results file; the 17-of-48 figure for v0.1 is backed by a transcript line on the
author's machine and nothing else.

**A known limit of this measurement, already stated in the README.** The oracle
plants only into files of an otherwise clean host repository. It therefore
cannot exercise anything that depends on a payload's surroundings, and the
"48 of 48" figure should be read as evidence about file containers, not as a
general false-negative rate.

## 4. Summary: what a third party can and cannot reproduce

| claim | status |
|---|---|
| which 385 repositories | **reproducible** — the list ships here |
| the selection rule | **reproducible** — every query is stated |
| the exact trees measured | **not reproducible** — no commit SHAs were recorded |
| the corpus figures, exactly | **not reproducible** — depends on the trees above |
| the corpus figures, approximately | reproducible by re-running against fresh clones |
| the planted-payload figures for v0.2 | backed by a surviving results file, not published |
| the planted-payload figure for v0.1 | **not reproducible** — file overwritten, transcript only |
| the measurement harness | **not published** |
