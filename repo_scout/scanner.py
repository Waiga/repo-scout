from __future__ import annotations

import json
import re
from pathlib import Path

from .models import Finding


# Extensions read as text. The v0.1 list held 15 suffixes, which excluded most
# of what public repositories are actually written in: a measured run over 328
# real repositories opened a median 7.7% of the bytes on disk, and reported a
# clean result for repositories it had barely read. Compiled languages, web
# component files, notebooks and documentation are all included now, because a
# `curl … | bash` in a README is the most common place that pattern appears.
TEXT_EXTENSIONS = {
    ".bash", ".bat", ".c", ".cc", ".cfg", ".cjs", ".cmd", ".conf", ".cpp",
    ".cs", ".css", ".env", ".fish", ".go", ".gradle", ".h", ".hpp", ".html",
    ".ini", ".ipynb", ".java", ".js", ".json", ".jsx", ".kt", ".kts", ".lua",
    ".md", ".mjs", ".mk", ".php", ".pl", ".properties", ".ps1", ".psm1",
    ".py", ".r", ".rb", ".rs", ".rst", ".scala", ".sh", ".sql", ".svelte",
    ".swift", ".tf", ".toml", ".ts", ".tsx", ".txt", ".vue", ".xml", ".yaml",
    ".yml", ".zsh",
}

# Files that carry no extension but are read as text anyway. `install`,
# `configure` and `scripts/bootstrap` are shell scripts by convention, and the
# planted-payload run confirmed every one of them was invisible to v0.1.
TEXT_FILENAMES = {
    "Makefile", "makefile", "GNUmakefile", "Dockerfile", "Containerfile",
    "Jenkinsfile", "Vagrantfile", "Rakefile", "Gemfile", "Brewfile",
    "install", "installer", "setup", "configure", "bootstrap", "build",
    "run", "entrypoint", "start", "postinstall", "preinstall",
}

SHEBANG_RE = re.compile(rb"^#!\s*/")

# Every pattern below is applied to a bounded window (see `_windows`), never to
# a whole file. The v0.1 patterns used `re.S` with a greedy `.*`, so a single
# "critical" finding covered a median 51% of the file it was reported against
# and, in the worst case measured, 3,492,650 characters of a 3.5 MB bundle. The
# evidence field showed the first 200 characters of that span, which did not
# contain the thing being reported.

REMOTE_SHELL_RE = re.compile(
    r"""(?ix)
    \b(?:curl|wget|iwr|invoke-webrequest)\b   # fetch
    [^|;&\n]{0,200}
    (?:
        \|\s*(?:sudo\s+)?(?:env\s+\S+\s+)*(?:ba|z|k|da|)sh\b   # | bash, | sudo sh, | env X=1 bash
      | \|\s*(?:sudo\s+)?(?:python3?|perl|ruby|node|iex)\b
    )
    """
)

# `bash <(curl …)` and `sh -c "$(curl …)"` are the same act written the other
# way round. v0.1 matched neither; both appear in real installers.
PROCESS_SUBSTITUTION_RE = re.compile(
    r"(?ix)\b(?:ba|z|k|da|)sh\b[^\n]{0,40}?[<$]\(\s*(?:curl|wget)\b"
)

# Decode-then-execute. Anchored on the execution call, and the decode has to
# appear within the same window rather than anywhere later in the file.
# Case matters here, and `(?i)` cost more than it bought. Applied to the whole
# pattern it made `Function` match the JavaScript keyword `function`, so any
# minified bundle -- which is one long line of `function(` -- matched as soon as
# a decode-ish word appeared within 200 characters. `unescape` was that word
# often enough on its own; it is ordinary URL handling, not base64, and it is
# gone. The execution anchors are matched case-sensitively as the languages
# actually spell them: `eval`, `exec`, and the capital-F `Function`
# constructor.
OBFUSCATED_EXEC_RE = re.compile(
    r"\b(?:eval|exec|new\s+Function|Function)\s*\([^\n]{0,200}?"
    r"\b(?i:base64|atob|b64decode|frombase64string|base64_decode)\b"
)

