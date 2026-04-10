import asyncio
from aiogram import Bot, Dispatcher
from loguru import logger

from app.config import settings
from app.handlers.base import router as base_router
from app.handlers.conversion import router as conversion_router
from app.utils.logger import setup_logger

async def main() -> None:
    """
    Main application entry point.
    
    Initializes standard logging, registers application routers,
    and starts the asynchronous polling mechanism for the Telegram bot.
    """
    setup_logger()
    logger.info("Initializing bot component.")
    
    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    
    # Register routers
    dp.include_router(conversion_router)
    dp.include_router(base_router)

    try:
        logger.info("Dropping pending updates and starting polling...")
        await bot.delete_webhook(drop_pending_updates=True) 
        await dp.start_polling(bot)
    finally:
        logger.info("Bot execution halted.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
