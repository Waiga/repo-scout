from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from .cache import FileCache
from .github_client import GitHubClient, GitHubClientError
from .models import EvidenceState, RepoReport, RepoSignals, RepoSummary
from .report import LIMITATION, risk_text, usefulness_text, verdict_text, write_report
from .scanner import scan_path
from .scoring import score_repository


DEFAULT_CACHE = Path(".repo-scout-cache")
DEFAULT_DOWNLOADS = Path("downloads")
DEFAULT_REPORTS = Path("reports")
REPO_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def _valid_repo_name(value: str) -> bool:
    if not isinstance(value, str) or not REPO_NAME_RE.fullmatch(value):
        return False
    if ".." in value:
        return False
    owner, repo = value.split("/")
    return owner != "." and repo != "."


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-scout",
        description=(
            "Report static evidence about a public GitHub repository or a local "
            "directory. Repo Scout does not prove that a repository is safe or "
            "infected: it reports what it observed and what it could not "
            "establish, and its verdicts are prioritization labels for human "
            "review."
        ),
    )
    parser.add_argument(
        "--reports-dir",
        default=str(DEFAULT_REPORTS),
        help=f"directory to write Markdown and HTML reports into (default: {DEFAULT_REPORTS})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search public GitHub repositories")
    search.add_argument("query")
    search.add_argument(
        "--limit", type=int, default=10, help="maximum number of results (default: 10)"
    )

    inspect = sub.add_parser("inspect", help="Inspect one public GitHub repository")
    inspect.add_argument("repo")

    download = sub.add_parser(
        "download",
        help=(
            "Clone a repo into the downloads directory (quarantine by location "
            "only: kept apart on disk, not sandboxed)"
        ),
    )
    download.add_argument("repo")
    download.add_argument(
        "--downloads-dir",
        default=str(DEFAULT_DOWNLOADS),
        help=f"directory to clone into (default: {DEFAULT_DOWNLOADS})",
    )

    scan = sub.add_parser(
        "scan",
        help="Static-scan a local repository path and write Markdown and HTML reports",
    )
    scan.add_argument("path")

    report = sub.add_parser(
        "report",
        help="Same as scan, under a second name; both write the same report files",
    )
    report.add_argument("path")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    reports_dir = Path(args.reports_dir)

    if args.command == "search":
        return run_search_command(args.query, args.limit, GitHubClient())
    if args.command == "inspect":
        if not _valid_repo_name(args.repo):
            print("Repository must use the OWNER/REPO form.")
            return 2
        return run_inspect_command(args.repo, GitHubClient(), reports_dir, FileCache(DEFAULT_CACHE))
    if args.command == "download":
        return run_download_command(args.repo, Path(args.downloads_dir))
    if args.command in {"scan", "report"}:
        return run_scan_command(Path(args.path), reports_dir)
    return 2


def run_search_command(query: str, limit: int, client: GitHubClient) -> int:
    try:
        repos = client.search_repositories(query, limit=limit)
    except GitHubClientError as exc:
        print(f"Search failed: {exc}")
        print("No-token mode depends on public GitHub access from this Python environment.")
        return 1
    scored = [(repo, score_repository(repo, RepoSignals(), [], query)) for repo in repos]

    # `search` opens no file and fetches no signal, so its risk and verdict
    # lines say the same two things about every result: no scan ran, and no
    # label was established. Printed per row they are two thirds of the listing
    # and they bury the usefulness figure, which is the part that varies.
    #
    # Whether they are really identical is checked rather than assumed. The
    # header is printed only when every result produced the same pair, and any
    # run where they differ falls back to printing them per row, so hoisting
    # can never turn one result's answer into a claim about the rest.
    shared = {(risk_text(score), verdict_text(score)) for _repo, score in scored}
    header = shared.pop() if len(shared) == 1 else None

    if header is not None:
        risk, verdict = header
        print(f"Risk: {risk}")
        print(f"Verdict: {verdict}")
        print("Both are the same for every result below; usefulness is what varies.")
        print()

    for index, (repo, score) in enumerate(scored, start=1):
        print(f"{index}. {repo.full_name}")
        if repo.description:
            print(f"   {repo.description}")
        print(f"   Usefulness: {usefulness_text(score)}")
        if header is None:
            print(f"   Risk: {risk_text(score)}")
            print(f"   Verdict: {verdict_text(score)}")
    return 0


def run_inspect_command(repo_name: str, client: GitHubClient, reports_dir: Path, cache: FileCache) -> int:
    if not _valid_repo_name(repo_name):
        print("Repository must use the OWNER/REPO form.")
        return 2
    cache_key = f"inspect:v2:{repo_name}"
    cached = _cached_evidence(cache.get(cache_key))
    if cached is not None:
        repo, signals = cached
    else:
        try:
            repo = client.get_repo(repo_name)
        except GitHubClientError as exc:
            print(f"Inspect failed: {exc}")
            return 1
        signals = _fetch_signals(client, repo)
        cache.set(cache_key, {"repo": repo.__dict__, "signals": signals.__dict__})
    # No query: `inspect` names one repository rather than searching for one.
    # Passing `repo_name` here matched the repository's name against itself and
    # reported a query match nobody asked for.
    score = score_repository(repo, signals, [])
    report = RepoReport(repo=repo, signals=signals, findings=[], score=score)
    md_path, html_path = write_report(report, reports_dir)
    print_summary(report)
    print(f"Report: {md_path}")
    print(f"HTML: {html_path}")
    return 0


