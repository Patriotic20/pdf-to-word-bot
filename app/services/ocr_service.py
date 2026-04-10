from __future__ import annotations

from pathlib import Path

import fitz
import pytesseract
from PIL import Image

OCR_DPI = 200


def _page_to_image(page: fitz.Page, dpi: int = OCR_DPI) -> Image.Image:
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    return Image.frombytes('RGB', [pix.width, pix.height], pix.samples)


def extract_text_from_image(image: Image.Image, lang: str = 'eng') -> str:
    """Extract text from a PIL image using Tesseract OCR."""
    return pytesseract.image_to_string(image, lang=lang).strip()


def is_text_pdf(pdf_path: str | Path, sample_pages: int = 3) -> bool:
    """Return True when the PDF contains readable text, not just scanned images."""
    path = Path(pdf_path)
    with fitz.open(str(path)) as document:
        for page_number, page in enumerate(document, start=1):
            if page_number > sample_pages:
                break
            if page.get_text().strip():
                return True
    return False


def extract_text_from_pdf(
    pdf_path: str | Path,
    lang: str = 'eng',
    dpi: int = OCR_DPI,
) -> str:
    """Extract searchable text from a PDF, falling back to OCR for scanned pages."""
    path = Path(pdf_path)
    result: list[str] = []

    with fitz.open(str(path)) as document:
        for page in document:
            page_text = page.get_text().strip()
            if page_text:
                result.append(page_text)
                continue

            image = _page_to_image(page, dpi=dpi)
            ocr_text = extract_text_from_image(image, lang=lang)
            if ocr_text:
                result.append(ocr_text)

    return '\n\n'.join(result)
