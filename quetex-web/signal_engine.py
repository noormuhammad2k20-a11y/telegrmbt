"""
signal_engine.py — Signal generation with MTF, session filter, cooldown.
Scans all assets in parallel. Returns signals sorted by confidence.
Includes WEAK signal support (50-65% confidence shown with warning).
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
import config as C
from data_client import get_candles
from analyzer import TechnicalAnalyzer, AnalysisResult

logger = logging.getLogger(__name__)

# In-memory cooldown: {asset_tf: datetime}
_cooldown: dict[str, datetime] = {}


def _on_cooldown(asset: str, tf: str) -> bool:
    key = f"{asset}:{tf}"
    last = _cooldown.get(key)
    if not last:
        return False
    delta = (datetime.now(timezone.utc) - last).total_seconds()
    return delta < C.COOLDOWN_MIN * 60


def _mark(asset: str, tf: str):
    _cooldown[f"{asset}:{tf}"] = datetime.now(timezone.utc)


def _in_session() -> bool:
    h = datetime.now(timezone.utc).hour
    return h in C.GOOD_HOURS


def _get_strength_label(confidence: float) -> str:
    """Return signal strength label based on confidence."""
    if confidence >= 75:
        return "STRONG"
    elif confidence >= 60:
        return "MEDIUM"
    else:
        return "WEAK"


_analyzer = TechnicalAnalyzer()


async def _get_mtf_trend(asset: str, confirm_tf: str) -> Optional[str]:
    """
    Get higher-TF trend for MTF confirmation.
    Returns 'BUY', 'SELL', or 'NEUTRAL'.
    """
    try:
        df = await get_candles(asset, confirm_tf, count=80)
        if df is None or len(df) < 55:
            return None
        import ta as ta_lib
        df = df.copy()
        df["ema_21"] = ta_lib.trend.EMAIndicator(close=df["close"], window=21).ema_indicator()
        df["ema_50"] = ta_lib.trend.EMAIndicator(close=df["close"], window=50).ema_indicator()
        p = float(df["close"].iloc[-1])
        e21 = float(df["ema_21"].iloc[-1]) if "ema_21" in df else p
        e50 = float(df["ema_50"].iloc[-1]) if "ema_50" in df else p
        if p > e21 > e50:
            return "BUY"
        if p < e21 < e50:
            return "SELL"
        return "NEUTRAL"
    except Exception:
        return None


async def scan_asset(asset: str, tf: str,
                      force: bool = False) -> Optional[dict]:
    """
    Scan one asset on one timeframe.
    Returns signal dict or None.
    Now includes WEAK signals (confidence >= WEAK_CONFIDENCE).
    """
    if not force and _on_cooldown(asset, tf):
        return None

    df = await get_candles(asset, tf)
    if df is None or df.empty:
        return None

    result: Optional[AnalysisResult] = _analyzer.analyze(df, asset, tf)
    if result is None:
        return None

    # Skip low volatility (but use much lower threshold now)
    if result.low_vol:
        logger.debug("Skip %s/%s: low volatility", asset, tf)
        return None

    # MTF confirmation
    confirm_tf = C.TF_5M if tf == C.TF_1M else C.TF_15M
    mtf_trend = await _get_mtf_trend(asset, confirm_tf)
    mtf_note = ""

    if mtf_trend == result.direction:
        result.confidence = min(result.confidence + C.MTF_BOOST, 97.0)
        mtf_note = f"✅ {confirm_tf} confirms {result.direction}"
    elif mtf_trend and mtf_trend not in (None, "NEUTRAL"):
        result.confidence = max(result.confidence - C.MTF_PENALTY, 0.0)
        mtf_note = f"⚠️ {confirm_tf} conflicts ({mtf_trend})"
    else:
        mtf_note = f"➖ {confirm_tf} neutral"

    result.confidence = round(result.confidence, 2)

    # WEAK signal threshold — show signals >= WEAK_CONFIDENCE with warning
    if result.confidence < C.WEAK_CONFIDENCE:
        return None

    # Determine signal strength label
    strength = _get_strength_label(result.confidence)
    is_weak = result.confidence < C.MIN_CONFIDENCE

    # Expiry map
    expiry_map = {"1min": "1 Minute", "5min": "5 Minutes", "15min": "15 Minutes"}
    expiry = expiry_map.get(tf, tf)

    _mark(asset, tf)

    return {
        "asset":       asset,
        "direction":   result.direction,
        "timeframe":   tf,
        "expiry":      expiry,
        "confidence":  result.confidence,
        "price":       result.price,
        "pattern":     result.pattern,
        "adx":         result.adx,
        "atr_pct":     result.atr_pct,
        "buy_pct":     result.buy_pct,
        "sell_pct":    result.sell_pct,
        "confirming":  result.confirming,
        "opposing":    result.opposing,
        "mtf_note":    mtf_note,
        "timestamp":   result.timestamp,
        "strength":    strength,
        "is_weak":     is_weak,
    }


async def scan_all(force: bool = False,
                   max_results: int = 10) -> list[dict]:
    """Scan all assets × all timeframes in parallel."""
    tasks = [
        scan_asset(a, tf, force)
        for a in C.ALL_ASSETS
        for tf in C.SCAN_TIMEFRAMES
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    signals = [r for r in results if isinstance(r, dict)]
    signals.sort(key=lambda x: x["confidence"], reverse=True)
    return signals[:max_results]


async def scan_one(asset: str) -> list[dict]:
    """Scan one specific asset on all timeframes."""
    tasks = [scan_asset(asset, tf, force=True) for tf in C.SCAN_TIMEFRAMES]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    signals = [r for r in results if isinstance(r, dict)]
    signals.sort(key=lambda x: x["confidence"], reverse=True)
    return signals
