from __future__ import annotations

import io
from pathlib import Path

import fitz
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from loguru import logger
from pdf2docx import Converter as Pdf2DocxConverter

from app.services.ocr_service import extract_page_elements, extract_text_from_pdf, is_text_pdf
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


def _clean_font_name(pdf_font_name: str) -> str:
    """Clean the PDF font name to get the base font name."""
    if not pdf_font_name:
        return "Arial"

    if "+" in pdf_font_name:
        pdf_font_name = pdf_font_name.split("+", 1)[1]

    suffixes = [
        "-BoldItalic", "-Bold", "-Italic", "MT", "PS",
        "Bold", "Italic", "-Oblique", "Oblique"
    ]
    
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if pdf_font_name.endswith(suffix):
                pdf_font_name = pdf_font_name[:-len(suffix)]
                changed = True
                break

    pdf_font_name = pdf_font_name.rstrip("-")
    
    if not pdf_font_name:
        return "Arial"

    return pdf_font_name


def _convert_hybrid(pdf_path: Path, output_path: Path, ocr_lang: str) -> None:
    """Hybrid conversion of PDF to DOCX with styled text and scaled images."""
    document = Document()
    
    with fitz.open(str(pdf_path)) as pdf_doc:
        total_pages = len(pdf_doc)
        if total_pages == 0:
            raise ConversionError("PDF file has 0 pages.")
            
        for page_num in range(total_pages):
            page = pdf_doc[page_num]
            logger.info(f"Processing page {page_num + 1}/{total_pages}")
            
            elements = extract_page_elements(page, ocr_lang=ocr_lang)
            text_count = sum(1 for e in elements if e[1] == "text")
            image_count = sum(1 for e in elements if e[1] == "image")
            
            logger.info(f"Page {page_num + 1} elements - Text blocks: {text_count}, Images: {image_count}")
            
            for _, el_type, content in elements:
                if el_type == "text":
                    paragraph = document.add_paragraph()
                    for span in content:
                        run = paragraph.add_run(span["text"])
                        
                        # Font Name
                        font_name = _clean_font_name(span["font"])
                        if (span.get("flags", 0) & 8) or "Courier" in font_name or "Mono" in font_name:
                            font_name = "Courier New"
                        run.font.name = font_name
                        
                        # Font Size
                        size = span["size"]
                        if size <= 0 or size is None:
                            size = 11.0
                        run.font.size = Pt(size)
                        
                        # Bold
                        if span["bold"] or "Bold" in span["font"]:
                            run.bold = True
                            
                        # Italic
                        if span["italic"] or "Italic" in span["font"] or "Oblique" in span["font"]:
                            run.italic = True
                            
                        # Color
                        r, g, b = span["color_r"], span["color_g"], span["color_b"]
                        if not (r == 0 and g == 0 and b == 0):  # Don't apply pure black manually to support themes
                            run.font.color.rgb = RGBColor(r, g, b)
                            
                elif el_type == "image":
                    try:
                        image_bytes = content["bytes"]
                        img_width_pt = content["width_pt"]
                        page_width_pt = content["page_width_pt"]
                        
                        ratio = img_width_pt / float(page_width_pt) if page_width_pt > 0 else 1.0
                        calc_wd = 6.5 * ratio
                        calc_wd = max(1.0, min(6.5, calc_wd))
                        
                        image_stream = io.BytesIO(image_bytes)
                        document.add_picture(image_stream, width=Inches(calc_wd))
                    except Exception as e:
                        logger.warning(f"Could not add picture to docx on page {page_num + 1}: {e}")
            
            if page_num < total_pages - 1:
                document.add_page_break()
                
    document.save(str(output_path))


def convert_pdf_to_word(
    pdf_path: str | Path,
    output_path: str | Path | None = None,
    *,
    ocr_fallback: bool = True,
    ocr_lang: str = 'eng',
) -> Path:
    """Convert a PDF to a DOCX file, preserving text styles and images."""
    source_path = Path(pdf_path)
    validate_pdf_file(source_path)

    if output_path is None:
        output_path = source_path.with_suffix('.docx')

    target_path = Path(output_path)
    if target_path.suffix.lower() != '.docx':
        target_path = target_path.with_suffix('.docx')

    target_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        _convert_hybrid(source_path, target_path, ocr_lang)
    except Exception as e:
        logger.error(f"Hybrid conversion failed: {e}. Falling back to pdf2docx method...")
        try:
            _convert_pdf2docx(source_path, target_path)
            if not _docx_contains_text(target_path):
                raise ConversionError('Converted document contains no text.')
        except Exception as e2:
            logger.error(f"pdf2docx fallback failed: {e2}. Trying final OCR fallback...")
            if not ocr_fallback:
                raise ConversionError(f"Both hybrid and pdf2docx conversions failed. Hybrid: {e}. pdf2docx: {e2}") from e2
            
            try:
                _create_docx_from_ocr(source_path, target_path, ocr_lang)
            except Exception as e3:
                 raise ConversionError(f"All conversion methods failed.\nHybrid: {e}\npdf2docx: {e2}\nOCR: {e3}") from e3

    return target_path
