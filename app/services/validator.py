from __future__ import annotations

from pathlib import Path

ALLOWED_EXTENSIONS = {'.pdf'}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024


class ValidationError(ValueError):
    """Raised when an uploaded or saved PDF fails validation."""


def is_pdf_file(file_name: str) -> bool:
    """Return True when the file name has a PDF extension."""
    return Path(file_name).suffix.lower() in ALLOWED_EXTENSIONS


def validate_pdf_file(file_path: str | Path) -> None:
    """Validate that the file exists, is a PDF, and is within allowed size limits."""
    pdf_path = Path(file_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if not pdf_path.is_file():
        raise ValidationError(f"PDF path must be a file: {pdf_path}")

    if pdf_path.suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type: {pdf_path.suffix}. Only PDF files are supported."
        )

    size = pdf_path.stat().st_size
    if size == 0:
        raise ValidationError("PDF file is empty.")

    if size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"PDF file is too large ({size} bytes). Maximum allowed size is "
            f"{MAX_FILE_SIZE_BYTES} bytes."
        )


def validate_pdf_upload(file_name: str, file_size: int) -> None:
    """Validate a PDF upload before saving it to disk."""
    if not is_pdf_file(file_name):
        raise ValidationError("Only PDF files are supported.")

    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"PDF upload is too large ({file_size} bytes). Maximum allowed size is "
            f"{MAX_FILE_SIZE_BYTES} bytes."
        )
