import logging
import os
import sys
from dotenv import load_dotenv
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from src.database.db import init_db
from src.bot.handlers import (
    start_command,
    add_habit_command,
    list_command,
    status_command,
    help_command,
    test_morning_command,
    test_rescue_command,
    test_duolingo_command,
    test_weekly_command,
    process_text_message,
    text_message_handler,
    button_callback_handler,
)
from src.scheduler.jobs import setup_scheduler

# Load environment variables from .env
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
import asyncio

async def start_health_check_server() -> None:
    """Start lightweight HTTP server for cloud platforms (Render, Koyeb) if PORT is set."""
    port_str = os.getenv("PORT")
    if not port_str:
        return

    try:
        port = int(port_str)
    except ValueError:
        return

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            await reader.read(1024)
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/plain; charset=utf-8\r\n"
                b"Content-Length: 15\r\n"
                b"Connection: close\r\n\r\n"
                b"HabitBot Online"
            )
            writer.write(response)
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    logger.info(f"Health check HTTP server running on port {port}")


async def post_init(application: Application) -> None:
    """Async callback triggered upon bot startup before polling begins."""
    logger.info("Initializing SQLite database...")
    await init_db()
    logger.info("Database initialized successfully.")
    await start_health_check_server()


def create_application() -> Application:
    """Build and configure the Telegram Bot Application and Scheduler."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token.strip() == "":
        logger.error(
            "CRITICAL: TELEGRAM_BOT_TOKEN is missing or empty in .env! "
            "Please add your bot token from @BotFather."
        )
        sys.exit(1)

    # Initialize Application with APScheduler-backed JobQueue
    app = (
        Application.builder()
        .token(token.strip())
        .post_init(post_init)
        .build()
    )

    # Register Command Handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("add_habit", add_habit_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("test_morning", test_morning_command))
    app.add_handler(CommandHandler("test_rescue", test_rescue_command))
    app.add_handler(CommandHandler("test_duolingo", test_duolingo_command))
    app.add_handler(CommandHandler("test_weekly", test_weekly_command))

    # Register Message Handler for Natural Language Habit Processing and Buttons
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_text_message))

    # Register Callback Query Handler for Interactive Buttons
    app.add_handler(CallbackQueryHandler(button_callback_handler))

    # Setup APScheduler Background Dispatcher
    setup_scheduler(app)

    return app


def main() -> None:
    """Main entry point for HabitBot."""
    logger.info("Starting HabitBot with Gemini AI Natural Language & Reply Keyboard...")
    app = create_application()
    logger.info("HabitBot handlers and scheduler registered. Starting polling...")
    app.run_polling()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logger.info("HabitBot stopped cleanly.")
