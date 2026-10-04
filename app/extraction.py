"""Component: ArchiveExtractor -- provides IExtraction.

Defensive ZIP extraction.

Accepting arbitrary archives from the internet is the one genuinely hostile
part of this application, so extraction is guarded against the three classic
attacks: path traversal (``../../etc/passwd``), absolute paths, and
decompression bombs (a few KB that expand to gigabytes).
"""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath

from .models import Submission, SubmissionFile

# Limits are generous for a coursework portfolio but far below anything that
# could exhaust the container. See docs/architecture.md for the rationale.
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MB expanded
MAX_ENTRIES = 5_000
MAX_COMPRESSION_RATIO = 200  # single-entry blow-up factor


class UnsafeArchive(Exception):
    """Raised when an archive violates an extraction safety limit."""


def _is_safe_member(name: str) -> bool:
    """Reject absolute paths, drive letters and any traversal outside root."""
    if name.startswith(("/", "\\")) or ":" in name.split("/")[0]:
        return False
    return ".." not in PurePosixPath(name).parts


def inspect(archive: zipfile.ZipFile) -> None:
    """Validate an archive against the safety limits without extracting it."""
    infos = archive.infolist()
    if len(infos) > MAX_ENTRIES:
        raise UnsafeArchive(f"Archive contains {len(infos)} entries (limit {MAX_ENTRIES}).")

    total = 0
    for info in infos:
        if not _is_safe_member(info.filename):
            raise UnsafeArchive(f"Unsafe path in archive: {info.filename!r}")
        total += info.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            raise UnsafeArchive(
                f"Archive expands beyond {MAX_UNCOMPRESSED_BYTES // (1024 * 1024)} MB."
            )
        # A tiny compressed entry that explodes is the signature of a zip bomb.
        if info.compress_size > 0 and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise UnsafeArchive(f"Suspicious compression ratio for {info.filename!r}.")


def extract(zip_path: Path, dest: Path, original_filename: str, phase: int | None = None) -> Submission:
    """Safely extract ``zip_path`` into ``dest`` and describe the result.

    Raises:
        UnsafeArchive: if the archive trips a safety limit.
        zipfile.BadZipFile: if the upload is not a valid ZIP.
    """
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        inspect(archive)
        archive.extractall(dest)

    submission = Submission(
        original_filename=original_filename,
        root=dest,
        phase=phase,
    )
    submission.files = _walk(dest)
    return submission


def _walk(root: Path) -> list[SubmissionFile]:
    """Collect every regular file below ``root`` as a SubmissionFile."""
    files: list[SubmissionFile] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relpath = path.relative_to(root).as_posix()
        files.append(SubmissionFile(relpath=relpath, size=path.stat().st_size, absolute=path))
    return files
