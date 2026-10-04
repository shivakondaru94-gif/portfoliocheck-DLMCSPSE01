"""Regular expressions shared by several rules.

The name/matriculation/course prefix appears in both the main directory name
and the code archive name, and the repository URL is read by two rules; keeping
each pattern in one place stops the rules drifting apart.
"""

from __future__ import annotations

import re

# "Surname-FirstName_MatrNo_Course", e.g. Mustermann-Max_12345678_PSE.
# [^\W\d_] is a unicode-aware "letter only" class, so German umlauts in a
# surname are accepted while digits and stray underscores are not.
_NAME = r"[^\W\d_]+(?:-[^\W\d_]+)+"
PREFIX = rf"(?P<name>{_NAME})_(?P<matr>\d{{6,10}})_(?P<course>[A-Za-z0-9]+)"

MAIN_DIR_PATTERN = re.compile(rf"^{PREFIX}$")

CODE_ARCHIVE_PATTERN = re.compile(rf"^(?P<prefix>{PREFIX})_Submission_Code\.zip$")

GITHUB_URL_PATTERN = re.compile(
    r"https://github\.com/(?P<user>[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?)"
    r"/(?P<repo>[A-Za-z0-9._-]+)"
)


def repository_name(match: re.Match) -> str:
    """Repository name from a GITHUB_URL_PATTERN match, without a .git suffix."""
    repo = match.group("repo")
    return repo[:-4] if repo.endswith(".git") else repo
