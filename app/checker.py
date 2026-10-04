"""Component: CheckService -- provides ICheckService.

The rule engine: runs every applicable rule against a submission and
aggregates the findings into a Report.
"""

from __future__ import annotations

import logging

from .models import Finding, Report, Severity, Submission
from .rules import all_rules

logger = logging.getLogger(__name__)


def run(submission: Submission) -> Report:
    """Evaluate every applicable rule and collect the findings.

    A rule that raises is reported as a WARN rather than taking the whole
    report down: a partial report is still useful to the student.
    """
    findings: list[Finding] = []

    for rule in all_rules():
        if not rule.applies_to(submission):
            continue
        try:
            result = rule.check(submission)
        except Exception:
            logger.exception("Rule %s failed", rule.id)
            findings.append(
                Finding(
                    rule.id,
                    rule.title,
                    Severity.WARN,
                    "This check could not be completed.",
                    "Verify this requirement manually against the assignment brief.",
                    rule.reference,
                )
            )
            continue

        findings.extend(result if isinstance(result, list) else [result])

    return Report(
        submission_name=submission.original_filename,
        phase=submission.phase,
        findings=findings,
    )
