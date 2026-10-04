"""Rule-level tests: one scenario per formal requirement."""

from __future__ import annotations

import pytest

from app import checker
from app.models import Severity

from .conftest import MAIN, MINIMAL_PDF, VALID_PHASE_3


def finding_for(report, rule_id):
    """The single finding for a rule (fails loudly if a rule produced several)."""
    matches = [f for f in report.findings if f.rule_id == rule_id]
    assert matches, f"no finding produced for {rule_id}"
    return matches[0]


def without(key):
    return {k: v for k, v in VALID_PHASE_3.items() if k != key}


def renamed(old, new):
    return {(new if k == old else k): v for k, v in VALID_PHASE_3.items()}


# -- happy path ---------------------------------------------------------------


def test_valid_submission_passes_every_rule(valid_submission):
    report = checker.run(valid_submission)
    assert report.overall is Severity.PASS, [
        (f.rule_id, f.message) for f in report.findings if f.severity is not Severity.PASS
    ]


# -- R01 main directory -------------------------------------------------------


@pytest.mark.parametrize(
    "bad_name",
    [
        "MustermannMax_12345678_PSE",  # missing hyphen between surname and first name
        "Mustermann-Max-12345678-PSE",  # hyphens instead of underscores
        "Mustermann-Max_12345678",  # course missing
        "submission",  # not even close
    ],
)
def test_main_directory_name_must_match_pattern(make_submission, bad_name):
    files = {k.replace(MAIN, bad_name, 1): v for k, v in VALID_PHASE_3.items()}
    report = checker.run(make_submission(files))
    assert finding_for(report, "R01").severity is Severity.FAIL


def test_files_at_archive_root_are_rejected(make_submission):
    files = dict(VALID_PHASE_3)
    files["stray_notes.txt"] = b"oops"
    report = checker.run(make_submission(files))
    assert finding_for(report, "R01").severity is Severity.FAIL


def test_unusual_matriculation_length_only_warns(make_submission):
    files = {k.replace("12345678", "123456", 1): v for k, v in VALID_PHASE_3.items()}
    report = checker.run(make_submission(files))
    assert finding_for(report, "R01").severity is Severity.WARN


def test_umlauts_in_surname_are_accepted(make_submission):
    files = {k.replace("Mustermann", "Müller", 1): v for k, v in VALID_PHASE_3.items()}
    report = checker.run(make_submission(files))
    assert finding_for(report, "R01").severity is Severity.PASS


# -- R02 folder structure -----------------------------------------------------


def test_missing_subdirectory_fails(make_submission):
    files = without(f"{MAIN}/02-Requirements/requirements.pdf")
    report = checker.run(make_submission(files))
    failures = [f for f in report.findings if f.rule_id == "R02"]
    assert len(failures) == 1
    assert failures[0].severity is Severity.FAIL
    assert "02-Requirements" in failures[0].message


def test_near_miss_folder_name_is_called_out(make_submission):
    files = renamed(
        f"{MAIN}/02-Requirements/requirements.pdf",
        f"{MAIN}/02_requirements/requirements.pdf",
    )
    report = checker.run(make_submission(files))
    finding = finding_for(report, "R02")
    assert finding.severity is Severity.FAIL
    assert "02_requirements" in finding.message


# -- R03 code archive ---------------------------------------------------------


def test_missing_code_archive_fails(make_submission):
    files = without(f"{MAIN}/04-Implementation/{MAIN}_Submission_Code.zip")
    files[f"{MAIN}/04-Implementation/readme.pdf"] = MINIMAL_PDF
    report = checker.run(make_submission(files))
    assert finding_for(report, "R03").severity is Severity.FAIL


def test_wrongly_named_code_archive_fails(make_submission):
    files = renamed(
        f"{MAIN}/04-Implementation/{MAIN}_Submission_Code.zip",
        f"{MAIN}/04-Implementation/code.zip",
    )
    report = checker.run(make_submission(files))
    finding = finding_for(report, "R03")
    assert finding.severity is Severity.FAIL
    assert "code.zip" in finding.message


