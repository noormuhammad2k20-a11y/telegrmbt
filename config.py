# config.py
"""
Quetex Bot — Configuration
Loads all environment variables from .env with proper types and defaults.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ────────────────────────────────────────────────
TELEGRAM_TOKEN    = os.getenv("TELEGRAM_TOKEN")
try:
    TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
except ValueError:
    TELEGRAM_CHAT_ID = 0

# ─── Quotex Credentials ─────────────────────────────────────
QUOTEX_EMAIL      = os.getenv("QUOTEX_EMAIL")
QUOTEX_PASSWORD   = os.getenv("QUOTEX_PASSWORD")

# ─── Bot Settings ────────────────────────────────────────────
SIGNAL_INTERVAL   = int(os.getenv("SIGNAL_INTERVAL", "5"))          # Minutes between auto-scans
MIN_CONFIDENCE    = float(os.getenv("MIN_CONFIDENCE", "70"))        # Minimum % to send signal
ASSETS            = os.getenv("ASSETS", "EURUSD-OTC").split(",")    # Comma-separated asset list
TIMEFRAMES        = [int(t) for t in os.getenv("TIMEFRAMES", "60,300").split(",")]  # Seconds
USE_DEMO          = os.getenv("USE_DEMO", "true").lower() == "true" # Demo vs real account

# ─── Constants ───────────────────────────────────────────────
CANDLE_COUNT      = 100     # Number of historical candles to fetch per analysis
COOLDOWN_MINUTES  = 15      # Minimum minutes between signals for same asset
MAX_SCORE         = 12      # Maximum possible indicator score (for confidence calc)
