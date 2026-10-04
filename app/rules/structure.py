"""Rules covering the prescribed folder structure of the zip folder."""

from __future__ import annotations

from ..models import REQUIRED_SUBDIRECTORIES, Finding, Submission
from .base import Rule, register


@register
class RequiredSubdirectoriesRule(Rule):
    id = "R02"
    title = "Required subdirectories"
    reference = "Chapter 4.2: subdirectories 01-Project-management ... 04-Implementation"

    def check(self, submission: Submission) -> list[Finding]:
        findings: list[Finding] = []
        present: list[str] = []

        for name, contents in REQUIRED_SUBDIRECTORIES.items():
            path = submission.inner(name)
            if submission.has_directory(path):
                present.append(name)
            else:
                near = self._near_miss(submission, name)
                hint = (
                    f" A folder named {near!r} exists -- the name must match exactly, "
                    "including the number prefix, capitalisation and hyphens."
                    if near
                    else ""
                )
                findings.append(
                    self.fail(
                        f"Subdirectory {name!r} is missing or empty.{hint}",
                        f"Create {name}/ inside the main directory and place the "
                        f"{contents} in it.",
                    )
                )

        if len(present) == len(REQUIRED_SUBDIRECTORIES):
            findings.append(self.ok("All four required subdirectories are present."))
        return findings

    def _near_miss(self, submission: Submission, expected: str) -> str | None:
        """Find an existing folder that differs only in case or separators."""
        normalised = self._normalise(expected)
        main = submission.main_directory
        for file in submission.files:
            parts = file.relpath.split("/")
            candidate = parts[1] if main and len(parts) > 2 else parts[0]
            if candidate != expected and self._normalise(candidate) == normalised:
                return candidate
        return None

    @staticmethod
    def _normalise(value: str) -> str:
        return value.lower().replace("-", "").replace("_", "").replace(" ", "")
