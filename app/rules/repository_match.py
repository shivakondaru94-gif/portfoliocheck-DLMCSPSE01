"""Rule R07: the public repository and the submitted code archive are identical."""

from __future__ import annotations

import zipfile
from pathlib import PurePosixPath

from ..extraction import UnsafeArchive, inspect
from ..models import Finding, Submission, SubmissionFile
from ..repository import (
    GitHubRepositoryClient,
    RepositoryInventory,
    RepositoryNotFound,
    RepositoryUnavailable,
    blob_hash,
)
from .base import Rule, register
from .patterns import CODE_ARCHIVE_PATTERN, GITHUB_URL_PATTERN, repository_name

# Archive entries that archiving tools add on their own and that can never be
# part of a repository tree.
IGNORED_PREFIXES = ("__MACOSX/", ".git/")
IGNORED_NAMES = {".DS_Store", "Thumbs.db"}
# How many differing paths to name in a finding before summarising.
SHOW_AT_MOST = 5


@register
class RepositoryMatchRule(Rule):
    id = "R07"
    title = "GitHub repository matches code archive"
    phases = (3,)
    reference = (
        "Chapter 1.1.3: the content of the GitHub repository and the contents of "
        "the ZIP file uploaded to your zip folder should be identical"
    )

    def __init__(self, client: RepositoryInventory | None = None) -> None:
        # Replaceable so that tests, and deployments without network access,
        # can supply another IRepositoryInventory.
        self.client: RepositoryInventory = client or GitHubRepositoryClient()

    def check(self, submission: Submission) -> Finding:
        url = self._repository_url(submission)
        archive = self._code_archive(submission)
        if url is None or archive is None:
            missing = "the GitHub link (R04)" if url is None else "the code archive (R03)"
            return self.warn(
                f"The comparison could not run because {missing} was not found.",
                "Fix the findings for R03 and R04 first; this check then runs "
                "automatically.",
            )
        owner, repo = url

        try:
            local = self._archive_hashes(archive)
        except (zipfile.BadZipFile, UnsafeArchive) as exc:
            return self.fail(
                f"The code archive {archive.name!r} could not be read: {exc}",
                "Recreate the code archive from the files in your repository "
                "using an ordinary ZIP tool.",
            )

        try:
            remote = self.client.inventory(owner, repo)
        except RepositoryNotFound:
            return self.fail(
                f"The repository {owner}/{repo} does not exist or is not public.",
                "Check the URL in your .txt file and make sure the repository "
                "visibility is set to Public on GitHub.",
            )
        except RepositoryUnavailable as exc:
            return self.warn(
                f"GitHub could not be reached, so {owner}/{repo} was not compared "
                f"({exc}).",
                "Run the check again later. If it keeps failing, compare the "
                "repository and the code archive by hand before submitting.",
            )

        local = _strip_wrapper(local, set(remote.blobs))
        return self._compare(local, remote.blobs, f"{owner}/{repo}", remote.truncated)

    # -- comparison -----------------------------------------------------------

    def _compare(
        self,
        local: dict[str, tuple[str, str]],
        remote: dict[str, str],
        name: str,
        truncated: bool,
    ) -> Finding:
        only_remote = sorted(set(remote) - set(local))
        only_local = sorted(set(local) - set(remote))
        # A file counts as identical if its bytes match, or if they match once
        # Windows line endings are normalised -- git itself performs that
        # conversion on checkout, so a CRLF copy is the same file.
        differ = sorted(
            path
            for path in set(local) & set(remote)
            if remote[path] not in local[path]
        )

        if not (only_remote or only_local or differ):
            if truncated:
                return self.warn(
                    f"All {len(local)} files compared match {name}, but GitHub "
                    "returned only part of the repository tree.",
                    "Very large repositories cannot be compared completely; "
                    "check that no files are missing from the archive by hand.",
                )
            return self.ok(
                f"All {len(local)} files in the code archive are identical to {name}."
            )

        parts = []
        if only_remote:
            parts.append(f"{len(only_remote)} only in the repository ({_sample(only_remote)})")
        if only_local:
            parts.append(f"{len(only_local)} only in the archive ({_sample(only_local)})")
        if differ:
            parts.append(f"{len(differ)} with different content ({_sample(differ)})")
        return self.fail(
            f"The code archive and {name} are not identical: " + "; ".join(parts) + ".",
            "Commit and push every change, then create the code archive again from "
            "the repository (for example with GitHub's Download ZIP) so that both "
            "contain exactly the same files.",
        )

    # -- inputs ---------------------------------------------------------------

    @staticmethod
    def _repository_url(submission: Submission) -> tuple[str, str] | None:
        for file in submission.files:
            if file.suffix != ".txt":
                continue
            text = file.absolute.read_text(encoding="utf-8", errors="replace")
            match = GITHUB_URL_PATTERN.search(text)
            if match:
                return match.group("user"), repository_name(match)
        return None

    @staticmethod
    def _code_archive(submission: Submission) -> SubmissionFile | None:
        zips = [
            f
            for f in submission.files_under(submission.inner("04-Implementation"))
            if f.suffix == ".zip"
        ]
        # Prefer the correctly named archive, but compare any archive found so
        # that a naming mistake (reported by R03) does not hide a content one.
        named = [f for f in zips if CODE_ARCHIVE_PATTERN.match(f.name)]
        return (named or zips or [None])[0]

    @staticmethod
    def _archive_hashes(archive: SubmissionFile) -> dict[str, tuple[str, str]]:
        """Map each file in the nested archive to (raw hash, LF-normalised hash)."""
        hashes: dict[str, tuple[str, str]] = {}
        with zipfile.ZipFile(archive.absolute) as nested:
            # The nested archive is as untrusted as the outer one.
            inspect(nested)
            for info in nested.infolist():
                name = info.filename
                if info.is_dir() or name.startswith(IGNORED_PREFIXES):
                    continue
                if PurePosixPath(name).name in IGNORED_NAMES:
                    continue
                content = nested.read(info)
                hashes[name] = (
                    blob_hash(content),
                    blob_hash(content.replace(b"\r\n", b"\n")),
                )
        return hashes


def _strip_wrapper(
    local: dict[str, tuple[str, str]], remote_paths: set[str]
) -> dict[str, tuple[str, str]]:
    """Drop a single top-level folder that wraps the whole archive.

    GitHub's own "Download ZIP" puts every file under ``<repo>-<branch>/``; that
    folder is packaging, not content, unless the repository itself has it.
    """
    tops = {path.split("/", 1)[0] for path in local}
    if len(tops) != 1 or all("/" not in path for path in local):
        return local
    wrapper = next(iter(tops)) + "/"
    if any(path.startswith(wrapper) for path in remote_paths):
        return local
    return {path[len(wrapper):]: value for path, value in local.items()}


def _sample(paths: list[str]) -> str:
    shown = ", ".join(paths[:SHOW_AT_MOST])
    return shown + (f", and {len(paths) - SHOW_AT_MOST} more" if len(paths) > SHOW_AT_MOST else "")
