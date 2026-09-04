# Architecture

Repo Scout has five focused stages:

1. `repo_scout.cli` parses commands and controls filesystem and Git boundaries.
2. `repo_scout.github_client` reads public GitHub metadata and text files;
   `repo_scout.cache` stores reusable public responses locally.
3. `repo_scout.scanner` examines local files without executing them.
4. `repo_scout.scoring` converts observed evidence into usefulness and risk scores.
5. `repo_scout.report` renders Markdown and escaped HTML reports.

`repo_scout.models` holds the shared dataclasses and the `present` / `absent` /
`unknown` evidence type that every stage passes along unchanged.

Data flows in one direction from collection to evidence states, scoring, and reports.
An unavailable source remains `unknown`. Collection failures do not become negative
facts. A report records whether a static scan contributed to it, so a command that opens
no file reports risk as unknown instead of reporting no findings. Downloaded repositories
are never imported or executed by Repo Scout.