def test_code_archive_prefix_mismatch_warns(make_submission):
    files = renamed(
        f"{MAIN}/04-Implementation/{MAIN}_Submission_Code.zip",
        f"{MAIN}/04-Implementation/Mustermann-Erika_87654321_PSE_Submission_Code.zip",
    )
    report = checker.run(make_submission(files))
    assert finding_for(report, "R03").severity is Severity.WARN


def test_code_archive_not_checked_in_phase_1(make_submission):
    files = without(f"{MAIN}/04-Implementation/{MAIN}_Submission_Code.zip")
    files[f"{MAIN}/04-Implementation/notes.pdf"] = MINIMAL_PDF
    report = checker.run(make_submission(files, phase=1))
    assert not [f for f in report.findings if f.rule_id == "R03"]


# -- R04 GitHub link ----------------------------------------------------------


def test_missing_txt_file_fails(make_submission):
    report = checker.run(make_submission(without(f"{MAIN}/links.txt")))
    assert finding_for(report, "R04").severity is Severity.FAIL


def test_txt_without_github_url_fails(make_submission):
    files = dict(VALID_PHASE_3)
    files[f"{MAIN}/links.txt"] = b"see my repository, it is called pse_myproject"
    report = checker.run(make_submission(files))
    assert finding_for(report, "R04").severity is Severity.FAIL


def test_txt_without_application_url_warns(make_submission):
    files = dict(VALID_PHASE_3)
    files[f"{MAIN}/links.txt"] = b"https://github.com/maxmustermann/pse_myproject\n"
    report = checker.run(make_submission(files))
    assert finding_for(report, "R04").severity is Severity.WARN


def test_txt_with_invalid_encoding_does_not_crash(make_submission):
    files = dict(VALID_PHASE_3)
    files[f"{MAIN}/links.txt"] = (
        b"\xff\xfe Repository: https://github.com/maxmustermann/pse\n"
        b"App: https://example.onrender.com\n"
    )
    report = checker.run(make_submission(files))
    assert finding_for(report, "R04").severity is Severity.PASS


# -- R05 PDF integrity --------------------------------------------------------


def test_renamed_docx_is_detected(make_submission):
    files = dict(VALID_PHASE_3)
    files[f"{MAIN}/01-Project-management/profile.pdf"] = b"PK\x03\x04 this is really a docx"
    report = checker.run(make_submission(files))
    finding = finding_for(report, "R05")
    assert finding.severity is Severity.FAIL
    assert "profile.pdf" in finding.message


# -- R06 file size ------------------------------------------------------------


def test_oversized_file_fails(make_submission):
    files = dict(VALID_PHASE_3)
    files[f"{MAIN}/03-Architecture-documentation/architecture.pdf"] = (
        MINIMAL_PDF + b"\x00" * (16 * 1024 * 1024)
    )
    report = checker.run(make_submission(files))
    finding = finding_for(report, "R06")
    assert finding.severity is Severity.FAIL
    assert "architecture.pdf" in finding.message


# -- NFR8 resilience ----------------------------------------------------------


def test_failing_rule_does_not_stop_the_others(valid_submission, monkeypatch):
    from app.rules.base import Rule

    class ExplodingRule(Rule):
        id = "R99"
        title = "Deliberately broken rule"
        reference = "test only"

        def check(self, submission):
            raise RuntimeError("boom")

    real_rules = checker.all_rules()
    monkeypatch.setattr(checker, "all_rules", lambda: [ExplodingRule(), *real_rules])

    report = checker.run(valid_submission)

    broken = finding_for(report, "R99")
    assert broken.severity is Severity.WARN
    assert broken.fix  # the student is still told what to do
    evaluated = {f.rule_id for f in report.findings}
    assert {"R01", "R02", "R03", "R04", "R05", "R06", "R07"} <= evaluated


# -- NFR5 performance ---------------------------------------------------------


def test_typical_submission_is_checked_within_three_seconds(valid_submission):
    import time

    started = time.perf_counter()
    checker.run(valid_submission)
    assert time.perf_counter() - started < 3.0


# -- FR11 provenance ----------------------------------------------------------


def test_every_finding_names_its_source_provision(valid_submission):
    report = checker.run(valid_submission)
    assert all(f.reference for f in report.findings)
