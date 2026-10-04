"""Rules covering file formats and size limits."""

from __future__ import annotations

from ..models import Finding, Submission, SubmissionFile
from .base import Rule, register

PDF_MAGIC = b"%PDF-"
MAX_PHASE_FILE_BYTES = 15 * 1024 * 1024  # Chapters 4.2: max. 15 MB per phase file


@register
class PdfIntegrityRule(Rule):
    id = "R05"
    title = "PDF files are real PDFs"
    reference = "Chapter 4.2: permitted file formats -- PDF"

    def check(self, submission: Submission) -> list[Finding]:
        pdfs = [f for f in submission.files if f.suffix == ".pdf"]
        if not pdfs:
            return [
                self.warn(
                    "The submission contains no PDF files at all.",
                    "Every phase deliverable (concept, presentation, abstract) must be "
                    "submitted as PDF.",
                )
            ]

        broken = [f for f in pdfs if not self._is_pdf(f)]
        if broken:
            return [
                self.fail(
                    f"{f.relpath!r} has a .pdf extension but is not a PDF file.",
                    "Export the document to PDF properly instead of renaming it; a "
                    "renamed .docx cannot be opened by the examiner and therefore "
                    "cannot be assessed.",
                )
                for f in broken
            ]

        return [self.ok(f"All {len(pdfs)} PDF file(s) are valid PDFs.")]

    @staticmethod
    def _is_pdf(file: SubmissionFile) -> bool:
        with file.absolute.open("rb") as handle:
            return handle.read(len(PDF_MAGIC)) == PDF_MAGIC


@register
class FileSizeRule(Rule):
    id = "R06"
    title = "File size limits"
    reference = "Chapter 4.2: file size max. 15 MB (conception and development phase)"

    def check(self, submission: Submission) -> list[Finding]:
        oversized = [f for f in submission.files if f.size > MAX_PHASE_FILE_BYTES]
        if oversized:
            return [
                self.fail(
                    f"{f.relpath!r} is {self._mb(f.size)}, above the 15 MB limit for a "
                    "phase submission.",
                    "Compress embedded images or export the PDF at a lower resolution. "
                    "Keep images embedded -- do not drop them to save size.",
                )
                for f in oversized
            ]

        largest = max(submission.files, key=lambda f: f.size, default=None)
        if largest is None:
            return [
                self.fail(
                    "The archive contains no files.",
                    "Zip the main directory including all its subdirectories.",
                )
            ]
        return [
            self.ok(
                f"All files are within the 15 MB limit "
                f"(largest: {largest.name}, {self._mb(largest.size)})."
            )
        ]

    @staticmethod
    def _mb(size: int) -> str:
        return f"{size / (1024 * 1024):.1f} MB"
