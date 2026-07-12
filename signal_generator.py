# signal_generator.py
"""
Quetex Bot — Signal Generator
Applies confidence threshold, maps expiry times, and collects confirming indicators.
"""

import logging
from config import MIN_CONFIDENCE

logger = logging.getLogger(__name__)


class SignalGenerator:
    """Generates actionable trading signals from analysis results."""

    def generate(self, analysis: dict, asset: str, timeframe: int) -> dict | None:
        """
        Generate a trading signal from analysis data.

        Args:
            analysis: Output dict from TechnicalAnalyzer.analyze()
            asset: Asset name (e.g., 'EURUSD-OTC')
            timeframe: Timeframe in seconds (60, 300, etc.)

        Returns:
            Signal dict with all display data, or None if confidence is below threshold.
        """
        # Gate: do NOT send signal if confidence is too low
        if analysis["confidence"] < MIN_CONFIDENCE:
            logger.info(
                f"[SignalGen] {asset} confidence {analysis['confidence']}% "
                f"below threshold {MIN_CONFIDENCE}%. Skipping."
            )
            return None

        # Map timeframe (seconds) to human-readable expiry
        expiry_map = {60: "1 minute", 300: "5 minutes", 900: "15 minutes"}
        expiry = expiry_map.get(timeframe, f"{timeframe // 60} minutes")

        # Collect confirming indicators
        direction = analysis["direction"]
        confirming = []
        ind = analysis["indicators"]

        # RSI
        if ind["rsi"]["signal"] == direction:
            val = ind["rsi"]["value"]
            label = f"RSI {val} ({'Oversold' if val < 30 else 'Overbought'})"
            confirming.append(label)

        # MACD
        if ind["macd"]["signal"] == direction:
            cross_type = "Bullish Cross" if direction == "BUY" else "Bearish Cross"
            confirming.append(f"MACD {cross_type}")

        # Bollinger Bands
        if ind["bb"]["signal"] == direction:
            band = "Lower Band" if direction == "BUY" else "Upper Band"
            confirming.append(f"BB: Price at {band}")

        # Stochastic
        if ind["stoch"]["signal"] == direction:
            zone = "Buy Zone" if direction == "BUY" else "Sell Zone"
            confirming.append(f"Stoch K={ind['stoch']['k']} ({zone})")

        # EMA
        if ind["ema"]["signal"] == direction:
            comparison = ">" if direction == "BUY" else "<"
            confirming.append(f"EMA21 {comparison} EMA50")

        # Candlestick Pattern
        if (
            ind["pattern"]["signal"] == direction
            and ind["pattern"]["name"] != "None"
        ):
            confirming.append(f"Pattern: {ind['pattern']['name']}")

        # ADX
        if ind["adx"]["strong"]:
            confirming.append(f"ADX {ind['adx']['value']} (Strong trend)")

        signal = {
            "direction": direction,
            "asset": asset,
            "expiry": expiry,
            "timeframe": timeframe,
            "confidence": analysis["confidence"],
            "entry_price": analysis["current_price"],
            "pattern": ind["pattern"]["name"],
            "confirming_indicators": confirming,
            "timestamp": analysis["timestamp"],
        }

        logger.info(
            f"[SignalGen] ✅ Signal generated: {direction} {asset} "
            f"@ {analysis['confidence']}% confidence"
        )
        return signal
