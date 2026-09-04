import http.client
import json
import unittest
import urllib.error
from io import BytesIO

from repo_scout.github_client import GitHubClient, GitHubClientError


class FakeResponse:
    def __init__(self, payload: bytes):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.payload


class TruncatedResponse(FakeResponse):
    def __init__(self):
        super().__init__(b"")

    def read(self):
        raise http.client.IncompleteRead(b"partial", 10)


class MissingOpener:
    def __call__(self, request):
        error = urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, BytesIO())
        error.close()
        raise error


class UnavailableOpener:
    def __call__(self, request):
        raise urllib.error.URLError("network unavailable")


class GitHubClientTests(unittest.TestCase):
    def test_non_object_json_body_is_a_client_error_not_a_crash(self):
        # A body that parses but is not an object still fails every caller:
        # `search_repositories` calls `.get` on it and `get_repo` reads fields
        # out of it. A proxy or an error page can produce one, and it belongs
        # with the other transport failures rather than as an AttributeError.
        client = GitHubClient(opener=lambda request: FakeResponse(b'["not an object"]'))

        with self.assertRaises(GitHubClientError):
            client.search_repositories("codex plugin")
        with self.assertRaises(GitHubClientError):
            client.get_repo("owner/repo")


    def test_search_repositories_maps_summary_fields(self):
        payload = {
            "items": [
                {
                    "full_name": "owner/repo",
                    "description": "AI agent automation",
                    "html_url": "https://github.com/owner/repo",
                    "stargazers_count": 12,
                    "forks_count": 3,
                    "open_issues_count": 1,
                    "pushed_at": "2026-07-01T00:00:00Z",
                    "default_branch": "main",
                }
            ]
        }

        client = GitHubClient(opener=lambda req: FakeResponse(json.dumps(payload).encode()))
        results = client.search_repositories("ai agent")

        self.assertEqual(results[0].full_name, "owner/repo")
        self.assertEqual(results[0].stars, 12)

    def test_fetch_text_file_returns_text(self):
        client = GitHubClient(opener=lambda req: FakeResponse(b"# Readme"))

        result = client.fetch_text_file("owner/repo", "README.md", "main")

        self.assertEqual(result.status, "present")
        self.assertEqual(result.text, "# Readme")

    def test_file_fetch_states(self):
        present = GitHubClient(opener=lambda req: FakeResponse(b"# Readme"))
        missing = GitHubClient(opener=MissingOpener())
        unavailable = GitHubClient(opener=UnavailableOpener())

        self.assertEqual(present.fetch_text_file("owner/repo", "README.md").status, "present")
        self.assertEqual(missing.fetch_text_file("owner/repo", "README.md").status, "absent")
        self.assertEqual(unavailable.fetch_text_file("owner/repo", "README.md").status, "unknown")

    def test_truncated_file_response_is_unknown(self):
        client = GitHubClient(opener=lambda req: TruncatedResponse())

        result = client.fetch_text_file("owner/repo", "README.md")

        self.assertEqual(result.status, "unknown")
        self.assertIsNone(result.text)


class TruncatedJsonOpener:
    """Cuts the response short mid-body, as a dropped connection does."""

    def __call__(self, request):
        raise http.client.IncompleteRead(b'{"items": [')


class UndecodableOpener:
    def __call__(self, request):
        return FakeResponse(b"\xff\xfe not utf-8")


class JsonFailureTests(unittest.TestCase):
    def test_truncated_search_response_is_an_operational_failure(self):
        client = GitHubClient(opener=TruncatedJsonOpener())

        with self.assertRaises(GitHubClientError):
            client.search_repositories("anything")

    def test_undecodable_response_is_an_operational_failure(self):
        client = GitHubClient(opener=UndecodableOpener())

        with self.assertRaises(GitHubClientError):
            client.search_repositories("anything")


if __name__ == "__main__":
    unittest.main()
