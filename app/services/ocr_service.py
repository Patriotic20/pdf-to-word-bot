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
    """
    Render a PDF page out to an Image.Image object for OCR evaluation.
    
    Args:
        page: The PyMuPDF (fitz) page object.
        dpi: Target DPI for the rendered image. Defaults to OCR_DPI (200).
        
    Returns:
        Image.Image: The rendered PDF page as a PIL Image.
    """
    matrix: fitz.Matrix = fitz.Matrix(dpi / 72, dpi / 72)
    pix: fitz.Pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    return Image.frombytes('RGB', [pix.width, pix.height], pix.samples)


def extract_text_from_image(image: Image.Image, lang: str = 'eng') -> str:
    """
    Extract text strings from a PIL image using Tesseract OCR.
    
    Args:
        image: The PIL Image.Image to parse.
        lang: Tesseract language string (e.g., 'eng', 'rus').
        
    Returns:
        str: Discovered strings, or empty if none.
    """
    return pytesseract.image_to_string(image, lang=lang).strip()


def is_text_pdf(pdf_path: str | Path, sample_pages: int = 3) -> bool:
    """
    Validate whether the PDF contains embedded text (true PDF) rather than just scanned images.
    Checks up to `sample_pages` to maximize performance.
    
    Args:
        pdf_path: The filesystem path to the target PDF.
        sample_pages: The number of initial pages to scan. Defaults to 3.
        
    Returns:
        bool: True if text was discovered, False if it appears completely scanned.
    """
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
    """
    Extract styled text spans and image bounding boxes from a given PyMuPDF (fitz) page.
    Results are ordered by vertical Y-coordinate to preserve structural flow.
    
    Args:
        page: The target PyMuPDF page.
        ocr_lang: Fallback OCR language string.
        dpi: Internal processing DPI metric.
        
    Returns:
        A list of tuples formatting (y_coordinate, element_type, payload).
        element_type is either "text" or "image".
        For text, the payload is a List of parsed span dicts including fonts and sizes.
        For image, the payload provides image_bytes alongside scaling context.
    """
    elements: list[tuple[float, str, Any]] = []

    blocks: list[dict[str, Any]] = page.get_text("dict").get("blocks", [])
    page_width: float = page.rect.width

    for block in blocks:
        bbox = block.get("bbox", (0, 0, 0, 0))
        y0: float = float(bbox[1])

        if block.get("type") == 0:  # Text block
            spans_data: list[dict[str, Any]] = []
            lines = block.get("lines", [])
            for line_idx, line in enumerate(lines):
                line_spans = line.get("spans", [])
                for span in line_spans:
                    span_text: str = span.get("text", "")
                    if not span_text:
                        continue

                    color: int = span.get("color", 0)
                    flags: int = span.get("flags", 0)

                    spans_data.append({
                        "text": span_text.replace("\n", " "),
                        "font": span.get("font", "Arial"),
                        "size": float(span.get("size", 11.0)),
                        "bold": bool(flags & 16),
                        "italic": bool(flags & 2),
                        "color_r": (color >> 16) & 0xFF,
                        "color_g": (color >> 8) & 0xFF,
                        "color_b": color & 0xFF,
                        "flags": flags,
                    })

                # Insert a space between lines if needed to prevent merging words
                if spans_data and line_idx < len(lines) - 1:
                    last_text = str(spans_data[-1]["text"])
                    if last_text and not last_text.endswith(" ") and not last_text.endswith("-"):
                        space_span = spans_data[-1].copy()
                        space_span["text"] = " "
                        spans_data.append(space_span)

            if any(str(sd["text"]).strip() for sd in spans_data):
                elements.append((y0, "text", spans_data))

        elif block.get("type") == 1:  # Image block
            image_bytes: bytes | None = block.get("image")
            if image_bytes:
                try:
                    img = Image.open(io.BytesIO(image_bytes))
                    if img.mode not in ("RGB", "RGBA"):
                        img = img.convert("RGB")

                    # Skip broken or explicitly diminutive image segments
                    if img.width < 10 or img.height < 10:
                        logger.warning(f"Skipping insignificantly small image on page {page.number} ({img.width}x{img.height})")
                        continue

                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    img_width_pt: float = float(bbox[2]) - float(bbox[0])

                    elements.append((y0, "image", {
                        "bytes": buf.getvalue(),
                        "width_pt": img_width_pt,
                        "page_width_pt": page_width
                    }))
                except Exception as e:
                    logger.warning(f"Failed parsing discrete image block on page {page.number}: {e}")

    # Fallback entirely to OCR if the structured parse yielded nothing
    if not elements:
        logger.info(f"Page {page.number} returned empty structured bounds. Applying raw OCR fallback.")
        img_page = _page_to_image(page, dpi=dpi)
        ocr_text = extract_text_from_image(img_page, lang=ocr_lang)
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

    # Sort comprehensively by the Y coordinate vertical structure axis
    elements.sort(key=lambda x: x[0])
    return elements


def extract_text_from_pdf(
    pdf_path: str | Path,
    lang: str = 'eng',
    dpi: int = OCR_DPI,
) -> str:
    """
    Extract searchable strings directly from a PDF text layer.
    Automatically applies OCR scanning when a page presents as scanned.
    
    Args:
        pdf_path: Source PDF file.
        lang: Optical Character Recognition language.
        dpi: OCR internal resolution constraint.
    
    Returns:
        str: Discovered string document chunk.
    """
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
