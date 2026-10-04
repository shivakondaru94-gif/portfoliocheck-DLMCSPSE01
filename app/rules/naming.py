"""Rules covering the prescribed naming conventions."""

from __future__ import annotations

from ..models import Finding, Submission
from .base import Rule, register
from .patterns import MAIN_DIR_PATTERN


@register
class MainDirectoryNameRule(Rule):
    id = "R01"
    title = "Main directory name"
    reference = (
        "Chapter 4.2: Main directory (name of the zip folder) -> "
        "Name-First_Name_Matriculation_Course"
    )

    def check(self, submission: Submission) -> Finding:
        main = submission.main_directory
        if main is None:
            return self.fail(
                "The archive does not contain exactly one main directory; files or "
                "several folders sit at the top level.",
                "Put everything inside a single folder named "
                "Surname-FirstName_MatrNo_Course (e.g. Mustermann-Max_12345678_PSE) "
                "and zip that folder.",
            )

        match = MAIN_DIR_PATTERN.match(main)
        if not match:
            return self.fail(
                f"Main directory {main!r} does not follow the required pattern.",
                "Rename it to Surname-FirstName_MatrNo_Course, for example "
                "Mustermann-Max_12345678_PSE. Use a hyphen between surname and first "
                "name, and underscores between the other parts.",
            )

        if len(match.group("matr")) != 8:
            return self.warn(
                f"Matriculation number {match.group('matr')!r} is not 8 digits long.",
                "Check your matriculation number on myCampus; the examples in the "
                "brief use 8 digits.",
            )

        return self.ok(f"Main directory {main!r} follows the required pattern.")
