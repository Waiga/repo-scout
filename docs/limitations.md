# Limitations

Repo Scout is a static triage tool, not a malware sandbox, legal review, package
reputation service, or guarantee of safety.

- Pattern matching can miss indirect, generated, encrypted, or environment-dependent behavior.
- Test fixtures and security research can match dangerous patterns without being executable threats.
- Public GitHub requests can fail or be rate-limited; unavailable evidence is `unknown`.
- A shallow clone does not contain complete repository history.
- Stars, forks, contributors, and update dates are context signals, not proof of quality.
- `USE`, `INSPECT FIRST`, and `AVOID` are prioritization labels for human review.

Do not execute a repository merely because Repo Scout reports low static risk.
