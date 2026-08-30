from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


EvidenceState = Literal["present", "absent", "unknown"]


@dataclass(frozen=True)
class FileFetch:
    status: EvidenceState
    text: str | None = None


@dataclass(frozen=True)
class RepoSummary:
    full_name: str
    description: str
    url: str
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    pushed_at: str = ""
    default_branch: str = "main"


@dataclass(frozen=True)
class RepoSignals:
    has_readme: EvidenceState = "unknown"
    has_license: EvidenceState = "unknown"
    has_tests: EvidenceState = "unknown"
    has_ci: EvidenceState = "unknown"
    has_releases: EvidenceState = "unknown"
    has_package_metadata: EvidenceState = "unknown"
    contributor_count: int | None = None


@dataclass(frozen=True)
class Finding:
    severity: str
    rule: str
    path: str
    message: str
    evidence: str = ""


@dataclass(frozen=True)
class ScoreResult:
    usefulness: int
    risk: int
    verdict: str
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RepoReport:
    repo: RepoSummary
    signals: RepoSignals
    findings: list[Finding]
    score: ScoreResult
