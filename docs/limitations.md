# Limitations

Repo Scout is a static triage tool, not a malware sandbox, legal review, package
reputation service, or guarantee of safety.

## What it cannot see

- Pattern matching can miss indirect, generated, encrypted, or environment-dependent behavior.
- Compiled binaries are not read. Their presence is reported; their contents are not.
- A shallow clone does not contain complete repository history, and it does not contain
  submodule contents at all. Neither absence is visible in the report as a gap.
- Each pattern is matched against a window of one line plus the next, so a construction
  deliberately split across three or more lines is not matched.
- At most three findings per rule per file are reported, so a count of findings is a
  count of places worth looking, not a census.
- Test fixtures and security research can match dangerous patterns without being
  executable threats. A scanner's own test suite will light up, and so will a write-up
  that quotes an attack string in a Markdown file.
- Stars, forks, contributors, and update dates are context signals, not proof of quality.
- Public GitHub requests can fail or be rate-limited; unavailable evidence is `unknown`.

## What the labels mean

- `USE`, `INSPECT FIRST`, and `AVOID` are prioritization labels for human review.
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
run. It measures what the tool says about ordinary repositories; it does not establish
that the tool finds a determined attacker's code, because none of those repositories is
known to contain any.

What it misses was measured separately, by planting payloads whose detection is known in
advance across 48 file containers and 11 positions in a file. That is ground truth by
construction, and it is the only false-negative evidence here. It says nothing about
patterns the rules were never written to catch.

No claim is made that a reader who runs this tool makes a better adoption decision. That
has not been measured and there is no oracle here that could measure it.

Do not execute a repository merely because Repo Scout reports low static risk.
