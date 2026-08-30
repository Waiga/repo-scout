from __future__ import annotations

import html
import re
from pathlib import Path

from .models import RepoReport


# Shown wherever a report has no URL to give, which is every local scan: a
# directory on disk has no published address, and its path is not one.
NO_URL = "none recorded"


def render_markdown(report: RepoReport) -> str:
    lines = [
        f"# Repo Scout Report: {report.repo.full_name}",
        "",
        f"- **Verdict:** {report.score.verdict}",
        f"- **Usefulness:** {report.score.usefulness}/100",
        f"- **Risk:** {report.score.risk}/100",
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
    else:
        lines.append("No static risk findings.")

    return "\n".join(lines).rstrip() + "\n"


def render_html(report: RepoReport) -> str:
    url = report.repo.url
    url_html = f'<a href="{html.escape(url)}">{html.escape(url)}</a>' if url else NO_URL
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in report.score.reasons)
    if not reasons:
        reasons = "<li>No evidence recorded</li>"
    findings = "".join(_finding_html(finding) for finding in report.findings) or "<p>No static risk findings.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Repo Scout Report: {html.escape(report.repo.full_name)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 2rem; line-height: 1.5; }}
    .verdict {{ font-size: 1.25rem; font-weight: 700; }}
    code, pre {{ background: #f4f4f5; padding: .15rem .3rem; }}
    pre {{ padding: .75rem; overflow: auto; }}
  </style>
</head>
<body>
  <h1>Repo Scout Report: {html.escape(report.repo.full_name)}</h1>
  <p class="verdict">Verdict: {html.escape(report.score.verdict)}</p>
  <ul>
    <li>Usefulness: {report.score.usefulness}/100</li>
    <li>Risk: {report.score.risk}/100</li>
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
