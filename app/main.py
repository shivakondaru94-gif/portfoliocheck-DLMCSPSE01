"""Component: WebInterface -- HTTP layer of PortfolioCheck.

Accepts an upload, hands it to ArchiveExtractor and CheckService, and renders
the report. Also publishes the rule catalogue (FR13) and the folder skeleton
(FR10). Uses ICheckService, IRuleCatalogue, IExtraction and the domain model;
never an individual rule.
"""

from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import checker
from .extraction import UnsafeArchive, extract
from .models import REQUIRED_SUBDIRECTORIES
from .rules import all_rules

BASE_DIR = Path(__file__).parent
MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # refuse anything larger before touching disk
CHUNK = 1024 * 1024

app = FastAPI(title="PortfolioCheck", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "index.html", {"rules": all_rules()}
    )


@app.post("/check", response_class=HTMLResponse)
async def check(
    request: Request,
    submission: UploadFile = File(...),
    phase: str = Form(""),
) -> HTMLResponse:
    if not submission.filename or not submission.filename.lower().endswith(".zip"):
        return _error(request, "Please upload the zip folder of your submission (.zip).")

    workdir = Path(tempfile.mkdtemp(prefix="portfoliocheck-"))
    try:
        archive_path = workdir / "upload.zip"
        written = await _save(submission, archive_path)
        if written > MAX_UPLOAD_BYTES:
            return _error(
                request,
                f"The upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.",
            )

        # Extraction and rule evaluation do blocking file and network I/O, so
        # they run in a worker thread instead of stalling the event loop and
        # every other request with it.
        try:
            parsed = await run_in_threadpool(
                extract,
                archive_path,
                workdir / "extracted",
                original_filename=submission.filename,
                phase=int(phase) if phase in {"1", "2", "3"} else None,
            )
        except zipfile.BadZipFile:
            return _error(request, "That file is not a valid ZIP archive.")
        except UnsafeArchive as exc:
            return _error(request, f"The archive was rejected: {exc}")

        report = await run_in_threadpool(checker.run, parsed)
        return templates.TemplateResponse(request, "report.html", {"report": report})
    finally:
        # The extracted submission is never persisted; nothing a student
        # uploads survives the request.
        shutil.rmtree(workdir, ignore_errors=True)


@app.get("/skeleton")
def skeleton(name: str = "Surname-FirstName_MatrNo_Course") -> StreamingResponse:
    """Download an empty, correctly structured zip folder to fill in."""
    safe = "".join(c for c in name if c.isalnum() or c in "-_") or "Submission"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder, contents in REQUIRED_SUBDIRECTORIES.items():
            archive.writestr(
                f"{safe}/{folder}/README.txt",
                f"Place here: {contents}.\nDelete this file once the folder is filled.\n",
            )
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe}.zip"'},
    )


@app.get("/rules")
def rules() -> list[dict]:
    """The active rule catalogue (FR13), readable before anything is uploaded."""
    return [
        {
            "id": rule.id,
            "title": rule.title,
            "phases": list(rule.phases),
            "reference": rule.reference,
        }
        for rule in all_rules()
    ]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "rules": str(len(all_rules()))}


async def _save(upload: UploadFile, destination: Path) -> int:
    """Stream the upload to disk, stopping once the limit is exceeded."""
    written = 0
    with destination.open("wb") as handle:
        while chunk := await upload.read(CHUNK):
            written += len(chunk)
            if written > MAX_UPLOAD_BYTES:
                return written
            handle.write(chunk)
    return written


def _error(request: Request, message: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {"error": message, "rules": all_rules()},
        status_code=400,
    )
