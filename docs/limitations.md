# Limitations

Repo Scout is a static triage tool, not a malware sandbox, legal review, package
reputation service, or guarantee of safety.

## What it cannot see

- Pattern matching can miss indirect, generated, encrypted, or environment-dependent behavior.
- Compiled binaries are not read. Their presence is reported; their contents are not.
- A shallow clone does not contain complete repository history, and it does not contain
  submodule contents at all. Neither absence is visible in the report as a gap.
- Each pattern is matched against a window of one line plus the next, so a construction
  split across three or more lines is not matched.
- Within a window, only the first match of each rule is reported, so two secrets on one
  line are one finding. At most three findings per rule per file are reported. A count of
  findings is a count of places worth looking, not a census.
- Directories holding code the repository did not write are **not scanned at all**:
  `node_modules`, `vendor`, `third_party`, `target`, `dist`, `build`, `out`, `coverage`,
  virtual environments and the rest of `IGNORED_DIRS` in `repo_scout/scanner.py`. This is
  deliberate — a finding in a copied dependency is not a finding about this repository —
  but it is a complete blind spot, and `build/` in particular sometimes holds a project's
  own scripts rather than build output. Anything placed there is invisible to every rule.
- A finding in documentation or a test fixture is reported one severity step lower than
  the same finding in the repository's own source, and the message says so. A project's
  documented `curl … | bash` install line scored `critical` would drive `AVOID` by itself,
  which reports the genre of a file rather than the risk of a repository. The relief is
  one step only, so hostile code cannot be hidden under a directory name: two such
  findings still reach `INSPECT FIRST`, and the same files in `src/` reach `AVOID`.
- Text files larger than 64 MB are not read. The skip is reported as a `file-not-read`
  finding rather than passed over silently.
- Test fixtures and security research can match dangerous patterns without being
  executable threats. A scanner's own test suite will light up, and so will a write-up
  that quotes an attack string in a Markdown file.
- Stars, forks, contributors, and update dates are context signals, not proof of quality.
- Public GitHub requests can fail or be rate-limited; unavailable evidence is `unknown`.

## What the labels mean

- `USE`, `INSPECT FIRST`, and `AVOID` are prioritization labels for human review.
- **`USE` is not a statement about the code.** For a local scan the entire usefulness
  scale is five yes/no signals — a README, a licence, package metadata, a tests directory,
  a CI config — and every one of them is satisfied by an empty file or an empty directory.
  `USE` means the things a maintained project usually has are present and the static scan
  found nothing, and it means nothing more than that.
- A report can end with the verdict `not established`, which means the evidence
  gathered did not single out one of those three. It is a normal outcome, not a
  failure, and it is the correct one wherever the evidence, rather than the
  repository, is the limit.
- Usefulness is scored over the share of the scale a given run could observe, and the
  report says what that share was. A local scan reads no star count, so it is scored
  without one rather than penalised for it.

## What has been measured, and what has not

Version 0.2 was run against 385 real public repositories that this project did not
author, spanning eleven languages, security-research and malware-analysis repositories,
documentation-only repositories, monorepos, dotfile repositories and repositories whose
primary language is not English. Every finding rate quoted in the README comes from that
run. The zero-crash figure is a property of that corpus, not a guarantee. It measures what the tool says about ordinary repositories; it does not establish
that the tool finds a determined attacker's code, because none of those repositories is
known to contain any.

What it misses was measured separately, by planting payloads whose detection is known in
advance across 48 file containers, 11 positions in a file, and 11 directories. Six of
those directories are on the ignore list and detect nothing at all, by design. That is ground truth by
construction, and it is the only false-negative evidence here. It says nothing about
patterns the rules were never written to catch.

No claim is made that a reader who runs this tool makes a better adoption decision. That
has not been measured and there is no oracle here that could measure it.

Do not execute a repository merely because Repo Scout reports low static risk.
