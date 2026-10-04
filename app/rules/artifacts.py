"""Rules covering the individual artifacts the zip folder must contain."""

from __future__ import annotations

import re

from ..models import Finding, Submission
from .base import Rule, register
from .patterns import CODE_ARCHIVE_PATTERN, GITHUB_URL_PATTERN, repository_name


@register
class CodeArchiveRule(Rule):
    id = "R03"
    title = "Zipped code in 04-Implementation"
    phases = (3,)
    reference = (
        "Chapter 4.2: in 04-Implementation you upload a zipped version with the "
        "naming convention Name-FirstName_MatrNo_Course_Submission_Code.zip"
    )

    def check(self, submission: Submission) -> Finding:
        implementation = submission.inner("04-Implementation")
        zips = [f for f in submission.files_under(implementation) if f.suffix == ".zip"]

        if not zips:
            return self.fail(
                "No ZIP file found in 04-Implementation.",
                "Zip your complete program code and place it in 04-Implementation as "
                "Surname-FirstName_MatrNo_Course_Submission_Code.zip.",
            )

        for candidate in zips:
            match = CODE_ARCHIVE_PATTERN.match(candidate.name)
            if not match:
                continue
            main = submission.main_directory
            if main and match.group("prefix") != main:
                return self.warn(
                    f"{candidate.name!r} is named correctly but its prefix does not "
                    f"match the main directory {main!r}.",
                    "Use the same Surname-FirstName_MatrNo_Course prefix for the main "
                    "directory and the code archive.",
                )
            return self.ok(f"Code archive {candidate.name!r} is named correctly.")

        found = ", ".join(repr(z.name) for z in zips)
        return self.fail(
            f"No correctly named code archive in 04-Implementation (found: {found}).",
            "Rename it to Surname-FirstName_MatrNo_Course_Submission_Code.zip, for "
            "example Mustermann-Max_12345678_PSE_Submission_Code.zip.",
        )


@register
class GitHubLinkRule(Rule):
    id = "R04"
    title = "GitHub link in .txt file"
    phases = (3,)
    reference = (
        "Chapter 4.1: a .txt file including the link to your public GitHub "
        "repository, and -- for a web application -- the link to the application"
    )

    def check(self, submission: Submission) -> Finding:
        txt_files = [f for f in submission.files if f.suffix == ".txt"]
        if not txt_files:
            return self.fail(
                "No .txt file found in the submission.",
                "Add a .txt file containing the URL of your public GitHub repository "
                "and, for a web application, the URL of the deployed app plus any "
                "login credentials.",
            )

        for candidate in txt_files:
            text = self._read(candidate.absolute)
            match = GITHUB_URL_PATTERN.search(text)
            if not match:
                continue
            repo = f"{match.group('user')}/{repository_name(match)}"
            if not self._mentions_app_url(text, match.start()):
                return self.warn(
                    f"{candidate.name!r} links the repository {repo} but contains no "
                    "second URL for the deployed application.",
                    "For a web application the same .txt must also contain the link to "
                    "the cloud-hosted front end, plus login data if access is "
                    "restricted.",
                )
            return self.ok(f"{candidate.name!r} links the repository {repo}.")

        names = ", ".join(repr(f.name) for f in txt_files)
        return self.fail(
            f"No GitHub repository URL found in any .txt file (checked: {names}).",
            "Write the full URL in the form https://github.com/<user>/<repository> "
            "into the .txt file.",
        )

    @staticmethod
    def _read(path) -> str:
        # Students hand in .txt files written by Windows editors, so tolerate
        # anything that is not clean UTF-8 rather than failing the check.
        return path.read_text(encoding="utf-8", errors="replace")

    @staticmethod
    def _mentions_app_url(text: str, github_start: int) -> bool:
        """True when the file holds a URL other than the GitHub repository one."""
        others = [
            m for m in re.finditer(r"https?://\S+", text) if m.start() != github_start
        ]
        return any("github.com" not in m.group(0) for m in others)
