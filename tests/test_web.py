"""End-to-end tests through the HTTP layer."""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.main import app

from .conftest import VALID_PHASE_3


@pytest.fixture
def client():
    return TestClient(app)


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for relpath, content in files.items():
            zf.writestr(relpath, content)
    return buffer.getvalue()


def test_landing_page_lists_the_rules(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "R01" in response.text


def test_valid_submission_reports_ready(client):
    response = client.post(
        "/check",
        files={"submission": ("sub.zip", zip_bytes(VALID_PHASE_3), "application/zip")},
        data={"phase": "3"},
    )
    assert response.status_code == 200
    assert "Ready to submit" in response.text


def test_broken_submission_reports_failures(client):
    response = client.post(
        "/check",
        files={"submission": ("sub.zip", zip_bytes({"notes.txt": b"nothing here"}), "application/zip")},
        data={"phase": "3"},
    )
    assert response.status_code == 200
    assert "Not ready to submit" in response.text


def test_non_zip_upload_is_rejected(client):
    response = client.post(
        "/check",
        files={"submission": ("report.pdf", b"%PDF-1.4", "application/pdf")},
        data={"phase": "3"},
    )
    assert response.status_code == 400
    assert "zip folder" in response.text


def test_corrupt_zip_is_rejected(client):
    response = client.post(
        "/check",
        files={"submission": ("sub.zip", b"not really a zip", "application/zip")},
        data={"phase": ""},
    )
    assert response.status_code == 400
    assert "not a valid ZIP" in response.text


def test_skeleton_download_has_the_required_folders(client):
    response = client.get("/skeleton", params={"name": "Mustermann-Max_12345678_PSE"})
    assert response.status_code == 200

    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
        names = zf.namelist()
    assert any("01-Project-management" in n for n in names)
    assert any("04-Implementation" in n for n in names)


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_rule_catalogue_lists_every_rule_with_its_source(client):
    rules = client.get("/rules").json()
    assert [r["id"] for r in rules] == ["R01", "R02", "R03", "R04", "R05", "R06", "R07"]
    assert all(r["reference"] for r in rules)
    assert next(r for r in rules if r["id"] == "R07")["phases"] == [3]


def test_report_shows_source_provision(client):
    response = client.post(
        "/check",
        files={"submission": ("sub.zip", zip_bytes(VALID_PHASE_3), "application/zip")},
        data={"phase": "3"},
    )
    assert "Source: Chapter 4.2" in response.text


def test_unknown_phase_value_checks_all_rules(client):
    response = client.post(
        "/check",
        files={"submission": ("sub.zip", zip_bytes(VALID_PHASE_3), "application/zip")},
        data={"phase": "7"},
    )
    assert response.status_code == 200
    assert "R07" in response.text
