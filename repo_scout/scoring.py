from __future__ import annotations

from datetime import datetime, timezone

from .models import Finding, RepoSignals, RepoSummary, ScoreResult


def score_repository(
    repo: RepoSummary,
    signals: RepoSignals,
    findings: list[Finding],
    query: str = "",
) -> ScoreResult:
    usefulness, reasons = _usefulness(repo, signals, query)
    risk, risk_reasons = _risk(repo, signals, findings)
    verdict = _verdict(usefulness, risk)
    return ScoreResult(
        usefulness=usefulness,
        risk=risk,
        verdict=verdict,
        reasons=reasons + risk_reasons,
    )


def _usefulness(repo: RepoSummary, signals: RepoSignals, query: str) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0.0

    relevance = _relevance(repo, query)
    score += relevance * 30
    if relevance >= 0.7:
        reasons.append("Matches query terms in name or description")

    health = 0
    if signals.has_readme == "present":
        health += 0.3
        reasons.append("README present")
    if _freshness(repo.pushed_at) == "present":
        health += 0.3
        reasons.append("Recently updated")
    if signals.has_releases == "present":
        health += 0.2
    if repo.open_issues <= 25:
        health += 0.2
    score += min(health, 1.0) * 20

    contributors = signals.contributor_count or 0
    credibility = min(1.0, (repo.stars / 300) * 0.55 + (repo.forks / 40) * 0.25 + min(contributors, 5) / 25)
    score += credibility * 20
    if repo.stars >= 100:
        reasons.append("Meaningful star count")

    setup = 0
    if signals.has_readme == "present":
        setup += 0.45
    if signals.has_package_metadata == "present":
        setup += 0.35
        reasons.append("Package metadata present")
    if signals.has_license == "present":
        setup += 0.2
    score += min(setup, 1.0) * 15

    structure = 0
    if signals.has_tests == "present":
        structure += 0.4
        reasons.append("Tests detected")
    if signals.has_ci == "present":
        structure += 0.35
        reasons.append("CI detected")
    if signals.has_package_metadata == "present":
        structure += 0.25
    score += min(structure, 1.0) * 15

    return _clamp(score), reasons


def _risk(repo: RepoSummary, signals: RepoSignals, findings: list[Finding]) -> tuple[int, list[str]]:
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
    if _freshness(repo.pushed_at) == "absent":
        score += 10
        reasons.append("Repository has not been updated in 365 days")

    return min(score, 100), reasons


def _verdict(usefulness: int, risk: int) -> str:
    if usefulness < 50 or risk >= 70:
        return "AVOID"
    if usefulness >= 75 and risk < 30:
        return "USE"
    return "INSPECT FIRST"


def _relevance(repo: RepoSummary, query: str) -> float:
    terms = [t.lower() for t in query.split() if len(t) > 1]
    if not terms:
        return 0.5
    haystack = f"{repo.full_name} {repo.description}".lower()
    matched = sum(1 for term in terms if term in haystack)
    return matched / len(terms)


def _freshness(value: str) -> str:
    if not value:
        return "unknown"
    try:
        pushed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    return "present" if (datetime.now(timezone.utc) - pushed).days <= 365 else "absent"


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))
