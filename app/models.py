"""Component: DomainModel -- provides ISubmissionModel.

Core domain types shared by the rule engine and the web layer. Depends on
no other component.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# The folder layout prescribed by chapter 4.2 of the brief: subdirectory name
# -> what belongs in it. Domain knowledge shared by rule R02 and the skeleton
# download, so it lives here rather than in either of them.
REQUIRED_SUBDIRECTORIES = {
    "01-Project-management": "project profile, project plans, project management documents",
    "02-Requirements": "requirements documents, glossary",
    "03-Architecture-documentation": "software and system documentation, all diagrams",
    "04-Implementation": "program code and related documentation",
}


class Severity(str, Enum):
    """Outcome of a single rule evaluation, ordered from best to worst."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

    @property
    def rank(self) -> int:
        return {"pass": 0, "warn": 1, "fail": 2}[self.value]


@dataclass(frozen=True)
class Finding:
    """One verdict produced by one rule.

    ``fix`` is the actionable remedy shown to the student; it is deliberately
    mandatory for anything worse than PASS, because a report that only says
    "wrong" is exactly the problem this application exists to solve.
    """

    rule_id: str
    title: str
    severity: Severity
    message: str
    fix: str | None = None
    # The provision of the assignment brief the rule derives from (FR11).
    reference: str = ""

    def __post_init__(self) -> None:
        if self.severity is not Severity.PASS and not self.fix:
            raise ValueError(f"{self.rule_id}: a non-passing finding must carry a fix")


@dataclass
class SubmissionFile:
    """A single file inside the extracted submission."""

    relpath: str  # POSIX-style, relative to the submission root
    size: int
    absolute: Path

    @property
    def name(self) -> str:
        return self.relpath.rsplit("/", 1)[-1]

    @property
    def suffix(self) -> str:
        return Path(self.relpath).suffix.lower()

    @property
    def top_level_dir(self) -> str | None:
        """First path segment, or None for files sitting at the root."""
        parts = self.relpath.split("/")
        return parts[0] if len(parts) > 1 else None


@dataclass
class Submission:
    """Everything the rules need to know about one uploaded ZIP."""

    original_filename: str
    root: Path
    files: list[SubmissionFile] = field(default_factory=list)
    # Declared by the student on the upload form; rules that only apply to a
    # given portfolio phase consult this.
    phase: int | None = None

    @property
    def stem(self) -> str:
        """Uploaded archive name without the .zip extension."""
        return Path(self.original_filename).stem

    @property
    def total_size(self) -> int:
        return sum(f.size for f in self.files)

    @property
    def top_level_dirs(self) -> set[str]:
        return {d for f in self.files if (d := f.top_level_dir) is not None}

    @property
    def main_directory(self) -> str | None:
        """The single wrapper folder, if the archive has exactly one.

        The brief requires the ZIP to contain one main directory named
        ``Surname-First_Name_MatrNo_Course``; an archive whose contents were
        zipped without that wrapper returns None and fails the structure rule.
        """
        stray_at_root = any(f.top_level_dir is None for f in self.files)
        dirs = self.top_level_dirs
        if len(dirs) == 1 and not stray_at_root:
            return next(iter(dirs))
        return None

    def inner(self, relpath: str) -> str:
        """Prefix ``relpath`` with the main directory when there is one."""
        main = self.main_directory
        return f"{main}/{relpath}" if main else relpath

    def files_under(self, directory: str) -> list[SubmissionFile]:
        prefix = directory.rstrip("/") + "/"
        return [f for f in self.files if f.relpath.startswith(prefix)]

    def has_directory(self, relpath: str) -> bool:
        return bool(self.files_under(relpath))


@dataclass
class Report:
    """Aggregate result for one submission."""

    submission_name: str
    phase: int | None
    findings: list[Finding]

    @property
    def overall(self) -> Severity:
        if not self.findings:
            return Severity.PASS
        return max((f.severity for f in self.findings), key=lambda s: s.rank)

    def count(self, severity: Severity) -> int:
        return sum(1 for f in self.findings if f.severity is severity)

    @property
    def fails(self) -> int:
        return self.count(Severity.FAIL)

    @property
    def warns(self) -> int:
        return self.count(Severity.WARN)

    @property
    def passes(self) -> int:
        return self.count(Severity.PASS)

    @property
    def sorted_findings(self) -> list[Finding]:
        """Worst first, so the student sees what actually blocks them."""
        return sorted(self.findings, key=lambda f: (-f.severity.rank, f.rule_id))