# A secret is a literal value. v0.1 accepted a bare identifier, so
# `api_key = _sandbox_config_value` and `api_key=select_api_key_for_models`
# were both reported as secrets. The value now has to be quoted, and has to
# contain both a digit and a letter, which a Python identifier rarely does.
SECRET_RE = re.compile(
    r"""(?x)
    (?:
        \bghp_[A-Za-z0-9]{36}\b
      | \bgithub_pat_[A-Za-z0-9_]{22,}\b
      | \bxox[baprs]-[A-Za-z0-9-]{10,}\b
      | \bsk-[A-Za-z0-9]{32,}\b
      | \bAKIA[0-9A-Z]{16}\b
      | (?i:\b(?:api[_-]?key|secret|token|password|passwd)\b)
        \s*[:=]\s*
        (?P<q>['"])(?P<val>[A-Za-z0-9_\-./+]{16,})(?P=q)
    )
    """
)

# Credential source and network sink in the same window, in either order.
# v0.1 required the source first, so `requests.post(url, data=os.environ)` --
# the idiomatic Python form -- was missed.
_CRED = r"(?:process\.env|os\.environ|getenv|~/\.ssh|id_rsa|id_ed25519|\.aws/credentials|\.npmrc)"
_SINK = r"(?:requests\.post|httpx\.post|urlopen|fetch\s*\(|axios\.|\bcurl\b|net/http|XMLHttpRequest|WebSocket)"
EXFIL_RE = re.compile(rf"(?i)(?:{_CRED}[^\n]{{0,160}}{_SINK}|{_SINK}[^\n]{{0,160}}{_CRED})")

# Reading an environment variable and putting it in a URL is ordinary
# configuration, not exfiltration, and it was 114 of the findings in the
# measured run. These forms are excluded before the sink test is applied.
EXFIL_BENIGN_RE = re.compile(
    r"(?i)(?:https?_proxy|all_proxy|no_proxy|base_?url|_host\b|_port\b|_endpoint\b"
    r"|proxy|NODE_ENV|PLAYWRIGHT|VERCEL_URL|PUBLIC_URL)"
)

# npm lifecycle hooks. `husky` and `husky install` are the standard git-hook
# installer and were reported as high severity on ordinary repositories.
BENIGN_INSTALL_HOOK_RE = re.compile(
    r"^\s*(?:husky(?:\s+install)?|patch-package|is-ci\s|node\s+-e\s+.{0,40}husky)\s*$",
    re.I,
)

# Where a finding sits changes what it means. Measured over 385 real
# repositories: of 273 `secret-like-string` findings, the overwhelming majority
# were placeholders and fixtures -- `AKIAIOSFODNN7EXAMPLE` (Amazon's own
# documentation key), `github_pat_xxxxxxxx`, a scanner's own rule fixtures, a
# test asserting that a value does not leak. Of 329 `remote-shell` findings,
# most were the project's documented install line in its README.
#
# None of those is a false positive: the pattern really is there, and a reader
# deciding whether to adopt a project may well want to know it asks them to
# pipe a remote script into a shell. What is wrong is the weight. A documented
# installer scored `critical` drives `AVOID` single-handedly, which is the
# tool reporting the genre of the file rather than the risk of the repository.
#
# So these findings are reported, at a severity that reflects the context, and
# the message says which context it was.
DOCUMENTATION_RE = re.compile(r"(?i)(?:^|/)(?:docs?|documentation|examples?|samples?)/|\.(?:md|rst|txt|adoc)(?::|$)")
FIXTURE_RE = re.compile(
    r"(?i)(?:^|/)(?:tests?|testing|spec|specs|__tests__|fixtures?|mocks?|testdata|examples?)/"
    r"|(?:^|/)(?:test_[^/]*|[^/]*_test|[^/]*\.test|[^/]*\.spec|conftest)\.[A-Za-z0-9]+(?::|$)"
)

# One step down the scale in `scoring._risk`: 70 -> 35 -> 15 -> 5.
_DOWNGRADE = {"critical": "medium", "high": "low", "medium": "low", "low": "low"}


