"""Generate the sample submissions used by the manual test cases.

Run from the repository root:

    python samples/build_samples.py

Each archive models a realistic portfolio submission for a fictional student
project (a study-room booking system), using the example name from the
assignment brief itself. Every archive differs from the compliant one in
exactly one respect, so each manual test case exercises exactly one rule.
The output is deterministic: running the script twice produces identical files.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

HERE = Path(__file__).parent
MAIN = "Mustermann-Max_12345678_PSE"
# Fixed timestamp so regenerated archives are byte-identical.
STAMP = (2026, 9, 1, 12, 0, 0)


def pdf(title: str, *lines: str) -> bytes:
    """A minimal but valid single-page PDF containing the given text."""
    text_ops = ["BT", "/F1 16 Tf", "72 760 Td", f"({_escape(title)}) Tj", "/F1 11 Tf"]
    for line in lines:
        text_ops += ["0 -20 Td", f"({_escape(line)}) Tj"]
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, xref)
    )
    return out.getvalue()


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            info = zipfile.ZipInfo(name, date_time=STAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, content)
    return buffer.getvalue()


# -- the fictional student's documents ---------------------------------------

PROFILE = pdf(
    "Project profile: RoomSpot",
    "RoomSpot lets students book quiet study rooms in the campus library.",
    "Target group: full-time and part-time students of the Hamburg campus.",
    "Methodology: Kanban with two-week reviews.",
)
REQUIREMENTS = pdf(
    "Requirements and glossary: RoomSpot",
    "FR1 A student can see which rooms are free for a chosen time slot.",
    "FR2 A student can book a free room for up to three hours.",
    "NFR1 A booking is confirmed within two seconds.",
)
ARCHITECTURE = pdf(
    "Architecture documentation: RoomSpot",
    "Context view, component view and deployment view.",
    "Components: BookingApi, RoomCatalogue, Notification.",
)
CODE = zip_bytes({
    "README.md": b"# RoomSpot\n\nStudy-room booking for the campus library.\n\n"
                 b"Run locally with: docker compose up\n",
    "app/main.py": b"from fastapi import FastAPI\n\napp = FastAPI(title='RoomSpot')\n",
    "app/booking.py": b"MAX_HOURS = 3\n\n\ndef can_book(hours: int) -> bool:\n"
                      b"    return 0 < hours <= MAX_HOURS\n",
    "tests/test_booking.py": b"from app.booking import can_book\n\n\n"
                             b"def test_three_hours_is_allowed():\n    assert can_book(3)\n",
})
LINKS = (
    b"Repository: https://github.com/maxmustermann/pse_myproject\n"
    b"Application: https://roomspot.onrender.com\n"
    b"Login: not required\n"
)


def phase1(main: str = MAIN, **overrides: bytes) -> dict[str, bytes]:
    files = {
        f"{main}/01-Project-management/{MAIN}_P1_S.pdf": PROFILE,
        f"{main}/02-Requirements/requirements.pdf": REQUIREMENTS,
        f"{main}/03-Architecture-documentation/architecture.pdf": ARCHITECTURE,
        f"{main}/04-Implementation/README.txt": b"Implementation starts in phase 2.\n",
    }
    files.update(overrides)
    return files


def phase3(**overrides: bytes) -> dict[str, bytes]:
    files = phase1()
    del files[f"{MAIN}/04-Implementation/README.txt"]
    files[f"{MAIN}/04-Implementation/{MAIN}_Submission_Code.zip"] = CODE
    files[f"{MAIN}/links.txt"] = LINKS
    files.update(overrides)
    return files


SAMPLES: dict[str, bytes] = {
    "M01-phase1-compliant.zip": zip_bytes(phase1()),
    "M02-phase1-main-directory-underscore.zip": zip_bytes(
        {k.replace(MAIN, "Mustermann_Max_12345678_PSE", 1): v for k, v in phase1().items()}
    ),
    "M03-phase1-near-miss-folder.zip": zip_bytes(
        {k.replace("/02-Requirements/", "/02_requirements/"): v for k, v in phase1().items()}
    ),
    "M04-phase1-short-matriculation.zip": zip_bytes(
        {k.replace("12345678", "123456", 1): v for k, v in phase1().items()}
    ),
    "M05-phase2-renamed-docx.zip": zip_bytes(phase1(**{
        # A Word document (a ZIP container) saved with a .pdf extension.
        f"{MAIN}/03-Architecture-documentation/architecture.pdf":
            zip_bytes({"word/document.xml": b"<w:document>Architecture</w:document>"}),
    })),
    "M06-phase3-wrong-code-archive-name.zip": zip_bytes({
        (k.replace(f"{MAIN}_Submission_Code.zip", "code.zip")): v for k, v in phase3().items()
    }),
    "M07-phase3-missing-application-link.zip": zip_bytes(phase3(**{
        f"{MAIN}/links.txt": b"Repository: https://github.com/maxmustermann/pse_myproject\n",
    })),
}


def unsafe_traversal() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(zipfile.ZipInfo(f"{MAIN}/01-Project-management/profile.pdf", STAMP), PROFILE)
        zf.writestr(zipfile.ZipInfo("../outside-the-upload-folder.txt", STAMP), b"escaped\n")
    return buffer.getvalue()


SAMPLES["M08-unsafe-path-traversal.zip"] = unsafe_traversal()
SAMPLES["M09-not-a-zip.zip"] = b"This is a plain text file that was renamed to .zip.\n"


def main() -> None:
    for name, content in SAMPLES.items():
        (HERE / name).write_bytes(content)
        print(f"{name:45} {len(content):>7} bytes")


if __name__ == "__main__":
    main()
