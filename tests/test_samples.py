"""The sample submissions produce exactly the outcome documented for them.

samples/README.md specifies each manual test case as an input archive, a phase
and an expected result. This test executes those specifications, so the
documented expectations cannot drift away from the application's behaviour.
R07 is excluded from the expectations: its outcome for the samples depends on
a live repository and is covered with a fake repository in test_repository.py.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

SAMPLES = Path(__file__).parent.parent / "samples"

# file, phase, expected verdict per rule (R07 deliberately omitted)
CASES = [
    ("M01-phase1-compliant.zip", "1",
     {"R01": "pass", "R02": "pass", "R05": "pass", "R06": "pass"}),
    ("M02-phase1-main-directory-underscore.zip", "1",
     {"R01": "fail", "R02": "pass", "R05": "pass", "R06": "pass"}),
    ("M03-phase1-near-miss-folder.zip", "1",
     {"R01": "pass", "R02": "fail", "R05": "pass", "R06": "pass"}),
    ("M04-phase1-short-matriculation.zip", "1",
     {"R01": "warn", "R02": "pass", "R05": "pass", "R06": "pass"}),
    ("M05-phase2-renamed-docx.zip", "2",
     {"R01": "pass", "R02": "pass", "R05": "fail", "R06": "pass"}),
    ("M06-phase3-wrong-code-archive-name.zip", "3",
     {"R01": "pass", "R02": "pass", "R03": "fail", "R04": "pass", "R05": "pass", "R06": "pass"}),
    ("M07-phase3-missing-application-link.zip", "3",
     {"R01": "pass", "R02": "pass", "R03": "pass", "R04": "warn", "R05": "pass", "R06": "pass"}),
]

# The "Expected message contains" column of samples/README.md
MESSAGES = {
    "M01-phase1-compliant.zip": "follows the required pattern",
    "M02-phase1-main-directory-underscore.zip": "does not follow the required pattern",
    "M03-phase1-near-miss-folder.zip": "A folder named &#39;02_requirements&#39; exists",
    "M04-phase1-short-matriculation.zip": "is not 8 digits long",
    "M05-phase2-renamed-docx.zip": "has a .pdf extension but is not a PDF file",
    "M06-phase3-wrong-code-archive-name.zip": "No correctly named code archive",
    "M07-phase3-missing-application-link.zip": "contains no second URL for the deployed application",
}

HEADLINE = {"pass": "Ready to submit", "warn": "Almost there", "fail": "Not ready to submit"}


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def verdicts(html: str) -> dict[str, list[str]]:
    """Rule id -> the list of severities rendered for it in the report."""
    found: dict[str, list[str]] = {}
    for rule_id, status in re.findall(
        r'<span class="rule-id">(R\d+)</span>.*?status--(pass|warn|fail)', html, re.S
    ):
        found.setdefault(rule_id, []).append(status)
    return found


@pytest.mark.parametrize("name, phase, expected", CASES, ids=[c[0][:3] for c in CASES])
def test_sample_produces_documented_verdicts(client, name, phase, expected):
    with (SAMPLES / name).open("rb") as handle:
        response = client.post(
            "/check",
            files={"submission": (name, handle, "application/zip")},
            data={"phase": phase},
        )
    assert response.status_code == 200
    rendered = verdicts(response.text)
    for rule_id, severity in expected.items():
        # A rule can emit several findings; the worst one is what counts.
        worst = max(rendered[rule_id], key=["pass", "warn", "fail"].index)
        assert worst == severity, f"{name}: {rule_id} was {worst}, expected {severity}"
    assert MESSAGES[name] in response.text


def test_compliant_phase1_sample_is_ready_to_submit(client):
    with (SAMPLES / "M01-phase1-compliant.zip").open("rb") as handle:
        response = client.post(
            "/check", files={"submission": ("M01.zip", handle, "application/zip")}, data={"phase": "1"}
        )
    assert HEADLINE["pass"] in response.text


def test_near_miss_sample_names_the_misspelt_folder(client):
    with (SAMPLES / "M03-phase1-near-miss-folder.zip").open("rb") as handle:
        response = client.post(
            "/check", files={"submission": ("M03.zip", handle, "application/zip")}, data={"phase": "1"}
        )
    assert "02_requirements" in response.text


def test_traversal_sample_is_rejected_before_extraction(client):
    with (SAMPLES / "M08-unsafe-path-traversal.zip").open("rb") as handle:
        response = client.post(
            "/check", files={"submission": ("M08.zip", handle, "application/zip")}, data={"phase": ""}
        )
    assert response.status_code == 400
    assert "Unsafe path in archive" in response.text


def test_non_zip_sample_is_rejected(client):
    with (SAMPLES / "M09-not-a-zip.zip").open("rb") as handle:
        response = client.post(
            "/check", files={"submission": ("M09.zip", handle, "application/zip")}, data={"phase": ""}
        )
    assert response.status_code == 400
    assert "not a valid ZIP archive" in response.text


def test_sample_pdfs_are_structurally_valid():
    """Every xref offset in the generated PDFs points at the object it names."""
    import zipfile

    with zipfile.ZipFile(SAMPLES / "M01-phase1-compliant.zip") as zf:
        pdfs = [zf.read(n) for n in zf.namelist() if n.endswith(".pdf")]
    assert pdfs
    for data in pdfs:
        xref = int(data.rsplit(b"startxref\n", 1)[1].split(b"\n", 1)[0])
        entries = data[xref:].split(b"\n")[3:]
        offsets = [int(e[:10]) for e in entries if e.endswith(b" n ")]
        for number, offset in enumerate(offsets, start=1):
            assert data[offset:].startswith(b"%d 0 obj" % number)
