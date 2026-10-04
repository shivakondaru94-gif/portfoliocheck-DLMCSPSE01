"""Component: RuleRegistry -- provides IRuleCatalogue; defines IRule.

Rule abstraction and registry.

Every formal requirement from the portfolio brief is expressed as one small,
independently testable Rule. Adding a requirement means adding a class and
registering it -- nothing else in the system changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Finding, Severity, Submission


class Rule(ABC):
    """A single checkable requirement from the portfolio brief."""

    id: str
    title: str
    # Portfolio phases this rule applies to. Rules that hold for every phase
    # list all three.
    phases: tuple[int, ...] = (1, 2, 3)
    # Where the requirement comes from, quoted in the report so students can
    # verify the rule against the official document themselves.
    reference: str = ""

    def applies_to(self, submission: Submission) -> bool:
        """Whether this rule should run for the given submission."""
        if submission.phase is None:
            return True
        return submission.phase in self.phases

    @abstractmethod
    def check(self, submission: Submission) -> Finding | list[Finding]:
        """Evaluate the rule. Must return at least one Finding."""

    # -- helpers for subclasses -------------------------------------------------

    def ok(self, message: str) -> Finding:
        return Finding(self.id, self.title, Severity.PASS, message, reference=self.reference)

    def warn(self, message: str, fix: str) -> Finding:
        return Finding(self.id, self.title, Severity.WARN, message, fix, self.reference)

    def fail(self, message: str, fix: str) -> Finding:
        return Finding(self.id, self.title, Severity.FAIL, message, fix, self.reference)


_REGISTRY: list[Rule] = []


def register(rule_cls: type[Rule]) -> type[Rule]:
    """Class decorator that adds a rule to the global registry."""
    _REGISTRY.append(rule_cls())
    return rule_cls


def all_rules() -> list[Rule]:
    return sorted(_REGISTRY, key=lambda r: r.id)
