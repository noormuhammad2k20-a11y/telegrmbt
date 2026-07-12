"""
data_client.py — Market data via Twelve Data API (free tier).
Real-time OHLCV data. 8 requests/min on free plan.
Supports Forex and Crypto pairs.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import pandas as pd

import config as C

logger = logging.getLogger(__name__)

# In-memory cache: avoid hammering API
_cache: dict[str, tuple[pd.DataFrame, float]] = {}
CACHE_TTL = 45   # seconds

# Track data errors per asset for dashboard display
data_errors: dict[str, str] = {}

# Track last fetch time for freshness display
last_fetch_time: str = "Never"

# Rate limiter: max 8 requests per minute for free tier
_request_times: list[float] = []
MAX_REQUESTS_PER_MIN = 8


async def _rate_limit():
    """Enforce rate limit for Twelve Data free tier."""
    global _request_times
    now = time.time()
    # Remove requests older than 60 seconds
    _request_times = [t for t in _request_times if now - t < 60]
    if len(_request_times) >= MAX_REQUESTS_PER_MIN:
        wait = 60 - (now - _request_times[0]) + 0.5
        if wait > 0:
            logger.info("Rate limit: waiting %.1f seconds", wait)
            await asyncio.sleep(wait)
    _request_times.append(time.time())


def _cache_key(asset: str, tf: str) -> str:
    return f"{asset}:{tf}"


def _is_fresh(ts: float) -> bool:
    return (time.time() - ts) < CACHE_TTL


async def get_candles(asset: str, timeframe: str,
                      count: int = 200) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candles for the given asset and timeframe via Twelve Data.

    Returns DataFrame with lowercase columns: open, high, low, close, volume
    Sorted ascending by time. Returns None on failure.
    """
    global last_fetch_time

    key = _cache_key(asset, timeframe)
    if key in _cache:
        df, ts = _cache[key]
        if _is_fresh(ts) and len(df) >= 30:
            return df.copy()

    symbol = C.ASSET_MAP.get(asset)
    if not symbol:
        logger.warning("No Twelve Data symbol for asset: %s", asset)
        data_errors[asset] = "No symbol mapped"
        return None

    api_key = C.TWELVE_DATA_KEY
    if not api_key:
        logger.error("TWELVE_DATA_KEY not set in .env")
        data_errors[asset] = "API key missing"
        return None

    interval = C.TF_TD_MAP.get(timeframe, "1min")

    try:
        await _rate_limit()

        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": symbol,
            "interval": interval,
            "outputsize": count,
            "apikey": api_key,
            "format": "JSON",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
                data = await r.json()

                if "values" not in data:
                    error_msg = data.get("message", data.get("status", "Unknown error"))
                    logger.warning("No data for %s (%s): %s", asset, symbol, error_msg)
                    data_errors[asset] = str(error_msg)[:80]
                    return None

                df = pd.DataFrame(data["values"])
                df = df.rename(columns={
                    "datetime": "timestamp",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                })

                for col in ["open", "high", "low", "close"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce")

                if "volume" in df.columns:
                    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
                else:
                    df["volume"] = 0.0

                df = df[["open", "high", "low", "close", "volume"]].copy()
                df = df.dropna(subset=["open", "high", "low", "close"])
                df = df.iloc[::-1].reset_index(drop=True)  # Twelve Data returns newest first

                if len(df) > count:
                    df = df.tail(count).reset_index(drop=True)

                _cache[key] = (df.copy(), time.time())
                last_fetch_time = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

                # Clear any previous error for this asset
                if asset in data_errors:
                    del data_errors[asset]

                logger.info("Fetched %d candles for %s/%s via Twelve Data",
                            len(df), asset, timeframe)
                return df

    except asyncio.TimeoutError:
        logger.error("Timeout fetching %s/%s", asset, timeframe)
        data_errors[asset] = "Request timeout"
        return None
    except Exception as exc:
        logger.error("get_candles(%s, %s) error: %s", asset, timeframe, exc)
        data_errors[asset] = str(exc)[:80]
        return None


async def get_price(asset: str) -> float:
    """Return latest price for asset."""
    df = await get_candles(asset, "1min", count=5)
    if df is not None and len(df) > 0:
        return float(df["close"].iloc[-1])
    return 0.0


def get_data_errors() -> dict:
    """Return current data fetch errors per asset."""
    return dict(data_errors)


def get_last_fetch_time() -> str:
    """Return last successful data fetch time."""
    return last_fetch_time
