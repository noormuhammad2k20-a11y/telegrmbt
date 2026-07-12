# analyzer.py
"""
Quetex Bot — Technical Analysis Engine
8-indicator confluence analysis: RSI, MACD, Bollinger Bands, Stochastic,
EMA Crossover, ADX, Candlestick Patterns, Volume Filter.

Uses the 'ta' library (https://github.com/bukosabino/ta) for indicator calculations.
"""

import logging
from datetime import datetime, timezone
import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, EMAIndicator, ADXIndicator
from ta.volatility import BollingerBands
from config import MAX_SCORE

logger = logging.getLogger(__name__)


class TechnicalAnalyzer:
    """Multi-indicator technical analysis engine for trading signals."""

    def analyze(self, df: pd.DataFrame, current_price: float) -> dict:
        """
        Run full 8-indicator analysis on candle data.

        Args:
            df: DataFrame with columns: open, high, low, close, volume
            current_price: Current real-time price of the asset

        Returns:
            Analysis dict with direction, confidence, scores, and all indicator details.
        """
        buy_score = 0
        sell_score = 0

        # Default values in case of errors
        rsi_val = 50.0
        rsi_signal = "NEUTRAL"
        macd_line_val = 0.0
        macd_signal_name = "NEUTRAL"
        bb_upper = 0.0
        bb_lower = 0.0
        bb_signal = "NEUTRAL"
        k_val = 50.0
        stoch_signal = "NEUTRAL"
        ema21_val = 0.0
        ema50_val = 0.0
        ema_signal = "NEUTRAL"
        adx_val = 0.0
        adx_strong = False
        pattern_name = "None"
        pattern_signal = "NEUTRAL"
        vol_ratio = 1.0
        vol_signal = "NEUTRAL"

        try:
            # ──────────────────────────────────────────────────────
            # 1. RSI (14 period)
            # ──────────────────────────────────────────────────────
            rsi_indicator = RSIIndicator(close=df["close"], window=14)
            rsi_series = rsi_indicator.rsi()
            if rsi_series is not None and len(rsi_series.dropna()) > 0:
                rsi_val = rsi_series.iloc[-1]
                if rsi_val < 30:
                    buy_score += 2
                    rsi_signal = "BUY"  # Oversold
                elif rsi_val > 70:
                    sell_score += 2
                    rsi_signal = "SELL"  # Overbought
                else:
                    rsi_signal = "NEUTRAL"
        except Exception as e:
            logger.warning(f"[Analyzer] RSI calculation error: {e}")

        try:
            # ──────────────────────────────────────────────────────
            # 2. MACD (12, 26, 9)
            # ──────────────────────────────────────────────────────
            macd_indicator = MACD(
                close=df["close"], window_slow=26, window_fast=12, window_sign=9
            )
            macd_line_series = macd_indicator.macd()
            signal_line_series = macd_indicator.macd_signal()

            if (
                macd_line_series is not None
                and signal_line_series is not None
                and len(macd_line_series.dropna()) >= 2
                and len(signal_line_series.dropna()) >= 2
            ):
                macd_line = macd_line_series.iloc[-1]
                signal_line = signal_line_series.iloc[-1]
                prev_macd = macd_line_series.iloc[-2]
                prev_signal = signal_line_series.iloc[-2]
                macd_line_val = macd_line

                if prev_macd < prev_signal and macd_line > signal_line:
                    buy_score += 2
                    macd_signal_name = "BUY"  # Bullish crossover
                elif prev_macd > prev_signal and macd_line < signal_line:
                    sell_score += 2
                    macd_signal_name = "SELL"  # Bearish crossover
                else:
                    macd_signal_name = "NEUTRAL"
        except Exception as e:
            logger.warning(f"[Analyzer] MACD calculation error: {e}")

        try:
            # ──────────────────────────────────────────────────────
            # 3. Bollinger Bands (20, 2)
            # ──────────────────────────────────────────────────────
            bb_indicator = BollingerBands(
                close=df["close"], window=20, window_dev=2
            )
            bb_upper_series = bb_indicator.bollinger_hband()
            bb_lower_series = bb_indicator.bollinger_lband()

            if (
                bb_upper_series is not None
                and bb_lower_series is not None
                and len(bb_upper_series.dropna()) > 0
                and len(bb_lower_series.dropna()) > 0
            ):
                bb_upper = bb_upper_series.iloc[-1]
                bb_lower = bb_lower_series.iloc[-1]
                price = current_price

                if price < bb_lower:
                    buy_score += 1
                    bb_signal = "BUY"  # Below lower band
                elif price > bb_upper:
                    sell_score += 1
                    bb_signal = "SELL"  # Above upper band
                else:
                    bb_signal = "NEUTRAL"
        except Exception as e:
            logger.warning(f"[Analyzer] Bollinger Bands calculation error: {e}")

        try:
            # ──────────────────────────────────────────────────────
            # 4. Stochastic (14, 3)
            # ──────────────────────────────────────────────────────
            stoch_indicator = StochasticOscillator(
                high=df["high"], low=df["low"], close=df["close"],
                window=14, smooth_window=3,
            )
            k_series = stoch_indicator.stoch()

            if k_series is not None and len(k_series.dropna()) > 0:
                k_val = k_series.iloc[-1]

                if k_val < 20:
                    buy_score += 2
                    stoch_signal = "BUY"
                elif k_val > 80:
                    sell_score += 2
                    stoch_signal = "SELL"
                else:
                    stoch_signal = "NEUTRAL"
        except Exception as e:
            logger.warning(f"[Analyzer] Stochastic calculation error: {e}")

        try:
            # ──────────────────────────────────────────────────────
            # 5. EMA Crossover (EMA 21 vs EMA 50)
            # ──────────────────────────────────────────────────────
            ema21_indicator = EMAIndicator(close=df["close"], window=21)
            ema50_indicator = EMAIndicator(close=df["close"], window=50)
            ema21_series = ema21_indicator.ema_indicator()
            ema50_series = ema50_indicator.ema_indicator()

            if (
                ema21_series is not None
                and ema50_series is not None
                and len(ema21_series.dropna()) > 0
                and len(ema50_series.dropna()) > 0
            ):
                ema21_val = ema21_series.iloc[-1]
                ema50_val = ema50_series.iloc[-1]

                if current_price > ema21_val and ema21_val > ema50_val:
                    buy_score += 1
                    ema_signal = "BUY"
                elif current_price < ema21_val and ema21_val < ema50_val:
                    sell_score += 1
                    ema_signal = "SELL"
                else:
                    ema_signal = "NEUTRAL"
        except Exception as e:
            logger.warning(f"[Analyzer] EMA calculation error: {e}")

        try:
            # ──────────────────────────────────────────────────────
            # 6. ADX (14) — Trend Strength Multiplier
            # ──────────────────────────────────────────────────────
            adx_indicator = ADXIndicator(
                high=df["high"], low=df["low"], close=df["close"], window=14
            )
            adx_series = adx_indicator.adx()

            if adx_series is not None and len(adx_series.dropna()) > 0:
                adx_val = adx_series.iloc[-1]
                adx_strong = adx_val > 25  # Strong trend if ADX > 25
        except Exception as e:
            logger.warning(f"[Analyzer] ADX calculation error: {e}")

        try:
            # ──────────────────────────────────────────────────────
            # 7. Candlestick Patterns (manual detection on last 3 candles)
            # ──────────────────────────────────────────────────────
            pattern_name, pattern_signal = self._detect_patterns(df)
            if pattern_signal == "BUY":
                buy_score += 2
            elif pattern_signal == "SELL":
                sell_score += 2
        except Exception as e:
            logger.warning(f"[Analyzer] Pattern detection error: {e}")

        try:
            # ──────────────────────────────────────────────────────
            # 8. Volume Filter
            # ──────────────────────────────────────────────────────
            if len(df) >= 20 and "volume" in df.columns:
                avg_volume = df["volume"].iloc[-20:].mean()
                curr_volume = df["volume"].iloc[-1]
                vol_ratio = curr_volume / avg_volume if avg_volume > 0 else 1.0

                if vol_ratio >= 1.5:
                    vol_signal = "CONFIRM"
                    # Add 1 pt to whichever side is currently winning
                    if buy_score > sell_score:
                        buy_score += 1
                    else:
                        sell_score += 1
        except Exception as e:
            logger.warning(f"[Analyzer] Volume calculation error: {e}")

        # ──────────────────────────────────────────────────────
        # Final Score Calculation
        # ──────────────────────────────────────────────────────
        dominant = "BUY" if buy_score >= sell_score else "SELL"
        dominant_score = max(buy_score, sell_score)

        # ADX boost: if strong trend, +10% to confidence
        base_confidence = (dominant_score / MAX_SCORE) * 100
        if adx_strong:
            confidence = min(base_confidence * 1.1, 95.0)
        else:
            confidence = min(base_confidence, 95.0)

        return {
            "direction": dominant,
            "confidence": round(confidence, 1),
            "buy_score": buy_score,
            "sell_score": sell_score,
            "current_price": current_price,
            "indicators": {
                "rsi": {"value": round(rsi_val, 2), "signal": rsi_signal},
                "macd": {"value": round(macd_line_val, 5), "signal": macd_signal_name},
                "bb": {
                    "upper": round(bb_upper, 5),
                    "lower": round(bb_lower, 5),
                    "signal": bb_signal,
                },
                "stoch": {"k": round(k_val, 2), "signal": stoch_signal},
                "ema": {
                    "ema21": round(ema21_val, 5),
                    "ema50": round(ema50_val, 5),
                    "signal": ema_signal,
                },
                "adx": {"value": round(adx_val, 2), "strong": adx_strong},
                "pattern": {"name": pattern_name, "signal": pattern_signal},
                "volume": {"ratio": round(vol_ratio, 2), "signal": vol_signal},
            },
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _detect_patterns(self, df: pd.DataFrame) -> tuple[str, str]:
        """
        Detect candlestick patterns on the last 3 candles.

        Returns:
            Tuple of (pattern_name, signal) where signal is 'BUY', 'SELL', or 'NEUTRAL'
        """
        if len(df) < 3:
            return "None", "NEUTRAL"

        prev2 = df.iloc[-3]
        prev = df.iloc[-2]
        curr = df.iloc[-1]

        curr_open = curr["open"]
        curr_close = curr["close"]
        curr_high = curr["high"]
        curr_low = curr["low"]
        curr_body = abs(curr_close - curr_open)
        curr_upper_wick = curr_high - max(curr_open, curr_close)
        curr_lower_wick = min(curr_open, curr_close) - curr_low

        prev_open = prev["open"]
        prev_close = prev["close"]
        prev_body = abs(prev_close - prev_open)

        prev2_open = prev2["open"]
        prev2_close = prev2["close"]
        prev2_body = abs(prev2_close - prev2_open)

        curr_bullish = curr_close > curr_open
        curr_bearish = curr_close < curr_open
        prev_bullish = prev_close > prev_open
        prev_bearish = prev_close < prev_open
        prev2_bullish = prev2_close > prev2_open
        prev2_bearish = prev2_close < prev2_open

        # Avoid division by zero
        safe_body = max(curr_body, 0.00001)

        # ── Bullish Patterns ──────────────────────────────────

        # Bullish Engulfing
        if prev_bearish and curr_bullish and curr_body > prev_body:
            return "Bullish Engulfing", "BUY"

        # Hammer: lower wick > 2× body, small/no upper wick, body at top
        if (
            curr_lower_wick > 2 * safe_body
            and curr_upper_wick < safe_body * 0.5
            and curr_body > 0
        ):
            return "Hammer", "BUY"

        # Morning Star: bearish → doji/small → bullish (3-candle)
        prev_avg_body = (prev2_body + curr_body) / 2 if (prev2_body + curr_body) > 0 else 1
        if (
            prev2_bearish
            and prev_body < prev_avg_body * 0.3
            and curr_bullish
            and curr_body > prev2_body * 0.5
        ):
            return "Morning Star", "BUY"

        # Bullish Pin Bar: lower wick > 3× body, closes near high
        if curr_lower_wick > 3 * safe_body and curr_upper_wick < safe_body * 0.3:
            return "Bullish Pin Bar", "BUY"

        # ── Bearish Patterns ──────────────────────────────────

        # Bearish Engulfing
        if prev_bullish and curr_bearish and curr_body > prev_body:
            return "Bearish Engulfing", "SELL"

        # Shooting Star: upper wick > 2× body, small/no lower wick, body at bottom
        if (
            curr_upper_wick > 2 * safe_body
            and curr_lower_wick < safe_body * 0.5
            and curr_body > 0
        ):
            return "Shooting Star", "SELL"

        # Evening Star: bullish → doji/small → bearish (3-candle)
        if (
            prev2_bullish
            and prev_body < prev_avg_body * 0.3
            and curr_bearish
            and curr_body > prev2_body * 0.5
        ):
            return "Evening Star", "SELL"

        # Bearish Pin Bar: upper wick > 3× body, closes near low
        if curr_upper_wick > 3 * safe_body and curr_lower_wick < safe_body * 0.3:
            return "Bearish Pin Bar", "SELL"

        return "None", "NEUTRAL"
