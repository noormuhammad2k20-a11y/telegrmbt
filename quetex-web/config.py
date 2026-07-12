"""
config.py — All Quetex Web settings.
Assets mapped to Twelve Data API symbols (FREE, real-time data).
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
MIN_CONFIDENCE   = float(os.getenv("MIN_CONFIDENCE", 55))
WEAK_CONFIDENCE  = float(os.getenv("WEAK_CONFIDENCE", 50))   # show weak signals above this
SCAN_INTERVAL    = int(os.getenv("SCAN_INTERVAL", 1))    # minutes
COOLDOWN_MIN     = 5     # minutes between signals per asset
CANDLE_COUNT_1M  = 200   # 1-minute candles to fetch
CANDLE_COUNT_5M  = 150   # 5-minute candles

# ─── Twelve Data API ─────────────────────────────────────────
TWELVE_DATA_KEY  = os.getenv("TWELVE_DATA_KEY", "")

# ─── Asset Map: Display Name → Twelve Data Symbol ────────────
# Twelve Data free tier: 8 requests/min, real-time data
ASSET_MAP = {
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "EURJPY": "EUR/JPY",
    "BTCUSD": "BTC/USD",
    "ETHUSD": "ETH/USD",
    "AUDUSD": "AUD/USD",
    "USDCHF": "USD/CHF",
}

ALL_ASSETS = list(ASSET_MAP.keys())

# ─── Timeframe Settings ──────────────────────────────────────
TF_1M  = "1min"
TF_5M  = "5min"
TF_15M = "15min"

# Twelve Data interval names
TF_TD_MAP = {
    "1min":  "1min",
    "5min":  "5min",
    "15min": "15min",
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
MIN_ATR_PCT = 0.00005   # much lower ATR filter — more signals pass

# ─── MTF Adjustments ─────────────────────────────────────────
MTF_BOOST   = 8.0    # +8% if higher TF confirms
MTF_PENALTY = 10.0   # -10% if higher TF opposes

# ─── Market Session Filter (UTC hours) ───────────────────────
GOOD_HOURS = list(range(0, 24))   # ALL hours — scan 24/7

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
