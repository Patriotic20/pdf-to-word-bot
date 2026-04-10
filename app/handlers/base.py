from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

router = Router(name="base_handlers")

@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    """
    Handle the /start command.
    
    Welcomes the user and provides basic instructions.
    """
    logger.info(f"User {message.from_user.id} started the bot.")
    await message.answer(
        "Welcome! You can send me a PDF file anytime, "
        "and I will convert it to Word for you."
    )

@router.message()
async def handle_invalid_upload(message: Message) -> None:
    """
    Fallback handler for non-document messages.
    
    Guides the user on how to interact with the bot.
    """
    logger.warning(f"User {message.from_user.id} sent an invalid message type.")
    await message.answer("Please send me a PDF file to convert to Word.")
