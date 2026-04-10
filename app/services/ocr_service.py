from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import fitz
import pytesseract
from PIL import Image
from loguru import logger

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


def extract_page_elements(
    page: fitz.Page,
    ocr_lang: str = 'eng',
    dpi: int = OCR_DPI,
) -> list[tuple[float, str, Any]]:
    """Extract styled text and images from a PDF page, sorted by Y-coordinate."""
    elements: list[tuple[float, str, Any]] = []

    blocks = page.get_text("dict").get("blocks", [])
    page_width = page.rect.width

    for block in blocks:
        bbox = block.get("bbox", (0, 0, 0, 0))
        y0 = bbox[1]

        if block.get("type") == 0:  # Text block
            spans_data = []
            lines = block.get("lines", [])
            for line_idx, line in enumerate(lines):
                line_spans = line.get("spans", [])
                for span in line_spans:
                    span_text = span.get("text", "")
                    if not span_text:
                        continue

                    color = span.get("color", 0)
                    flags = span.get("flags", 0)

                    spans_data.append({
                        "text": span_text.replace("\n", " "),
                        "font": span.get("font", "Arial"),
                        "size": span.get("size", 11.0),
                        "bold": bool(flags & 16),
                        "italic": bool(flags & 2),
                        "color_r": (color >> 16) & 0xFF,
                        "color_g": (color >> 8) & 0xFF,
                        "color_b": color & 0xFF,
                        "flags": flags,
                    })

                # Insert a space between lines if needed to prevent merging words
                if spans_data and line_idx < len(lines) - 1:
                    last_text = spans_data[-1]["text"]
                    if last_text and not last_text.endswith(" ") and not last_text.endswith("-"):
                        space_span = spans_data[-1].copy()
                        space_span["text"] = " "
                        spans_data.append(space_span)

            if any(sd["text"].strip() for sd in spans_data):
                elements.append((y0, "text", spans_data))

        elif block.get("type") == 1:  # Image block
            image_bytes = block.get("image")
            if image_bytes:
                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    if img.mode not in ("RGB", "RGBA"):
                        img = img.convert("RGB")

                    # Skip broken or too small image segments
                    if img.width < 10 or img.height < 10:
                        logger.warning(f"Skipping too small image on page {page.number} ({img.width}x{img.height})")
                        continue

                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    img_width_pt = bbox[2] - bbox[0]

                    elements.append((y0, "image", {
                        "bytes": buf.getvalue(),
                        "width_pt": img_width_pt,
                        "page_width_pt": page_width
                    }))
                except Exception as e:
                    logger.warning(f"Failed to process image on page {page.number}: {e}")

    # Fallback to OCR if page has no extracted content
    if not elements:
        logger.info(f"Page {page.number} is empty, applying OCR.")
        img = _page_to_image(page, dpi=dpi)
        ocr_text = extract_text_from_image(img, lang=ocr_lang)
        if ocr_text:
            text_blocks = ocr_text.split('\n\n')
            for i, tb in enumerate(text_blocks):
                tb = tb.replace('\n', ' ').strip()
                tb = " ".join(tb.split())
                if tb:
                    elements.append((float(i), "text", [{
                        "text": tb,
                        "font": "Arial",
                        "size": 11.0,
                        "bold": False,
                        "italic": False,
                        "color_r": 0,
                        "color_g": 0,
                        "color_b": 0,
                        "flags": 0,
                    }]))

    elements.sort(key=lambda x: x[0])
    return elements


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
