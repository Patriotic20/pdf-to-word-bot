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
    # Telegram assigns a unique ID to every file on their servers
    file_id = message.document.file_id
    file_name = message.document.file_name
    
    await message.answer(f"File '{file_name}' received successfully! 📄\nFile ID: {file_id}")
    
    # Process the file here (e.g., download it, save it to PostgreSQL, etc.)
    # await bot.download(message.document, destination=f"./downloads/{file_name}")
    
    # Clear the state so the user is back to normal chat mode
    await state.clear()


# --- 4. Fallback Handler (If they send text instead of a file while in the state) ---
@dp.message(UploadProcess.waiting_for_file)
async def handle_invalid_upload(message: Message):
    await message.answer("That doesn't look like a document. Please upload a file.")

async def main():
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)



if __name__ == "__main__":
    asyncio.run(main())
