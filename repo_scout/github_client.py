from __future__ import annotations

import http.client
import json
import urllib.parse
import urllib.request
import urllib.error
from typing import Callable

from .models import FileFetch, RepoSummary


Opener = Callable[[urllib.request.Request], object]


class GitHubClient:
    def __init__(self, opener: Opener | None = None):
        self.opener = opener or urllib.request.urlopen

    def search_repositories(self, query: str, limit: int = 10) -> list[RepoSummary]:
        params = urllib.parse.urlencode(
            {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": min(limit, 100),
            }
        )
        data = self._get_json(f"https://api.github.com/search/repositories?{params}")
        return [_repo_from_json(item) for item in data.get("items", [])]

    def get_repo(self, full_name: str) -> RepoSummary:
        data = self._get_json(f"https://api.github.com/repos/{full_name}")
        return _repo_from_json(data)

    def fetch_text_file(self, full_name: str, path: str, branch: str = "main") -> FileFetch:
        encoded_path = "/".join(urllib.parse.quote(part) for part in path.split("/"))
        url = f"https://raw.githubusercontent.com/{full_name}/{urllib.parse.quote(branch)}/{encoded_path}"
        request = self._request(url)
        try:
            with self.opener(request) as response:
                text = response.read().decode("utf-8", errors="replace")
                return FileFetch("present", text)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return FileFetch("absent")
            return FileFetch("unknown")
        except (OSError, urllib.error.URLError, http.client.HTTPException):
            return FileFetch("unknown")

    def _get_json(self, url: str) -> dict:
        request = self._request(url)
        try:
            with self.opener(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (
            OSError,
            urllib.error.URLError,
            json.JSONDecodeError,
            http.client.HTTPException,
            UnicodeDecodeError,
        ) as exc:
            raise GitHubClientError(f"public GitHub request failed: {exc}") from exc
        # Every caller reads fields out of an object. A body that parses and is
        # not one - an error page, a proxy's reply, a bare list - is a failed
        # request, not a repository, and is reported as one rather than reaching
        # `.get` and raising AttributeError.
        if not isinstance(payload, dict):
            raise GitHubClientError(
                "public GitHub request failed: response body was not a JSON object"
            )
        return payload

    @staticmethod
    def _request(url: str) -> urllib.request.Request:
        return urllib.request.Request(
            url,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "repo-scout/0.1",
            },
        )


def _repo_from_json(data: dict) -> RepoSummary:
    return RepoSummary(
        full_name=data.get("full_name", ""),
        description=data.get("description") or "",
        url=data.get("html_url", ""),
        stars=int(data.get("stargazers_count") or 0),
        forks=int(data.get("forks_count") or 0),
        open_issues=int(data.get("open_issues_count") or 0),
        pushed_at=data.get("pushed_at") or "",
        default_branch=data.get("default_branch") or "main",
    )


class GitHubClientError(RuntimeError):
    pass
