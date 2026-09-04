from __future__ import annotations

import html
import re
from pathlib import Path

from .models import RepoReport, ScoreResult


# Shown wherever a report has no URL to give, which is every local scan: a
# directory on disk has no published address, and its path is not one.
NO_URL = "none recorded"

# Shown instead of a findings list when no static file scan ran. An empty
# findings list means "nothing was found" only after a scan; without one it
# means nothing was examined, and the two must not read alike.
NO_SCAN_FINDINGS = (
    "No static scan was performed, so the file contents of this repository are "
    "unknown. Run `repo-scout download OWNER/REPO` and then `repo-scout scan` on "
    "the downloaded directory to examine them."
)

# Shown instead of a numeric risk figure for the same reason: `0/100` on an
# unscanned repository is the strongest safety statement the tool can make, made
# where the least is known.
NO_SCAN_RISK = (
    "unknown (no static scan was performed; only repository metadata was checked)"
)


# Carried by every artifact the scores travel in. The README frames them
# carefully and the README does not travel with a report file, a terminal
# session or a pasted screenshot, so the framing is repeated where the numbers
# are rather than left behind in the repository.
LIMITATION = (
    "Static evidence only. Repo Scout does not prove that a repository is safe or "
    "infected. A verdict is a prioritization label for human review. "
    "See docs/limitations.md."
)


# Shown in place of a label when the evidence gathered cannot single one out.
# The three labels are prioritization claims about the repository, and two of
# them are pointed ones, so no label is a real outcome rather than a blank to be
# filled in with the most cautious-looking word.
NO_VERDICT = "not established"


def verdict_text(score: ScoreResult) -> str:
    """The verdict label, or why there is not one.

    Shared with the Markdown report, the HTML report, the terminal summary and
    the search listing. A report file is written to be shared and the README does
    not travel with it, so the qualification is carried next to the missing label
    rather than left behind in the repository.
    """
    if score.verdict:
        return score.verdict
    if score.verdict_blockers:
        return (
            f"{NO_VERDICT} ({'; '.join(score.verdict_blockers)}). "
            "Read the Signals and Evidence sections."
        )
    return f"{NO_VERDICT}. Read the Signals and Evidence sections."


def risk_text(score: ScoreResult) -> str:
    """The risk figure, or why there is not one.

    Shared with the terminal summary and the search listing so that a report
    file, a summary line and a search result cannot disagree about whether a
    scan happened.
    """
    if not score.static_scan:
        return NO_SCAN_RISK
    return f"{score.risk}/100"


def usefulness_text(score: ScoreResult) -> str:
    """The usefulness figure, widened by whatever was not established.

    The confirmed figure counts only evidence that was established, so on its own
    it reads the same for a repository whose files could not be fetched and one
    confirmed to lack them. The ceiling is what tells them apart. It covers every
    unestablished part of the scale, not only the file signals: a local scan
    reads no star count, and an unread star count is unknown in the same sense as
    an unreadable README.
    """
    ceiling = score.usefulness_ceiling
    confirmed = f"{score.usefulness}/100"
    if ceiling is None or ceiling <= score.usefulness:
        return confirmed
    return (
        f"{confirmed} confirmed, up to {ceiling}/100 if everything that could "
        "not be established turns out present"
    )


def render_markdown(report: RepoReport) -> str:
    lines = [
        f"# Repo Scout Report: {report.repo.full_name}",
        "",
        f"- **Verdict:** {verdict_text(report.score)}",
        f"- **Usefulness:** {usefulness_text(report.score)}",
        f"- **Risk:** {risk_text(report.score)}",
        f"- **URL:** {report.repo.url or NO_URL}",
        f"- **Description:** {report.repo.description}",
        "",
        "## Signals",
        "",
        f"- README: {report.signals.has_readme}",
        f"- License: {report.signals.has_license}",
        f"- Tests: {report.signals.has_tests}",
        f"- CI: {report.signals.has_ci}",
        f"- Package metadata: {report.signals.has_package_metadata}",
        "",
        "## Evidence",
        "",
    ]
    if report.score.reasons:
        lines.extend(f"- {reason}" for reason in report.score.reasons)
    else:
        lines.append("- No evidence recorded")

    lines.extend(["", "## Findings", ""])
    if report.findings:
        for finding in report.findings:
            lines.extend(
                [
                    f"### {finding.severity.upper()}: {finding.rule}",
                    "",
                    f"- **Path:** `{finding.path}`",
                    f"- **Message:** {finding.message}",
                ]
            )
            if finding.evidence:
                lines.extend(["", "```text", finding.evidence, "```"])
            lines.append("")
    elif report.score.static_scan:
        lines.append("No static risk findings.")
    else:
        lines.append(NO_SCAN_FINDINGS)

    lines.extend(["", "---", "", LIMITATION])

    return "\n".join(lines).rstrip() + "\n"


def render_html(report: RepoReport) -> str:
    url = report.repo.url
    url_html = f'<a href="{html.escape(url)}">{html.escape(url)}</a>' if url else NO_URL
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in report.score.reasons)
    if not reasons:
        reasons = "<li>No evidence recorded</li>"
    empty = "No static risk findings." if report.score.static_scan else NO_SCAN_FINDINGS
    findings = "".join(_finding_html(finding) for finding in report.findings) or f"<p>{html.escape(empty)}</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Repo Scout Report: {html.escape(report.repo.full_name)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 2rem; line-height: 1.5; }}
    .verdict {{ font-size: 1.25rem; font-weight: 700; }}
    .limitation {{ color: #52525b; }}
    code, pre {{ background: #f4f4f5; padding: .15rem .3rem; }}
    pre {{ padding: .75rem; overflow: auto; }}
  </style>
</head>
<body>
  <h1>Repo Scout Report: {html.escape(report.repo.full_name)}</h1>
  <p class="verdict">Verdict: {html.escape(verdict_text(report.score))}</p>
  <ul>
    <li>Usefulness: {html.escape(usefulness_text(report.score))}</li>
    <li>Risk: {html.escape(risk_text(report.score))}</li>
    <li>URL: {url_html}</li>
    <li>Description: {html.escape(report.repo.description)}</li>
  </ul>
  <h2>Signals</h2>
  <ul>
    <li>README: {html.escape(report.signals.has_readme)}</li>
    <li>License: {html.escape(report.signals.has_license)}</li>
    <li>Tests: {html.escape(report.signals.has_tests)}</li>
    <li>CI: {html.escape(report.signals.has_ci)}</li>
    <li>Package metadata: {html.escape(report.signals.has_package_metadata)}</li>
  </ul>
  <h2>Evidence</h2>
  <ul>{reasons}</ul>
  <h2>Findings</h2>
  {findings}
  <hr>
  <p class="limitation">{html.escape(LIMITATION)}</p>
</body>
</html>
"""


def write_report(report: RepoReport, out_dir: Path | str) -> tuple[Path, Path]:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    slug = _slug(report.repo.full_name)
    md_path = root / f"{slug}.md"
    html_path = root / f"{slug}.html"
    md_path.write_text(render_markdown(report), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    return md_path, html_path


def _finding_html(finding) -> str:
    evidence = ""
    if finding.evidence:
        evidence = f"<pre>{html.escape(finding.evidence)}</pre>"
    return f"""
<section>
  <h3>{html.escape(finding.severity.upper())}: {html.escape(finding.rule)}</h3>
  <ul>
    <li>Path: <code>{html.escape(finding.path)}</code></li>
    <li>Message: {html.escape(finding.message)}</li>
  </ul>
  {evidence}
</section>
"""


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "__", value).strip("_") or "report"
