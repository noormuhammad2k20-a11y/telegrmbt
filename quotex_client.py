# quotex_client.py
"""
Quetex Bot — Quotex WebSocket Client
Async client wrapping pyquotex for candle fetching and price queries.
"""

import asyncio
import logging
import time
import pandas as pd
from pyquotex.stable_api import Quotex
from config import CANDLE_COUNT

logger = logging.getLogger(__name__)


class QuotexClient:
    """Async Quotex WebSocket client with auto-reconnect."""

    def __init__(self, email: str, password: str, demo: bool = True):
        self.email = email
        self.password = password
        self.demo = demo
        self.client = Quotex(
            email=self.email,
            password=self.password,
            lang="en",
            host="market-qx.trade",
        )
        self.connected = False
        self._max_retries = 3
        self._retry_delay = 5  # seconds

    async def connect(self) -> bool:
        """
        Connect to Quotex WebSocket with retry logic.
        Retries up to 3 times with 5-second delays on failure.
        Returns True if connected successfully.
        """
        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(
                    f"[QuotexClient] Connection attempt {attempt}/{self._max_retries}..."
                )
                check, reason = await self.client.connect()

                if check:
                    self.connected = True
                    # Set account type
                    await self.client.change_account("PRACTICE" if self.demo else "REAL")
                    account_type = "DEMO" if self.demo else "REAL"
                    logger.info(
                        f"[QuotexClient] ✅ Connected successfully ({account_type} account)"
                    )
                    return True
                else:
                    logger.warning(
                        f"[QuotexClient] ❌ Connection failed: {reason}"
                    )
            except Exception as e:
                logger.error(
                    f"[QuotexClient] ❌ Connection error on attempt {attempt}: {e}"
                )

            if attempt < self._max_retries:
                logger.info(
                    f"[QuotexClient] Retrying in {self._retry_delay} seconds..."
                )
                await asyncio.sleep(self._retry_delay)

        logger.error(
            f"[QuotexClient] ❌ Failed to connect after {self._max_retries} attempts."
        )
        self.connected = False
        return False

    async def disconnect(self):
        """Disconnect from Quotex WebSocket."""
        try:
            await self.client.close()
            self.connected = False
            logger.info("[QuotexClient] Disconnected.")
        except Exception as e:
            logger.error(f"[QuotexClient] Error disconnecting: {e}")

    async def _ensure_connected(self):
        """Re-establish connection if dropped."""
        if not self.connected:
            logger.warning("[QuotexClient] Connection lost. Reconnecting...")
            await self.connect()

    async def get_candles(
        self, asset: str, timeframe: int, count: int = CANDLE_COUNT
    ) -> pd.DataFrame:
        """
        Fetch historical candles for an asset.

        Args:
            asset: Asset name (e.g., 'EURUSD-OTC')
            timeframe: Candle period in seconds (60 = 1m, 300 = 5m)
            count: Number of candles to fetch (default: 100)

        Returns:
            DataFrame with columns: time, open, high, low, close, volume
        """
        await self._ensure_connected()

        try:
            candles = await self.client.get_candles(
                asset, end_from_time=None, offset=count * timeframe, period=timeframe
            )

            if not candles:
                logger.warning(
                    f"[QuotexClient] No candles returned for {asset} (tf={timeframe}s)"
                )
                return pd.DataFrame()

            # Convert pyquotex candle format to DataFrame
            # pyquotex returns list of dicts: id, from, to, open, close, min, max, volume
            rows = []
            for c in candles:
                rows.append({
                    "time": c.get("from", c.get("time", 0)),
                    "open": float(c.get("open", 0)),
                    "high": float(c.get("max", c.get("high", 0))),
                    "low": float(c.get("min", c.get("low", 0))),
                    "close": float(c.get("close", 0)),
                    "volume": float(c.get("volume", 0)),
                })

            df = pd.DataFrame(rows)

            if not df.empty:
                df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
                df = df.sort_values("time").reset_index(drop=True)

            logger.info(
                f"[QuotexClient] Fetched {len(df)} candles for {asset} (tf={timeframe}s)"
            )
            return df

        except Exception as e:
            logger.error(f"[QuotexClient] Error fetching candles for {asset}: {e}")
            # Try reconnecting and retrying once
            self.connected = False
            await self._ensure_connected()
            return pd.DataFrame()

    async def get_current_price(self, asset: str) -> float:
        """
        Get the current realtime price for an asset.

        Args:
            asset: Asset name (e.g., 'EURUSD-OTC')

        Returns:
            Current price as float, or 0.0 on error.
        """
        await self._ensure_connected()

        try:
            # Fetch the most recent 1-minute candle to get current price
            candles = await self.client.get_candles(asset, 60, 1, time.time())
            if candles and len(candles) > 0:
                price = float(candles[-1].get("close", 0))
                return price
            return 0.0
        except Exception as e:
            logger.error(
                f"[QuotexClient] Error getting current price for {asset}: {e}"
            )
            return 0.0
