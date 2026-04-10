from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message
from loguru import logger

from app.config import TEMP_DIR
from app.services.converter import convert_pdf_to_word
from app.services.validator import ValidationError, validate_pdf_upload
from app.utils.file_helpers import delete_temp_files

router = Router(name="conversion_handlers")

@router.message(F.document)
async def handle_document_upload(message: Message, state: FSMContext, bot: Bot) -> None:
    """
    Handle document uploads for on-demand conversion.
    
    Accepts PDF files, processes them asynchronously, and returns
    a formatted DOCX file. Clears any existing FSM state gracefully.
    """
    # Clear any existing FSM state gracefully
    await state.clear()
    
    user_id = message.from_user.id
    document = message.document
    
    if not document:
        logger.warning(f"User {user_id} sent a message without a document.")
        return

    file_id = document.file_id
    file_name = document.file_name or "uploaded.pdf"
    file_size = document.file_size or 0
    
    logger.info(f"User {user_id} uploaded a file: {file_name} (ID: {file_id}, Size: {file_size} bytes)")
    
    # 1. Validation
    try:
        validate_pdf_upload(file_name, file_size)
        logger.info(f"Validation successful for user {user_id}'s file {file_name}")
    except ValidationError as e:
        logger.warning(f"Validation failed for user {user_id}: {e}")
        error_msg = str(e)
        if "size" in error_msg.lower():
            await message.answer(error_msg)
        else:
            await message.answer("Only PDF files are supported.")
        return

    # Notify user that process started
    await message.answer("File received! Downloading and converting... This might take a moment. ⏳")
    
    unique_id = uuid.uuid4().hex
    pdf_path = TEMP_DIR / f"{unique_id}.pdf"
    docx_path = TEMP_DIR / f"{unique_id}.docx"
    
    try:
        # 2. Download
        logger.info(f"Downloading file {file_name} to {pdf_path}")
        await bot.download(document, destination=pdf_path)
        
        # 3. Convert
        logger.info(f"Starting conversion for {pdf_path}")
        # Using asyncio.to_thread to keep the bot responsive during heavy CPU tasks
        await asyncio.to_thread(
            convert_pdf_to_word, 
            pdf_path, 
            docx_path, 
            ocr_fallback=True, 
            ocr_lang='eng'
        )
        logger.info(f"Conversion successful, created {docx_path}")
        
        # 4. Send
        logger.info(f"Sending converted document {docx_path.name} to user {user_id}")
        await message.answer_document(
            FSInputFile(path=str(docx_path), filename=f"{Path(file_name).stem}.docx"),
            caption="Here is your converted Word document! 🎉"
        )
        
    except Exception as e:
        logger.error(f"Error processing file for user {user_id}: {e}")
        await message.answer("Conversion failed, please try another PDF.")
    finally:
        # 5. Cleanup temporary files using the utility
        logger.info(f"Initiating temporary file cleanup for {unique_id}")
        await delete_temp_files(pdf_path, docx_path)
