"""
config.py — All Quetex Web settings.
Assets mapped to yfinance tickers (FREE, reliable data).
"""
import os
from dotenv import load_dotenv
load_dotenv()

# ─── App Settings ────────────────────────────────────────────
SECRET_KEY      = os.getenv("SECRET_KEY", "quetex2025")
PASSWORD        = os.getenv("PASSWORD", "quetex123")
PORT            = int(os.getenv("PORT", 8000))

# ─── Database Settings ───────────────────────────────────────
DB_HOST         = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT         = int(os.getenv("DB_PORT", 3307))
DB_USER         = os.getenv("DB_USER", "root")
DB_PASS         = os.getenv("DB_PASS", "")
DB_NAME         = os.getenv("DB_NAME", "quetex_signals")

# ─── Signal Settings ─────────────────────────────────────────
MIN_CONFIDENCE   = float(os.getenv("MIN_CONFIDENCE", 70))
SCAN_INTERVAL    = int(os.getenv("SCAN_INTERVAL", 5))    # minutes
COOLDOWN_MIN     = 15    # minutes between signals per asset
CANDLE_COUNT_1M  = 200   # 1-minute candles to fetch
CANDLE_COUNT_5M  = 150   # 5-minute candles

# ─── Asset Map: Display Name → yfinance Ticker ───────────────
# yfinance is FREE, stable, no API key needed
ASSET_MAP = {
    "EURUSD-OTC": "EURUSD=X",
    "GBPUSD-OTC": "GBPUSD=X",
    "USDJPY-OTC": "USDJPY=X",
    "EURJPY-OTC": "EURJPY=X",
    "GBPJPY-OTC": "GBPJPY=X",
    "AUDUSD-OTC": "AUDUSD=X",
    "USDCHF-OTC": "USDCHF=X",
    "NZDUSD-OTC": "NZDUSD=X",
    "AUDCAD-OTC": "AUDCAD=X",
    "EURGBP-OTC": "EURGBP=X",
    "BTCUSD":     "BTC-USD",
    "ETHUSD":     "ETH-USD",
}

ALL_ASSETS = list(ASSET_MAP.keys())

# ─── Timeframe Settings ──────────────────────────────────────
TF_1M  = "1m"
TF_5M  = "5m"
TF_15M = "15m"

# yfinance period for each interval
TF_PERIOD_MAP = {
    "1m":  ("7d",  "1m"),   # period, interval
    "5m":  ("60d", "5m"),
    "15m": ("60d", "15m"),
}

# Main scan timeframes
SCAN_TIMEFRAMES = [TF_1M, TF_5M]

# ─── Indicator Weights (MUST sum = 100) ──────────────────────
WEIGHTS = {
    "rsi":        12,
    "macd":       18,   # most reliable → highest weight
    "bollinger":   8,
    "stochastic": 12,
    "ema":        10,
    "williams_r":  8,
    "cci":         7,
    "psar":        5,
    "pattern":    15,   # price action → high weight
    "volume":      5,
}
assert sum(WEIGHTS.values()) == 100

# ─── ADX Thresholds ──────────────────────────────────────────
ADX_WEAK    = 15
ADX_NORMAL  = 25
ADX_STRONG  = 35

# ─── Volatility Filter ───────────────────────────────────────
MIN_ATR_PCT = 0.00015   # skip if ATR < 0.015% of price

# ─── MTF Adjustments ─────────────────────────────────────────
MTF_BOOST   = 8.0    # +8% if higher TF confirms
MTF_PENALTY = 10.0   # -10% if higher TF opposes

# ─── Market Session Filter (UTC hours) ───────────────────────
GOOD_HOURS = list(range(7, 22))   # 07:00-22:00 UTC

# ─── Indicator Periods ───────────────────────────────────────
RSI_LEN   = 14
MACD_F    = 12; MACD_S = 26; MACD_G = 9
BB_LEN    = 20; BB_STD = 2.0
STOCH_K   = 14; STOCH_D = 3
EMA_FAST  = 21; EMA_MED = 50; EMA_SLOW = 200
ADX_LEN   = 14
WILLR_LEN = 14
CCI_LEN   = 20
ATR_LEN   = 14
