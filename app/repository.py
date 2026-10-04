"""Component: RepositoryClient -- provides IRepositoryInventory (FR12).

Retrieves the file inventory of a public GitHub repository so that it can be
compared with the code archive in a submission. Every file is identified by its
git blob hash, which lets two inventories be compared for identical *content*
without downloading a single file from the repository.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

API_ROOT = "https://api.github.com"
# Kept short so an unreachable service cannot push a check past NFR5.
TIMEOUT_SECONDS = 2.5


@dataclass(frozen=True)
class Inventory:
    """The files of one repository snapshot: path -> git blob hash."""

    owner: str
    repo: str
    ref: str
    blobs: dict[str, str]
    # GitHub truncates very large trees; a truncated inventory is incomplete.
    truncated: bool = False


class RepositoryNotFound(Exception):
    """The repository does not exist or is not public."""


class RepositoryUnavailable(Exception):
    """The hosting service could not be reached or refused the request."""


class RepositoryInventory(Protocol):
    """IRepositoryInventory: anything that can list a repository's files."""

    def inventory(self, owner: str, repo: str) -> Inventory: ...


def blob_hash(content: bytes) -> str:
    """The git blob hash of ``content`` -- identical to ``git hash-object``."""
    header = b"blob %d\0" % len(content)
    return hashlib.sha1(header + content).hexdigest()


class GitHubRepositoryClient:
    """IRepositoryInventory backed by the public GitHub REST API.

    Anonymous requests are limited to 60 per hour per IP address. Setting the
    GITHUB_TOKEN environment variable raises that limit; the token needs no
    scopes because only public repositories are read.
    """

    def __init__(self, token: str | None = None, timeout: float = TIMEOUT_SECONDS) -> None:
        self._token = token if token is not None else os.environ.get("GITHUB_TOKEN")
        self._timeout = timeout

    def inventory(self, owner: str, repo: str) -> Inventory:
        meta = self._get(f"/repos/{owner}/{repo}")
        ref = meta["default_branch"]
        tree = self._get(f"/repos/{owner}/{repo}/git/trees/{ref}?recursive=1")
        blobs = {
            entry["path"]: entry["sha"]
            for entry in tree.get("tree", [])
            # "tree" entries are directories, "commit" entries are submodules;
            # neither has content that could appear in the code archive.
            if entry.get("type") == "blob"
        }
        return Inventory(owner, repo, ref, blobs, bool(tree.get("truncated")))

    def _get(self, path: str) -> dict:
        request = urllib.request.Request(
            API_ROOT + path,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "PortfolioCheck",
                **({"Authorization": f"Bearer {self._token}"} if self._token else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise RepositoryNotFound(path) from exc
            raise RepositoryUnavailable(f"HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise RepositoryUnavailable(str(exc)) from exc
