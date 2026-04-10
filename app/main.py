import asyncio
import uuid
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, FSInputFile
from pydantic_settings import BaseSettings
from loguru import logger

from app.services.converter import convert_pdf_to_word
from app.services.validator import validate_pdf_upload, ValidationError
from app.utils.logger import setup_logger

class Settings(BaseSettings):
    bot_token: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

class UploadProcess(StatesGroup):
    waiting_for_file = State()

settings = Settings()
bot = Bot(token=settings.bot_token)
dp = Dispatcher()

TEMP_DIR = Path("/app/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    """Handle /start command."""
    logger.info(f"User {message.from_user.id} started the bot.")
    await message.answer("Welcome! Please upload a file (like a PDF or ZIP).")
    await state.set_state(UploadProcess.waiting_for_file)

@dp.message(UploadProcess.waiting_for_file, F.document)
async def handle_document_upload(message: Message, state: FSMContext) -> None:
    """Handle document uploads for conversion."""
    user_id = message.from_user.id
    file_id = message.document.file_id
    file_name = message.document.file_name or "uploaded.pdf"
    file_size = message.document.file_size or 0
    
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
        await bot.download(message.document, destination=pdf_path)
        
        # 3. Convert
        logger.info(f"Starting conversion for {pdf_path}")
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
        # 5. Cleanup temporary files
        logger.info(f"Cleaning up temporary files for {unique_id}")
        if pdf_path.exists():
            try:
                pdf_path.unlink()
                logger.info(f"Deleted {pdf_path}")
            except Exception as e:
                logger.error(f"Failed to delete {pdf_path}: {e}")
                
        if docx_path.exists():
            try:
                docx_path.unlink()
                logger.info(f"Deleted {docx_path}")
            except Exception as e:
                logger.error(f"Failed to delete {docx_path}: {e}")
                
        # Clear state
        await state.clear()

@dp.message(UploadProcess.waiting_for_file)
async def handle_invalid_upload(message: Message) -> None:
    """Handle invalid non-document messages during upload state."""
    logger.warning(f"User {message.from_user.id} sent an invalid message type.")
    await message.answer("That doesn't look like a document. Please upload a file.")

async def main() -> None:
    """Main bot execution."""
    setup_logger()
    logger.info("Starting bot...")
    try:
        await bot.delete_webhook(drop_pending_updates=True) 
        await dp.start_polling(bot)
    finally:
        logger.info("Bot stopped.")

if __name__ == "__main__":
    asyncio.run(main())
