from __future__ import annotations

from datetime import datetime, timezone

from .models import EvidenceState, Finding, RepoSignals, RepoSummary, ScoreResult


SIGNAL_FIELDS = (
    "has_readme",
    "has_license",
    "has_tests",
    "has_ci",
    "has_releases",
    "has_package_metadata",
)


def score_repository(
    repo: RepoSummary,
    signals: RepoSignals,
    findings: list[Finding],
    query: str = "",
    scanned: bool = False,
    metadata: bool = True,
    query_accepted: bool = True,
) -> ScoreResult:
    """Score a repository from the evidence actually gathered about it.

    `scanned` says whether a static file scan produced `findings`. It is not
    inferred from the list being empty, because a caller that ran no scan hands
    over the same empty list as a scan that found nothing.

    `metadata` says whether `repo` carries published repository metadata. A
    local directory has no stars, forks, open issue count or push date, so the
    caller that built its `RepoSummary` from a path passes False and those axes
    are treated as unobserved rather than as zeroes. Scoring the placeholders
    reported a shortfall the tool never measured as a property of the scanned
    repository.
    """
    usefulness, reasons, observable = _usefulness(repo, signals, query, metadata)
    ceiling, _, _ = _usefulness(repo, signals, query, metadata, unknown_as_present=True)
    risk, risk_reasons = _risk(repo, signals, findings, metadata)
    verdict = _verdict(usefulness, ceiling, risk, scanned)
    blockers = [] if verdict else _verdict_blockers(
        signals, query, metadata, scanned, query_accepted
    )
    return ScoreResult(
        usefulness=usefulness,
        risk=risk,
        verdict=verdict,
        reasons=reasons + risk_reasons,
        verdict_blockers=blockers,
        static_scan=scanned,
        usefulness_ceiling=ceiling,
        observable_scale=observable,
    )


def _usefulness(
    repo: RepoSummary,
    signals: RepoSignals,
    query: str,
    metadata: bool,
    unknown_as_present: bool = False,
) -> tuple[int, list[str]]:
    score = 0.0
    # `observable` is the share of the 100-point scale this run was in a
    # position to read at all. v0.1 scored every run out of a fixed 100
    # containing axes it knew it could not reach, so a local scan was capped at
    # 36 confirmed points, the label at the confirmed end was permanently
    # `AVOID`, and both `USE` and `INSPECT FIRST` were unreachable from every
    # command -- confirmed by enumerating 3.36 million input combinations.
    #
    # An axis that is out of scale for this run is excluded from BOTH passes.
    # It is not unestablished evidence that could turn out present; it is
    # something this command does not read. Only a signal that was looked for
    # and came back `unknown` separates the confirmed figure from the ceiling,
    # which is what makes the gap between them mean what it says.
    observable = 0.0
    freshness = _freshness(repo.pushed_at) if metadata else "unknown"

    def counts(state: str) -> bool:
        """Whether `state` earns its points.

        Confirmed evidence always does. `unknown` does only in the ceiling pass,
        which is what makes the ceiling an upper bound rather than a second
        opinion: the gap between the two passes is the unestablished evidence.
        """
        return state == "present" or (unknown_as_present and state == "unknown")

    relevance = _relevance(repo, query)
    if relevance is not None:
        # Relevance is scored only when a query was supplied. `scan`, `report`
        # and `inspect` take none, so for them it is out of scale rather than
        # a shortfall.
        score += relevance * 30
        observable += 30

    health = 0.0
    health_weight = 0.3
    if counts(signals.has_readme):
        health += 0.3
    if metadata:
        health_weight = 1.0
        if counts(freshness):
            health += 0.3
        if counts(signals.has_releases):
            health += 0.2
        if repo.open_issues <= 25:
            health += 0.2
    score += min(health, health_weight) * 20
    observable += 20 * health_weight

    if metadata:
        # `contributor_count` is populated by no V0.1 command, so `None` is the
        # normal case and means unknown -- unknown within an axis this run does
        # read, so it belongs in the ceiling.
        contributors = signals.contributor_count
        contribution = (
            min(contributors, 5) / 25
            if contributors is not None
            else (0.2 if unknown_as_present else 0.0)
        )
        credibility = min(1.0, (repo.stars / 300) * 0.55 + (repo.forks / 40) * 0.25 + contribution)
        score += credibility * 20
        observable += 20

    setup = 0.0
    if counts(signals.has_readme):
        setup += 0.45
    if counts(signals.has_package_metadata):
        setup += 0.35
    if counts(signals.has_license):
        setup += 0.2
    score += min(setup, 1.0) * 15
    observable += 15

    structure = 0.0
    if counts(signals.has_tests):
        structure += 0.4
    if counts(signals.has_ci):
        structure += 0.35
    if counts(signals.has_package_metadata):
        structure += 0.25
    score += min(structure, 1.0) * 15
    observable += 15

    normalised = (score / observable * 100) if observable else 0.0
    return (
        _clamp(normalised),
        _usefulness_reasons(repo, signals, relevance, freshness, metadata),
        int(round(observable)),
    )


