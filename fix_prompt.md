# Prompt for LLM: Fix PDF-to-Word Telegram Bot

---

## Role & Context

You are a senior Python developer specializing in aiogram 3.x Telegram bots, async Python, and PDF processing. You have deep knowledge of loguru, pdf2docx, PyMuPDF, and pytesseract.

## Project Context

This is a Telegram bot that accepts PDF uploads from users and converts them to DOCX files. The tech stack is:

- **Python 3.12** with **aiogram 3.x** (FSM-based handlers)
- **pdf2docx** + **PyMuPDF** + **pytesseract** for PDF-to-DOCX conversion (with OCR fallback)
- **python-docx** for DOCX creation
- **loguru** for logging (installed but not wired up)
- **Docker** deployment (Tesseract OCR with `eng` + `rus` language packs installed)

### Current file structure:

```
app/
├── main.py                  # Bot entry point, handlers, FSM states
├── bot/
│   ├── handlers.py          # EMPTY
│   └── messages.py          # EMPTY
├── services/
│   ├── converter.py         # convert_pdf_to_word() — works standalone
│   ├── ocr_service.py       # OCR extraction with Tesseract
│   └── validator.py         # PDF validation (extension, size, existence)
├── states/
│   └── upload_states.py     # EMPTY
└── utils/
    ├── file_manager.py      # EMPTY
    └── logger.py            # EMPTY
```

### Current `app/main.py` (full code):

```python
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
import asyncio


class UploadProcess(StatesGroup):
    waiting_for_file = State()

BOT_TOKEN = "8540988454:AAG6g3gvUMV9dROXmKlnzRvbS_tUu6bHhHw"
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await message.answer("Welcome! Please upload a file (like a PDF or ZIP).")
    await state.set_state(UploadProcess.waiting_for_file)
    
    
@dp.message(UploadProcess.waiting_for_file, F.document)
async def handle_document_upload(message: Message, state: FSMContext):
    file_id = message.document.file_id
    file_name = message.document.file_name
    
    await message.answer(f"File '{file_name}' received successfully! 📄\nFile ID: {file_id}")
    
    # Process the file here (e.g., download it, save it to PostgreSQL, etc.)
    # await bot.download(message.document, destination=f"./downloads/{file_name}")
    
    await state.clear()


@dp.message(UploadProcess.waiting_for_file)
async def handle_invalid_upload(message: Message):
    await message.answer("That doesn't look like a document. Please upload a file.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```

### Current `app/services/converter.py` (full code):

```python
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
```

### Current `app/services/validator.py` (full code):

```python
from __future__ import annotations

from pathlib import Path

ALLOWED_EXTENSIONS = {'.pdf'}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024


class ValidationError(ValueError):
    """Raised when an uploaded or saved PDF fails validation."""


def is_pdf_file(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in ALLOWED_EXTENSIONS


def validate_pdf_file(file_path: str | Path) -> None:
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
    if not is_pdf_file(file_name):
        raise ValidationError("Only PDF files are supported.")

    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"PDF upload is too large ({file_size} bytes). Maximum allowed size is "
            f"{MAX_FILE_SIZE_BYTES} bytes."
        )
```

### Docker setup:

The Dockerfile installs `tesseract-ocr`, `tesseract-ocr-rus`, `tesseract-ocr-eng`. A `temp/` volume is mounted at `/app/temp`.

---

## Tasks

There are **two bugs** to fix:

### Bug 1: Logging is not implemented

The project has `loguru` as a dependency and an empty `app/utils/logger.py`, but no logging is configured or used anywhere. Logs should be visible in Docker container output (`stdout`).

### Bug 2: Bot receives PDF but never returns DOCX

The `handle_document_upload` handler in `main.py` acknowledges the file but **never actually**:
1. Downloads the PDF from Telegram servers to local disk
2. Validates it's a PDF (using `validator.py`)
3. Calls the conversion service (`converter.py`)
4. Sends the resulting DOCX back to the user
5. Cleans up temporary files

The conversion service (`converter.py`) works correctly on its own — the problem is purely that `main.py` doesn't call it.

---

## Requirements

### For Bug 1 (Logging):
1. Configure loguru in `app/utils/logger.py` with a `setup_logger()` function
2. Log to `stdout` (for Docker) with format that includes timestamp, level, and message
3. Optionally also log to a rotating file at `/app/temp/bot.log`
4. Add log statements in:
   - Bot startup and shutdown
   - Every handler entry (user ID, file name)
   - Validation success/failure
   - Conversion start/end/failure
   - File download and file send events
   - Cleanup actions
5. Use appropriate log levels: `INFO` for normal flow, `WARNING` for validation failures, `ERROR` for conversion failures

### For Bug 2 (PDF → DOCX pipeline):
1. In `handle_document_upload`, add the full pipeline:
   - Validate the upload is a PDF using `validate_pdf_upload(file_name, file_size)` **before** downloading
   - Download the file from Telegram to `/app/temp/{unique_name}.pdf` using `await bot.download(...)`
   - Call `convert_pdf_to_word(pdf_path, output_path)` to produce the DOCX (note: this is a **sync** function — wrap it with `asyncio.to_thread()` or `loop.run_in_executor()`)
   - Send the DOCX back to the user via `await message.answer_document(types.FSInputFile(docx_path))`
   - Clean up both the PDF and DOCX temp files in a `finally` block
2. Handle errors gracefully:
   - If the file is not a PDF → tell user "Only PDF files are supported."
   - If the file is too large → tell user the size limit
   - If conversion fails → tell user "Conversion failed, please try another PDF."
3. Use `uuid4()` or similar for temp file naming to avoid collisions
4. Move the bot token to an environment variable or pydantic-settings config (the project already depends on `pydantic-settings`)
5. Keep the FSM flow: user sends `/start` → bot asks for file → user uploads → bot converts and replies → state clears

## Constraints

- **Language/Framework**: Python 3.12, aiogram 3.x, loguru
- **No new dependencies**: Use only what's already in `pyproject.toml`
- **Async safety**: `convert_pdf_to_word()` is synchronous — do NOT call it directly in an async handler. Use `asyncio.to_thread()`.
- **File paths**: Use `/app/temp/` for all temporary files (this directory is a Docker volume)
- **Bot token**: Must NOT be hardcoded. Use `pydantic-settings` `BaseSettings` to load from environment variable `BOT_TOKEN`
- **Existing code**: Do NOT modify `converter.py`, `ocr_service.py`, or `validator.py` — they work correctly

## Expected Output

Provide the following files with complete, working code:

1. **`app/utils/logger.py`** — loguru setup
2. **`app/main.py`** — fully rewritten with the conversion pipeline, logging, and config
3. **`app/bot/handlers.py`** — (optional) if you move handlers out of main.py for cleaner structure

For each file:
- Include all necessary imports
- Add type hints
- Add docstrings for functions
- Include error handling with logging

Label each file clearly in your response.
