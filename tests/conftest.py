"""Shared test fixtures.

Submissions are built from a plain ``{relative path: content}`` mapping so that
each test reads as a description of the folder it exercises.

No test touches the network: the repository comparison (R07) is always wired
to an in-memory FakeRepository by the autouse fixture below.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app.extraction import extract
from app.models import Submission
from app.repository import Inventory, blob_hash
from app.rules import all_rules

MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

MAIN = "Mustermann-Max_12345678_PSE"
CODE_ARCHIVE = f"{MAIN}/04-Implementation/{MAIN}_Submission_Code.zip"
OWNER, REPO = "maxmustermann", "pse_myproject"

# The student's project as it exists both in the repository and in the code
# archive. Tests that need the two to differ change one side only.
PROJECT_FILES = {
    "README.md": b"# Room booking\n\nRun with: docker compose up\n",
    "app/main.py": b"from fastapi import FastAPI\n\napp = FastAPI()\n",
    "tests/test_main.py": b"def test_placeholder():\n    assert True\n",
}


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for relpath, content in files.items():
            zf.writestr(relpath, content)
    return buffer.getvalue()


# A submission that satisfies every rule; individual tests break one thing at
# a time by overriding entries in this mapping.
VALID_PHASE_3 = {
    f"{MAIN}/01-Project-management/profile.pdf": MINIMAL_PDF,
    f"{MAIN}/02-Requirements/requirements.pdf": MINIMAL_PDF,
    f"{MAIN}/03-Architecture-documentation/architecture.pdf": MINIMAL_PDF,
    CODE_ARCHIVE: zip_bytes(PROJECT_FILES),
    f"{MAIN}/links.txt": (
        f"Repository: https://github.com/{OWNER}/{REPO}\n"
        "Application: https://pse-myproject.onrender.com\n"
    ).encode(),
}


class FakeRepository:
    """In-memory IRepositoryInventory with a scriptable outcome."""

    def __init__(self, files: dict[str, bytes]) -> None:
        self.files = dict(files)
        self.error: Exception | None = None
        self.truncated = False
        self.requests: list[tuple[str, str]] = []

    def inventory(self, owner: str, repo: str) -> Inventory:
        self.requests.append((owner, repo))
        if self.error is not None:
            raise self.error
        blobs = {path: blob_hash(content) for path, content in self.files.items()}
        return Inventory(owner, repo, "main", blobs, self.truncated)


@pytest.fixture(autouse=True)
def fake_repository(monkeypatch) -> FakeRepository:
    fake = FakeRepository(PROJECT_FILES)
    rule = next(r for r in all_rules() if r.id == "R07")
    monkeypatch.setattr(rule, "client", fake)
    return fake


def build_submission(tmp_path: Path, files: dict[str, bytes], phase: int | None = 3) -> Submission:
    """Zip ``files``, extract it through the real pipeline, return a Submission."""
    archive = tmp_path / "upload.zip"
    archive.write_bytes(zip_bytes(files))
    return extract(
        archive,
        tmp_path / "extracted",
        original_filename=f"{MAIN}.zip",
        phase=phase,
    )


@pytest.fixture
def make_submission(tmp_path):
    counter = {"n": 0}

    def factory(files: dict[str, bytes], phase: int | None = 3) -> Submission:
        counter["n"] += 1
        workdir = tmp_path / f"case{counter['n']}"
        workdir.mkdir()
        return build_submission(workdir, files, phase)

    return factory


@pytest.fixture
def valid_submission(make_submission) -> Submission:
    return make_submission(dict(VALID_PHASE_3))
