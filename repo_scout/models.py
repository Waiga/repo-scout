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
    # `None` when the evidence gathered cannot support any label. A verdict is a
    # claim about the repository, and the three labels include two that are
    # actively negative or actively positive, so the absence of a label is a
    # real outcome rather than a missing value to be filled in with the worst
    # one. `verdict_blockers` says why, for the run that produced it.
    verdict: str | None
    reasons: list[str] = field(default_factory=list)
    verdict_blockers: list[str] = field(default_factory=list)
    # Whether a static file scan contributed to `risk`. It defaults to False so
    # that a caller has to state a scan happened: an empty findings list on its
    # own cannot tell "the scan found nothing" from "nothing was examined", and
    # only one of those may be reported as an absence.
    static_scan: bool = False
    # `usefulness` recomputed with every `unknown` signal counted as `present`.
    # `usefulness` itself counts confirmed evidence only, so the two differ by
    # exactly the weight of the evidence that could not be established, and a
    # repository whose evidence is unknown stops reading like one confirmed to
    # lack the same files. `None` means the caller supplied no ceiling.
    usefulness_ceiling: int | None = None


@dataclass(frozen=True)
class RepoReport:
    repo: RepoSummary
    signals: RepoSignals
    findings: list[Finding]
    score: ScoreResult