def _cached_evidence(cached: object) -> tuple[RepoSummary, RepoSignals] | None:
    """Rebuild a cached entry, or `None` when it cannot be used.

    The cache is a directory of files on the user's disk. A truncated write, a
    hand edit, or an entry written by an older set of fields all parse as JSON
    and then do not fit the dataclasses. A cache is an optimisation, so an entry
    that cannot be rebuilt is treated as a miss and the evidence is fetched
    again, rather than ending the command in a TypeError or a KeyError.
    """
    if not isinstance(cached, dict):
        return None
    try:
        return RepoSummary(**cached["repo"]), RepoSignals(**cached["signals"])
    except (AttributeError, KeyError, TypeError):
        return None


def run_download_command(repo_name: str, downloads_dir: Path) -> int:
    if not _valid_repo_name(repo_name):
        print("Repository must use the OWNER/REPO form.")
        return 2
    destination = downloads_dir / repo_name.replace("/", "__")
    if destination.exists():
        print(f"Already exists: {destination}")
        return 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    git = shutil.which("git")
    if not git:
        print("git not found on PATH")
        return 1
    url = f"https://github.com/{repo_name}.git"
    try:
        subprocess.run([git, "clone", "--depth", "1", url, str(destination)], check=True)
    except subprocess.CalledProcessError:
        print(f"Download failed: {repo_name}")
        return 1
    print(f"Downloaded to the quarantine directory: {destination}")
    print("Quarantine is by location only: the clone is kept apart on disk, not sandboxed.")
    print("No repository code was executed.")
    return 0


def run_scan_command(path: Path, reports_dir: Path) -> int:
    if not path.exists() or not path.is_dir():
        print(f"Scan path is not a directory: {path}")
        return 2
    repo = _local_repo_summary(path)
    try:
        signals = _local_signals(path)
        findings = scan_path(path)
    except OSError as exc:
        # `_local_signals` calls `path.iterdir()` and the scanner walks the tree,
        # so a directory the process cannot read, or one that disappears mid
        # scan, raises here. Reported the way the download failures are, rather
        # than as a traceback, and no report is written for a scan that did not
        # happen.
        print(f"Scan path could not be read: {path} ({exc.strerror or exc})")
        return 1
    # No query: `scan` and `report` take a path, not search terms. Passing
    # `path.name` here matched the directory name against the name taken from
    # it and reported a query match nobody asked for.
    # `metadata=False`: the summary above was built from a directory, so its
    # star, fork, open-issue and push-date fields are placeholders rather than
    # anything that was read. Scoring them held every local scan below the AVOID
    # threshold and reported that ceiling as a property of the scanned
    # repository.
    score = score_repository(repo, signals, findings, scanned=True, metadata=False)
    report = RepoReport(repo=repo, signals=signals, findings=findings, score=score)
    md_path, html_path = write_report(report, reports_dir)
    print_summary(report)
    print(f"Report: {md_path}")
    print(f"HTML: {html_path}")
    return 0


def print_summary(report: RepoReport) -> None:
    print(f"{report.repo.full_name}")
    print(f"Usefulness: {usefulness_text(report.score)}")
    print(f"Risk: {risk_text(report.score)}")
    print(f"Verdict: {verdict_text(report.score)}")
    for reason in report.score.reasons[:5]:
        print(f"- {reason}")
    print(LIMITATION)


def _fetch_signals(client: GitHubClient, repo: RepoSummary) -> RepoSignals:
    return RepoSignals(
        has_readme=_first_state(client, repo, ("README.md", "README.rst", "README.txt", "README")),
        has_license=_first_state(client, repo, ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")),
        has_ci=_first_state(client, repo, (".github/workflows/ci.yml", ".github/workflows/ci.yaml")),
        has_package_metadata=_first_state(client, repo, ("package.json", "pyproject.toml")),
    )


def _first_state(client: GitHubClient, repo: RepoSummary, paths: tuple[str, ...]) -> EvidenceState:
    results = [client.fetch_text_file(repo.full_name, path, repo.default_branch) for path in paths]
    if any(result.status == "present" for result in results):
        return "present"
    if all(result.status == "absent" for result in results):
        return "absent"
    return "unknown"


def _local_repo_summary(path: Path) -> RepoSummary:
    # `url` is empty on purpose: a local directory has no published URL, and its
    # absolute path would put the reader's filesystem layout into a report that
    # is written to be shared. The directory name identifies the scan instead.
    return RepoSummary(
        full_name=_local_target_name(path),
        description="Local repository scan",
        url="",
        pushed_at="",
    )


def _local_target_name(path: Path) -> str:
    """Name the scanned directory, never its location.

    Resolved first, so a path written as `.` or `foo/..` still yields the name
    of the directory it points at. A resolved path with no final component,
    such as the filesystem root, falls back to a fixed label.
    """
    return path.resolve().name or "local repository"


def _local_signals(path: Path) -> RepoSignals:
    return RepoSignals(
        has_readme=_state(any(path.glob("README*"))),
        has_license=_state(any(path.glob("LICENSE*"))),
        has_tests=_state(any(p.name.startswith("test") or p.name == "tests" for p in path.iterdir())),
        has_ci=_state((path / ".github" / "workflows").exists()),
        has_package_metadata=_state(
            any((path / name).exists() for name in ("package.json", "pyproject.toml", "Cargo.toml", "go.mod"))
        ),
    )


def _state(observed: bool) -> EvidenceState:
    return "present" if observed else "absent"


if __name__ == "__main__":
    raise SystemExit(main())