def _usefulness_reasons(
    repo: RepoSummary,
    signals: RepoSignals,
    relevance: float | None,
    freshness: str,
    metadata: bool,
) -> list[str]:
    """The Evidence lines a report prints, in the order the components score.

    Every line here is keyed on `present`, never on `counts`, so the ceiling pass
    cannot put an unestablished signal into the evidence list as an observation.
    The star line is keyed on `metadata` for the same reason: a local scan's zero
    is a placeholder, not a count anybody read.
    """
    reasons: list[str] = []
    if relevance is not None and relevance >= 0.7:
        reasons.append("Matches query terms in name or description")
    if signals.has_readme == "present":
        reasons.append("README present")
    if freshness == "present":
        reasons.append("Recently updated")
    if metadata and repo.stars >= 100:
        reasons.append("Meaningful star count")
    if signals.has_package_metadata == "present":
        reasons.append("Package metadata present")
    if signals.has_tests == "present":
        reasons.append("Tests detected")
    if signals.has_ci == "present":
        reasons.append("CI detected")
    return reasons


def _risk(
    repo: RepoSummary,
    signals: RepoSignals,
    findings: list[Finding],
    metadata: bool,
) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    weights = {"critical": 70, "high": 35, "medium": 15, "low": 5}
    for finding in findings:
        score += weights.get(finding.severity, 10)
        reasons.append(f"{finding.severity} risk: {finding.rule} in {finding.path}")

    if signals.has_license == "absent":
        score += 8
        reasons.append("No license observed")
    if signals.has_readme == "absent":
        score += 10
        reasons.append("No README observed")
    if metadata and _freshness(repo.pushed_at) == "absent":
        score += 10
        reasons.append("Repository has not been updated in 365 days")

    return min(score, 100), reasons


def _verdict(usefulness: int, ceiling: int, risk: int, scanned: bool) -> str | None:
    """The label, or `None` when the evidence cannot single one out.

    `usefulness` is what was confirmed and `ceiling` is what the unestablished
    evidence could still add, so between them they bound where the real figure
    lies. A label is emitted only when both ends carry the same one. Printing
    the label at the low end instead states the shortfall of the evidence as a
    property of the repository, which is how a local scan came to report `AVOID`
    for a directory with every observable signal present and no findings.
    """
    labels = {_label(value, risk, scanned) for value in (usefulness, ceiling)}
    if len(labels) == 1:
        return labels.pop()
    return None


def _label(usefulness: int, risk: int, scanned: bool) -> str | None:
    """The label one usefulness figure earns, or `None` if it earns none.

    `AVOID` fires on low usefulness whatever the risk, so it stands without a
    scan. Nothing else does: without a scan the risk figure is not a measurement,
    so neither the low-risk half of `USE` nor the high-risk half of `AVOID` can
    be ruled in or out.
    """
    if usefulness < 50:
        return "AVOID"
    if not scanned:
        return None
    if risk >= 70:
        return "AVOID"
    if usefulness >= 75 and risk < 30:
        return "USE"
    return "INSPECT FIRST"


def _verdict_blockers(
    signals: RepoSignals,
    query: str,
    metadata: bool,
    scanned: bool,
    query_accepted: bool,
) -> list[str]:
    """Why no label was established, read off the run that produced it.

    A fixed sentence would be as opaque as a wrong label: the reader needs to
    know whether to supply a query, fetch metadata, run a scan, or accept that
    the evidence is simply not available.
    """
    blockers: list[str] = []
    if not [term for term in query.split() if len(term) > 1]:
        # `scan`, `report` and `inspect` accept no query, so telling their
        # reader that none was given named a remedy the command does not have.
        # It appeared on every clean local scan.
        blockers.append(
            "no query was given, so relevance was not scored"
            if query_accepted
            else "this command takes no query, so relevance is not part of its scale"
        )
    if not metadata:
        blockers.append("repository metadata is unavailable for a local path")
    if not scanned:
        blockers.append("no static scan was performed, so risk is unknown")
    unknown = sum(1 for field in SIGNAL_FIELDS if getattr(signals, field) == "unknown")
    if unknown:
        noun = "signal" if unknown == 1 else "signals"
        blockers.append(f"{unknown} repository {noun} could not be established")
    return blockers


def _relevance(repo: RepoSummary, query: str) -> float | None:
    """How much of the query the repository matched, or `None` for no query.

    `None` is not zero and not a half match. `scan`, `report` and `inspect` take
    no query, so relevance is not a thing that can be observed for them: the
    component is skipped rather than scored, and no evidence line is produced.
    Returning 0.5 here previously gave an unqueried report 15 usefulness points
    for a question nobody asked.
    """
    terms = [t.lower() for t in query.split() if len(t) > 1]
    if not terms:
        return None
    haystack = f"{repo.full_name} {repo.description}".lower()
    matched = sum(1 for term in terms if term in haystack)
    return matched / len(terms)


def _freshness(value: str) -> EvidenceState:
    if not value:
        return "unknown"
    try:
        pushed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    return "present" if (datetime.now(timezone.utc) - pushed).days <= 365 else "absent"


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))
