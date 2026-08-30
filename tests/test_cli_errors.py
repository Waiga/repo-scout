import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from repo_scout.cache import FileCache
from repo_scout.cli import (
    main,
    run_download_command,
    run_inspect_command,
    run_scan_command,
    run_search_command,
)
from repo_scout.github_client import GitHubClientError


class FailingClient:
    def search_repositories(self, query, limit=10):
        raise GitHubClientError("public GitHub request failed: certificate verify failed")


class CliErrorTests(unittest.TestCase):
    def test_search_command_handles_github_client_error(self):
        code = run_search_command("codex plugin", 3, FailingClient())

        self.assertEqual(code, 1)

    def test_scan_rejects_missing_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            code = run_scan_command(missing, Path(tmp) / "reports")

        self.assertEqual(code, 2)

    def test_inspect_rejects_malformed_repo_before_client_call(self):
        client = Mock()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code = run_inspect_command("not-a-repo", client, root / "reports", FileCache(root / "cache"))

        self.assertEqual(code, 2)
        client.get_repo.assert_not_called()

    def test_rejects_path_traversal_and_shell_characters_before_download(self):
        with tempfile.TemporaryDirectory() as tmp, patch("repo_scout.cli.shutil.which") as which:
            for repo_name in ("../repo", "owner/../repo", "owner/repo/extra", "owner\\repo", "owner/repo;echo pwned"):
                self.assertEqual(run_download_command(repo_name, Path(tmp)), 2)

        which.assert_not_called()

    def test_rejects_dot_only_components_before_client_or_git(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("repo_scout.cli.shutil.which") as which, \
             patch("repo_scout.cli.subprocess.run") as run:
            root = Path(tmp)
            for repo_name in ("./repo", "owner/.", "./."):
                client = Mock()
                code = run_inspect_command(repo_name, client, root / "reports", FileCache(root / "cache"))
                self.assertEqual(code, 2)
                client.get_repo.assert_not_called()
                self.assertEqual(run_download_command(repo_name, root), 2)

        which.assert_not_called()
        run.assert_not_called()

    def test_main_rejects_malformed_inspect_before_initializing_dependencies(self):
        with patch("repo_scout.cli.GitHubClient") as client, patch("repo_scout.cli.FileCache") as cache:
            code = main(["inspect", "not-a-repo"])

        self.assertEqual(code, 2)
        client.assert_not_called()
        cache.assert_not_called()

    def test_scan_rejects_regular_file_without_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "repo-file"
            path.write_text("not a directory")
            reports = root / "reports"

            code = run_scan_command(path, reports)

        self.assertEqual(code, 2)
        self.assertFalse(reports.exists())

    def test_existing_download_destination_skips_git_lookup_and_run(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("repo_scout.cli.shutil.which") as which, \
             patch("repo_scout.cli.subprocess.run") as run:
            root = Path(tmp)
            (root / "owner__repo").mkdir()

            code = run_download_command("owner/repo", root)

        self.assertEqual(code, 0)
        which.assert_not_called()
        run.assert_not_called()

    def test_missing_git_reports_operational_failure_without_subprocess(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("repo_scout.cli.shutil.which", return_value=None), \
             patch("repo_scout.cli.subprocess.run") as run:
            code = run_download_command("owner/repo", Path(tmp))

        self.assertEqual(code, 1)
        run.assert_not_called()

    def test_download_reports_clone_failure(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("repo_scout.cli.shutil.which", return_value="/usr/bin/git"), \
             patch("repo_scout.cli.subprocess.run", side_effect=subprocess.CalledProcessError(1, ["git"])):
            code = run_download_command("owner/repo", Path(tmp))

        self.assertEqual(code, 1)

    def test_download_uses_argument_list_and_shallow_clone(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("repo_scout.cli.shutil.which", return_value="/usr/bin/git"), \
             patch("repo_scout.cli.subprocess.run") as run:
            root = Path(tmp)
            code = run_download_command("owner/repo", root)

        self.assertEqual(code, 0)
        run.assert_called_once_with(
            ["/usr/bin/git", "clone", "--depth", "1", "https://github.com/owner/repo.git", str(root / "owner__repo")],
            check=True,
        )

    def test_rejects_consecutive_dot_names_before_client_or_git(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("repo_scout.cli.shutil.which") as which, \
             patch("repo_scout.cli.subprocess.run") as run:
            root = Path(tmp)
            for repo_name in ("owner..name/repo", "owner/repo..name", "..owner/repo", "owner/repo.."):
                client = Mock()
                code = run_inspect_command(repo_name, client, root / "reports", FileCache(root / "cache"))
                self.assertEqual(code, 2, repo_name)
                client.get_repo.assert_not_called()
                self.assertEqual(run_download_command(repo_name, root), 2, repo_name)

        which.assert_not_called()
        run.assert_not_called()

    def test_accepts_ordinary_dotted_names(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch("repo_scout.cli.shutil.which", return_value=None) as which:
            code = run_download_command("owner.name/repo.name", Path(tmp))

        self.assertEqual(code, 1)
        which.assert_called_once_with("git")


if __name__ == "__main__":
    unittest.main()
