from __future__ import annotations

from pathlib import Path

from docx import Document
from pdf2docx import Converter as Pdf2DocxConverter

from app.services.ocr_service import extract_text_from_pdf, is_text_pdf
from app.services.validator import validate_pdf_file


class ConversionError(RuntimeError):
    """Raised when a PDF-to-DOCX conversion fails."""


def _docx_contains_text(docx_path: Path) -> bool:
    document = Document(docx_path)
    return any(paragraph.text.strip() for paragraph in document.paragraphs)


def _convert_pdf2docx(pdf_path: Path, output_path: Path) -> None:
    with Pdf2DocxConverter(str(pdf_path)) as converter:
        converter.convert(str(output_path), start=0, end=None)


def _create_docx_from_ocr(pdf_path: Path, output_path: Path, lang: str) -> None:
    extracted_text = extract_text_from_pdf(pdf_path, lang=lang)
    if not extracted_text.strip():
        raise ConversionError("OCR extraction produced no text.")

    document = Document()
    for paragraph in extracted_text.split('\n\n'):
        paragraph = paragraph.strip()
        if paragraph:
            document.add_paragraph(paragraph)

    document.save(str(output_path))


def convert_pdf_to_word(
    pdf_path: str | Path,
    output_path: str | Path | None = None,
    *,
    ocr_fallback: bool = True,
    ocr_lang: str = 'eng',
) -> Path:
    """Convert a PDF to a DOCX file.

    If the PDF contains only scanned pages, the function falls back to OCR.
    """
    source_path = Path(pdf_path)
    validate_pdf_file(source_path)

    if output_path is None:
        output_path = source_path.with_suffix('.docx')

    target_path = Path(output_path)
    if target_path.suffix.lower() != '.docx':
        target_path = target_path.with_suffix('.docx')

    target_path.parent.mkdir(parents=True, exist_ok=True)

    if ocr_fallback and not is_text_pdf(source_path):
        _create_docx_from_ocr(source_path, target_path, ocr_lang)
        return target_path

    try:
        _convert_pdf2docx(source_path, target_path)
        if not _docx_contains_text(target_path):
            raise ConversionError('Converted document contains no text.')
    except Exception:
        if not ocr_fallback:
            raise
        _create_docx_from_ocr(source_path, target_path, ocr_lang)

    return target_path