def _context_of(rel: str) -> str | None:
    """`documentation`, `test fixture`, or None for the repository's own code."""
    if FIXTURE_RE.search(rel):
        return "test fixture"
    if DOCUMENTATION_RE.search(rel):
        return "documentation"
    return None


# How many findings one rule may report from one file. Without a cap a minified
# bundle reports the same pattern hundreds of times and buries everything else.
MAX_FINDINGS_PER_RULE_PER_FILE = 3

# Longest window handed to a regex. One minified line can be megabytes.
MAX_LINE_CHARS = 2000

# A repository vendoring 200 DLLs produced 200 findings and a 200-section
# report, and reached AVOID on the count alone.
MAX_BINARY_BLOB_FINDINGS = 5


def scan_path(path: Path | str) -> list[Finding]:
    root = Path(path)
    findings: list[Finding] = []
    binary_blobs = 0
    for file_path in _iter_files(root):
        rel = str(file_path.relative_to(root))
        if _looks_binary(file_path):
            if file_path.suffix.lower() in {".bin", ".exe", ".dll", ".dylib", ".so"}:
                binary_blobs += 1
                if binary_blobs > MAX_BINARY_BLOB_FINDINGS:
                    continue
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


# Directories whose contents are not the repository's own work, or are build
# output. `vendor`, `third_party` and `target` were missing, so findings in
# copied dependencies were reported against the repository that vendored them.
IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".tox", ".nox", ".next", ".gradle", ".terraform",
    "node_modules", "bower_components", "vendor", "third_party", "thirdparty",
    "venv", ".venv", "site-packages", "__pycache__", "dist", "build", "out",
    "target", "Pods", "coverage", "_build", "deps",
}


def _iter_files(root: Path):
    """Walk the repository, skipping directories that are not its own source.

    The name test is applied to the path RELATIVE to the scan root. Applied to
    the absolute path, as it was in v0.1, a repository that merely sat beneath
    a directory called `build` or `venv` had every one of its files skipped,
    and the report then stated "No static risk findings" about a scan that had
    opened nothing at all.
    """
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        try:
            relative_parts = file_path.relative_to(root).parts
        except ValueError:  # pragma: no cover - rglob yields paths under root
            continue
        if any(part in IGNORED_DIRS for part in relative_parts[:-1]):
            continue
        yield file_path


def _is_text_candidate(path: Path) -> bool:
    """Whether the file is read as text.

    Extension first, then a small set of conventional extensionless names, then
    a shebang. The shebang check opens the file, so it runs last and only for
    names that got no answer from the two cheap tests.
    """
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    if path.name in TEXT_FILENAMES:
        return True
    if path.name.startswith(".env") or ".env" in path.name:
        return True
    if path.name.startswith(".") and path.suffix == "":
        # .bashrc, .zshrc, .profile: dotfiles carry shell, and a dotfile repo is
        # entirely made of them.
        return True
    if path.suffix == "":
        return _has_shebang(path)
    return False


