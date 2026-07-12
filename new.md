# QUETEX WEB SYSTEM — IMPROVED WORKING PROMPT

## CORE PROBLEM TO SOLVE
The current system shows 0 signals because:
1. yfinance data is delayed 15min — not suitable for binary options
2. MIN_CONFIDENCE=70 + ATR filter = almost nothing passes
3. No real Quotex connection possible (no official API)

## SOLUTION: Use Reliable Free Real-Time Data

Replace yfinance with these FREE, real-time sources:
- Forex: exchangerate.host API (free, real-time)
- Crypto: CoinGecko API (free, real-time)
- Backup: Twelve Data free tier (8 requests/min free)

## FILE: config.py CHANGES

MIN_CONFIDENCE = 55    # Lower from 70 to 55 — more signals
SCAN_INTERVAL = 1      # Scan every 1 minute (not 5)
COOLDOWN_MIN = 5       # 5 min cooldown (not 15)
GOOD_HOURS = list(range(0, 24))  # ALL hours (remove session filter)
MIN_ATR_PCT = 0.00005  # Much lower ATR filter

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

## FILE: data_client.py — NEW VERSION

Use Twelve Data free API for real-time OHLCV:

```python
import aiohttp

TWELVE_DATA_KEY = "your_free_key_from_twelvedata.com"

async def get_candles(symbol: str, interval: str, outputsize: int = 100):
    url = f"https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_KEY,
        "format": "JSON"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as r:
            data = await r.json()
            if "values" not in data:
                return None
            df = pd.DataFrame(data["values"])
            df = df.rename(columns={"datetime":"timestamp","open":"Open",
                                     "high":"High","low":"Low",
                                     "close":"Close","volume":"Volume"})
            for col in ["Open","High","Low","Close","Volume"]:
                df[col] = pd.to_numeric(df[col])
            df = df.sort_values("timestamp").reset_index(drop=True)
            return df
```

## SIGNAL QUALITY IMPROVEMENTS

1. Lower MIN_CONFIDENCE to 55% — more signals will appear
2. Remove ATR filter OR lower it to 0.00005
3. Remove GOOD_HOURS restriction — scan 24/7
4. Reduce COOLDOWN to 5 minutes
5. Add fallback: if confidence < 55%, show "WEAK" signal with warning

## DASHBOARD IMPROVEMENTS

Add to index.html:
- Show WEAK signals (50-65%) in yellow/gray color
- Add "Signal Strength" label: STRONG/MEDIUM/WEAK
- Show last data fetch time so user knows data is fresh
- Add manual REFRESH button that instantly triggers scan
- Show which assets had data errors in red

## IMPORTANT DISCLAIMER
This system generates signals based on technical indicators only.
Signals do NOT directly connect to Quotex platform.
Use signals as guidance only — always verify before trading.
No system achieves 90%+ accuracy consistently.