"""Extract text from uploaded PDF resumes with PyMuPDF.

Scope: text-based PDFs only. Scanned / image-only PDFs have no text layer and
are rejected with a clear message; OCR is not implemented.

Every problem raises ``PDFExtractionError``, which carries a machine-readable
``code`` and a suggested HTTP ``status_code`` so the API layer can turn it into
a consistent JSON error.
"""

from __future__ import annotations

import os
from typing import Tuple

import pymupdf
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

ALLOWED_EXTENSION = ".pdf"
PDF_MAGIC = b"%PDF-"
MAX_PAGES = 50           # a resume is a few pages; protects against huge documents
MAX_FILENAME_CHARS = 255  # length of the database column
DEFAULT_MAX_BYTES = 5 * 1024 * 1024


class PDFExtractionError(Exception):
    """A PDF could not be accepted or read."""

    def __init__(self, message: str, code: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def _clean_text(pages) -> str:
    """Join page texts and tidy them (no NUL characters, no trailing spaces)."""
    text = "\n".join(page.replace("\x00", "") for page in pages)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def extract_text_from_pdf(data: bytes) -> str:
    """Return the text of all pages of a PDF given as bytes.

    Raises ``PDFExtractionError`` with one of these codes:
      invalid_pdf         empty file, not a PDF, or corrupt
      encrypted_pdf       password-protected
      too_many_pages      more than ``MAX_PAGES`` pages
      no_extractable_text no text layer (for example a scan)
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError(f"data must be bytes, got {type(data).__name__}")
    if not data:
        raise PDFExtractionError("The uploaded file is empty.", "invalid_pdf", 400)
    if PDF_MAGIC not in bytes(data[:1024]):
        raise PDFExtractionError(
            "The file is not a valid PDF (it does not start with a PDF header).", "invalid_pdf", 400
        )

    try:
        document = pymupdf.open(stream=bytes(data), filetype="pdf")
    except Exception as exc:  # PyMuPDF raises several error types for broken files
        raise PDFExtractionError(
            "The PDF could not be opened; the file may be corrupt.", "invalid_pdf", 400
        ) from exc

    with document:
        if document.needs_pass:
            raise PDFExtractionError(
                "The PDF is password-protected. Remove the password and upload it again.",
                "encrypted_pdf",
                422,
            )
        if document.page_count > MAX_PAGES:
            raise PDFExtractionError(
                f"The PDF has {document.page_count} pages; the maximum is {MAX_PAGES}.",
                "too_many_pages",
                422,
            )
        try:
            pages = [page.get_text("text") for page in document]
        except Exception as exc:
            raise PDFExtractionError(
                "The PDF could not be read; the file may be corrupt.", "invalid_pdf", 400
            ) from exc

    text = _clean_text(pages)
    if not text:
        raise PDFExtractionError(
            "No extractable text was found in the PDF. It may be a scanned or image-only "
            "document; OCR is not supported. Upload a text-based PDF or paste the resume text.",
            "no_extractable_text",
            422,
        )
    return text


def extract_text_from_upload(
    upload: FileStorage, max_bytes: int = DEFAULT_MAX_BYTES
) -> Tuple[str, str]:
    """Validate an uploaded file and extract its text.

    Returns ``(safe_filename, text)``. Raises ``PDFExtractionError`` with the
    codes above plus:
      unsupported_file_type  the filename does not end in .pdf  (HTTP 415)
      file_too_large         larger than ``max_bytes``           (HTTP 413)
    """
    original_name = upload.filename or ""
    extension = os.path.splitext(original_name)[1].lower()
    if extension != ALLOWED_EXTENSION:
        shown = extension or "no extension"
        raise PDFExtractionError(
            f"Unsupported file type ({shown}). Only PDF files are accepted.",
            "unsupported_file_type",
            415,
        )

    data = upload.stream.read(max_bytes + 1)  # one extra byte reveals an oversized file
    if len(data) > max_bytes:
        raise PDFExtractionError(
            f"The file is larger than the {max_bytes / (1024 * 1024):g} MB limit.",
            "file_too_large",
            413,
        )

    text = extract_text_from_pdf(data)
    safe_name = secure_filename(original_name) or "resume.pdf"
    return safe_name[:MAX_FILENAME_CHARS], text
