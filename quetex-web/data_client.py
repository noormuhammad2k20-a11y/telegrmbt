"""
data_client.py — Market data via yfinance.
yfinance is FREE, reliable, no API key needed.
Supports Forex OTC pairs, Crypto, and Indices.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
import pandas as pd
import yfinance as yf
from config import ASSET_MAP, TF_PERIOD_MAP

logger = logging.getLogger(__name__)

# In-memory cache: avoid hammering API
_cache: dict[str, tuple[pd.DataFrame, float]] = {}
CACHE_TTL = 45   # seconds


def _cache_key(asset: str, tf: str) -> str:
    return f"{asset}:{tf}"


def _is_fresh(ts: float) -> bool:
    import time
    return (time.time() - ts) < CACHE_TTL


async def get_candles(asset: str, timeframe: str,
                      count: int = 200) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candles for the given asset and timeframe.

    Returns DataFrame with lowercase columns: open, high, low, close, volume
    Sorted ascending by time. Returns None on failure.
    """
    import time
    key = _cache_key(asset, timeframe)
    if key in _cache:
        df, ts = _cache[key]
        if _is_fresh(ts) and len(df) >= 30:
            return df.copy()

    ticker = ASSET_MAP.get(asset)
    if not ticker:
        logger.warning("No yfinance ticker for asset: %s", asset)
        return None

    period, interval = TF_PERIOD_MAP.get(timeframe, ("7d", "1m"))

    try:
        df = yf.download(
            tickers=ticker,
            period=period,
            interval=interval,
            progress=False,
            auto_adjust=True,
            prepost=False,
        )
        if df is None or df.empty:
            logger.warning("Empty data for %s (%s)", asset, ticker)
            return None

        # Flatten MultiIndex columns if present (yfinance >= 0.2.31)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

        df.columns = [c.lower() for c in df.columns]

        # Ensure required columns exist
        for col in ["open", "high", "low", "close"]:
            if col not in df.columns:
                logger.warning("Missing column %s for %s", col, asset)
                return None

        if "volume" not in df.columns:
            df["volume"] = 0.0

        df = df[["open", "high", "low", "close", "volume"]].copy()
        df = df.dropna(subset=["open", "high", "low", "close"])
        df = df.sort_index()

        # Tail to count
        if len(df) > count:
            df = df.tail(count)

        df = df.reset_index(drop=True)

        _cache[key] = (df.copy(), time.time())
        logger.info("Fetched %d candles for %s/%s", len(df), asset, timeframe)
        return df

    except Exception as exc:
        logger.error("get_candles(%s, %s) error: %s", asset, timeframe, exc)
        return None


async def get_price(asset: str) -> float:
    """Return latest price for asset."""
    df = await get_candles(asset, "1m", count=5)
    if df is not None and len(df) > 0:
        return float(df["close"].iloc[-1])
    return 0.0


def get_all_prices() -> dict:
    """Synchronous batch price fetch for dashboard display."""
    prices = {}
    for asset, ticker in ASSET_MAP.items():
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            prices[asset] = round(float(info.last_price), 6)
        except Exception:
            prices[asset] = 0.0
    return prices
