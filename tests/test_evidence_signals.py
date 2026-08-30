import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from repo_scout.cli import _fetch_signals, _local_signals
from repo_scout.models import FileFetch, RepoSummary


class SignalClient:
    def __init__(self, values):
        self.values = values

    def fetch_text_file(self, full_name, path, branch="main"):
        return self.values.get(path, FileFetch("absent"))


class EvidenceSignalTests(unittest.TestCase):
    def test_remote_variants_and_unknowns_are_preserved(self):
        client = SignalClient(
            {
                "README.rst": FileFetch("present", "Repo"),
                "LICENSE.md": FileFetch("present", "MIT"),
                "pyproject.toml": FileFetch("unknown"),
                "package.json": FileFetch("absent"),
                ".github/workflows/ci.yml": FileFetch("unknown"),
            }
        )
        repo = RepoSummary("owner/repo", "", "", default_branch="main")

        signals = _fetch_signals(client, repo)

        self.assertEqual(signals.has_readme, "present")
        self.assertEqual(signals.has_license, "present")
        self.assertEqual(signals.has_package_metadata, "unknown")
        self.assertEqual(signals.has_ci, "unknown")

    def test_local_absence_is_confirmed_without_stale_penalty(self):
        with TemporaryDirectory() as tmp:
            signals = _local_signals(Path(tmp))

        self.assertEqual(signals.has_readme, "absent")
        self.assertEqual(signals.has_license, "absent")
