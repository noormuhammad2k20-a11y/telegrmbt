# main.py
"""
Quetex Bot — Entry Point
Initializes all components and starts the bot.
"""

import asyncio
import logging
import sys

# Windows console emoji support
if sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import (
    QUOTEX_EMAIL,
    QUOTEX_PASSWORD,
    TELEGRAM_CHAT_ID,
    TELEGRAM_TOKEN,
    USE_DEMO,
)
from quotex_client import QuotexClient
from analyzer import TechnicalAnalyzer
from signal_generator import SignalGenerator
from bot import QuetexBot

# ─── Logging Setup ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def validate_config():
    """Validate that all required configuration is present."""
    errors = []
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "your_bot_token_from_botfather":
        errors.append("TELEGRAM_TOKEN is not set in .env")
    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == 0:
        errors.append("TELEGRAM_CHAT_ID is not set in .env")
    if not QUOTEX_EMAIL or QUOTEX_EMAIL == "your_quotex_login_email":
        errors.append("QUOTEX_EMAIL is not set in .env")
    if not QUOTEX_PASSWORD or QUOTEX_PASSWORD == "your_quotex_login_password":
        errors.append("QUOTEX_PASSWORD is not set in .env")

    if errors:
        for err in errors:
            logger.error(f"❌ Config Error: {err}")
        logger.error("Please fill in the .env file with your actual credentials.")
        sys.exit(1)


async def main():
    """Initialize all components and start the Quetex bot."""
    logger.info("=" * 50)
    logger.info("  QUETEX SIGNAL BOT — Starting Up")
    logger.info("=" * 50)

    # Validate configuration
    validate_config()

    account_type = "DEMO" if USE_DEMO else "REAL"
    logger.info(f"Account mode: {account_type}")

    # Initialize Quotex WebSocket client
    logger.info("Connecting to Quotex...")
    qx_client = QuotexClient(
        email=QUOTEX_EMAIL,
        password=QUOTEX_PASSWORD,
        demo=USE_DEMO,
    )
    connected = await qx_client.connect()
    if not connected:
        logger.error("❌ Failed to connect to Quotex. Bot will start but scans may fail.")
        logger.error("   Check your QUOTEX_EMAIL and QUOTEX_PASSWORD in .env")

    # Initialize analysis components
    analyzer = TechnicalAnalyzer()
    signal_gen = SignalGenerator()

    # Initialize and run Telegram bot
    bot = QuetexBot(
        token=TELEGRAM_TOKEN,
        chat_id=TELEGRAM_CHAT_ID,
        qx_client=qx_client,
        analyzer=analyzer,
        signal_gen=signal_gen,
    )

    if connected:
        logger.info("Quotex Connected")
        logger.info("Auto Scan ON")
        logger.info("Live candle scanning running")
        # Ensure auto_mode is True by default as requested
        bot.auto_mode = True
        bot._save_auto_state()

    logger.info("🚀 Quetex bot starting...")
    try:
        await bot.run()
    except Exception as e:
        logger.error(f"Fatal Telegram Error: {e}")
        logger.error("Failed to initialize the Telegram bot. Check your TELEGRAM_TOKEN and internet connection.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (Ctrl+C).")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
