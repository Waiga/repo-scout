from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Finding


TEXT_EXTENSIONS = {
    ".bash",
    ".cjs",
    ".env",
    ".js",
    ".json",
    ".mjs",
    ".ps1",
    ".py",
    ".rb",
    ".sh",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
}

REMOTE_SHELL_RE = re.compile(r"(curl|wget)\b[^|;&\n]*\|\s*(bash|sh|zsh|python|python3)\b", re.I)
OBFUSCATED_EXEC_RE = re.compile(r"(eval|exec|Function)\s*\(.*(base64|atob|b64decode)", re.I | re.S)
SECRET_RE = re.compile(
    r"(?i)\b("
    r"ghp_[A-Za-z0-9_]{20,}|"
    r"github_token\s*=\s*['\"]?[A-Za-z0-9_]{20,}|"
    r"api[_-]?key\s*=\s*['\"]?[A-Za-z0-9_\-]{20,}|"
    r"secret\s*=\s*['\"]?[A-Za-z0-9_\-]{20,}"
    r")"
)
EXFIL_RE = re.compile(r"(?i)(process\.env|os\.environ|~/.ssh|id_rsa).{0,120}(fetch|curl|requests\.post|http)", re.S)


def scan_path(path: Path | str) -> list[Finding]:
    root = Path(path)
    findings: list[Finding] = []
    for file_path in _iter_files(root):
        rel = str(file_path.relative_to(root))
        if _looks_binary(file_path):
            if file_path.suffix.lower() in {".bin", ".exe", ".dll", ".dylib", ".so"}:
                findings.append(
                    Finding(
                        severity="medium",
                        rule="binary-blob",
                        path=rel,
                        message="Binary-like file present in source tree",
                    )
                )
            continue

        if file_path.name == "package.json":
            findings.extend(_scan_package_json(file_path, rel))

        if _is_text_candidate(file_path):
            text = _read_text(file_path)
            findings.extend(_scan_text(text, rel))

    return findings


def _iter_files(root: Path):
    ignored_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if any(part in ignored_dirs for part in file_path.parts):
            continue
        yield file_path


def _is_text_candidate(path: Path) -> bool:
    return (
        path.suffix.lower() in TEXT_EXTENSIONS
        or path.name in {"Makefile", "Dockerfile", "install.sh"}
        or path.name.startswith(".env")
        or ".env" in path.name
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _looks_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return False
    if not chunk:
        return False
    if b"\x00" in chunk:
        return True
    non_text = sum(1 for b in chunk if b < 9 or (13 < b < 32))
    return non_text / max(len(chunk), 1) > 0.25


def _scan_package_json(path: Path, rel: str) -> list[Finding]:
    findings: list[Finding] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return findings
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return findings
    for name in ("preinstall", "install", "postinstall", "prepare"):
        if name in scripts:
            findings.append(
                Finding(
                    severity="high",
                    rule="package-install-hook",
                    path=rel,
                    message=f"Package install hook `{name}` runs during dependency installation",
                    evidence=str(scripts[name])[:200],
                )
            )
    return findings


def _scan_text(text: str, rel: str) -> list[Finding]:
    checks = [
        ("critical", "remote-shell", "Remote shell execution pattern", REMOTE_SHELL_RE),
        ("critical", "obfuscated-execution", "Obfuscated decode plus execution pattern", OBFUSCATED_EXEC_RE),
        ("high", "secret-like-string", "Secret-like token string present", SECRET_RE),
        ("high", "possible-exfiltration", "Possible credential/network exfiltration pattern", EXFIL_RE),
    ]
    findings: list[Finding] = []
    for severity, rule, message, pattern in checks:
        match = pattern.search(text)
        if match:
            findings.append(
                Finding(
                    severity=severity,
                    rule=rule,
                    path=rel,
                    message=message,
                    evidence=match.group(0)[:200],
                )
            )
    return findings