def _has_shebang(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return SHEBANG_RE.match(handle.read(64)) is not None
    except OSError:
        return False


def _read_text(path: Path) -> str:
    """Decode the file, honouring a byte-order mark.

    UTF-16 is what a file saved by a Windows editor looks like, and decoding it
    as UTF-8 turns every character into a replacement character with a NUL
    beside it, so every pattern missed. Checked in the planted-payload run:
    all four rules missed a UTF-16 file before this.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    for bom, encoding in (
        (b"\xff\xfe\x00\x00", "utf-32-le"),
        (b"\x00\x00\xfe\xff", "utf-32-be"),
        (b"\xff\xfe", "utf-16-le"),
        (b"\xfe\xff", "utf-16-be"),
        (b"\xef\xbb\xbf", "utf-8-sig"),
    ):
        if raw.startswith(bom):
            return raw.decode(encoding, errors="replace")
    return raw.decode("utf-8", errors="replace")


def _looks_binary(path: Path) -> bool:
    """Sniff the first 2 KB.

    `read_bytes()[:2048]` read the whole file into memory before discarding all
    but the first 2 KB, so sniffing a 3.5 MB bundle cost 3.5 MB. Read 2 KB.
    """
    try:
        with path.open("rb") as handle:
            chunk = handle.read(2048)
    except OSError:
        return False
    if not chunk:
        return False
    if chunk.startswith((b"\xff\xfe", b"\xfe\xff", b"\xef\xbb\xbf")):
        # A byte-order mark says this is text in a wide encoding. UTF-16 puts a
        # NUL beside every ASCII character, so the NUL test below would call
        # every Windows-saved file binary and skip it.
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
        if name not in scripts:
            continue
        body = str(scripts[name])
        if BENIGN_INSTALL_HOOK_RE.match(body):
            # `husky`, `husky install` and `patch-package` are the standard
            # hooks; reporting them as high severity made every ordinary
            # JavaScript repository look like a risk.
            continue
        findings.append(
            Finding(
                severity="medium",
                rule="package-install-hook",
                path=rel,
                message=f"Package install hook `{name}` runs during dependency installation",
                evidence=body[:200],
            )
        )
    return findings


def _windows(text: str):
    """Yield `(line_number, window)` pairs, one per line.

    The window is the line plus the next one, so a pattern whose two halves sit
    on consecutive lines is still found, while nothing can match across a whole
    file. Line length is capped: a minified bundle is one line of megabytes, and
    a bounded window there is the point of the exercise.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        if len(line) > MAX_LINE_CHARS:
            # Slide over the long line in overlapping chunks rather than
            # skipping it: minified installers are real, and so are minified
            # payloads.
            for start in range(0, len(line), MAX_LINE_CHARS // 2):
                yield index, line[start:start + MAX_LINE_CHARS], None
            continue
        following = lines[index] if index < len(lines) else ""
        if len(following) > MAX_LINE_CHARS:
            following = following[:MAX_LINE_CHARS]
        # `split_at` is where the second line begins inside the window, so a
        # match starting past it belongs to the next line. Reporting the
        # window's own start line put every such finding one line early.
        yield index, line + "\n" + following, len(line) + 1


def _scan_text(text: str, rel: str) -> list[Finding]:
    """Report each rule against bounded windows of the file.

    Every finding carries the line it was found on and the text that actually
    matched, capped at `MAX_FINDINGS_PER_RULE_PER_FILE` so one noisy file cannot
    fill a report.
    """
    checks = [
        ("critical", "remote-shell", "Remote shell execution pattern",
         (REMOTE_SHELL_RE, PROCESS_SUBSTITUTION_RE), None),
        ("critical", "obfuscated-execution", "Obfuscated decode plus execution pattern",
         (OBFUSCATED_EXEC_RE,), None),
        ("high", "secret-like-string", "Secret-like token string present",
         (SECRET_RE,), None),
        ("high", "possible-exfiltration", "Possible credential/network exfiltration pattern",
         (EXFIL_RE,), EXFIL_BENIGN_RE),
    ]
    findings: list[Finding] = []
    counts: dict[str, int] = {}
    # Windows overlap by one line, so the same match is reachable twice.
    seen: set[tuple[str, int, str]] = set()
    for line_no, window, split_at in _windows(text):
        for severity, rule, message, patterns, benign in checks:
            if counts.get(rule, 0) >= MAX_FINDINGS_PER_RULE_PER_FILE:
                continue
            for pattern in patterns:
                match = pattern.search(window)
                if not match:
                    continue
                matched = match.group(0)
                if benign is not None and benign.search(matched):
                    break
                reported_line = line_no
                if split_at is not None and match.start() >= split_at:
                    reported_line = line_no + 1
                key = (rule, reported_line, matched)
                if key in seen:
                    break
                seen.add(key)
                counts[rule] = counts.get(rule, 0) + 1
                context = _context_of(rel)
                findings.append(
                    Finding(
                        severity=_DOWNGRADE[severity] if context else severity,
                        rule=rule,
                        path=f"{rel}:{reported_line}",
                        message=(f"{message} (in {context}, so weighted lower)"
                                 if context else message),
                        evidence=matched.strip()[:200],
                    )
                )
                break
    return findings
