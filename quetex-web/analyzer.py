"""
analyzer.py — 12-indicator weighted technical analysis engine.
Indicators: RSI, MACD, Bollinger, Stochastic, EMA(21/50/200),
            ADX, Williams%R, CCI, Parabolic SAR, ATR, 16 Candle Patterns, Volume.

Uses `ta` library (Technical Analysis) for all calculations.
Weighted scoring: each indicator has a weight (total=100).
Returns confidence % based on weighted consensus.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np
import ta
import config as C

logger = logging.getLogger(__name__)


@dataclass
class IndResult:
    name:   str
    signal: str     # BUY | SELL | NEUTRAL
    weight: int     # from config WEIGHTS
    value:  float = 0.0
    label:  str = ""    # human-readable label


@dataclass
class AnalysisResult:
    asset:         str
    timeframe:     str
    direction:     str      # BUY | SELL
    confidence:    float    # 0-100
    buy_pct:       float
    sell_pct:      float
    price:         float
    adx:           float
    atr_pct:       float
    low_vol:       bool
    pattern:       str
    indicators:    list = field(default_factory=list)
    confirming:    list = field(default_factory=list)
    opposing:      list = field(default_factory=list)
    timestamp:     str = ""
    error:         Optional[str] = None


class TechnicalAnalyzer:

    def analyze(self, df: pd.DataFrame, asset: str,
                timeframe: str) -> Optional[AnalysisResult]:
        """
        Run 12-indicator analysis. Returns AnalysisResult or None.
        """
        if df is None or len(df) < 60:
            logger.debug("Not enough data for %s/%s (%d candles)",
                         asset, timeframe, len(df) if df is not None else 0)
            return None

        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        try:
            df = df.copy()
            df.columns = [c.lower() for c in df.columns]
            price = float(df["close"].iloc[-1])
            if price <= 0:
                return None

            # ── Calculate all indicators ──────────────────────
            self._calc_all(df)

            # ── ATR volatility check ──────────────────────────
            atr_col = "atr"
            atr_val = float(df[atr_col].iloc[-1]) if atr_col in df.columns and not df[atr_col].isna().all() else 0.0
            atr_pct = (atr_val / price) if price > 0 else 0.0
            low_vol = atr_pct < C.MIN_ATR_PCT

            # ── ADX ───────────────────────────────────────────
            adx_col = "adx"
            adx_val = float(df[adx_col].iloc[-1]) if adx_col in df.columns and not df[adx_col].isna().all() else 20.0

            # ── Run all indicator checks ──────────────────────
            ind_results = [
                self._rsi(df),
                self._macd(df),
                self._bollinger(df, price),
                self._stochastic(df),
                self._ema(df, price),
                self._williams_r(df),
                self._cci(df),
                self._psar(df, price),
                self._pattern(df),
                self._volume(df),
            ]

            # ── Weighted score ────────────────────────────────
            total_w = sum(r.weight for r in ind_results if r.signal != "NEUTRAL")
            buy_w   = sum(r.weight for r in ind_results if r.signal == "BUY")
            sell_w  = sum(r.weight for r in ind_results if r.signal == "SELL")

            # Normalize to max possible (100)
            max_w = sum(C.WEIGHTS.values())
            buy_pct  = (buy_w  / max_w * 100) if max_w > 0 else 0
            sell_pct = (sell_w / max_w * 100) if max_w > 0 else 0

            # ── ADX multiplier ────────────────────────────────
            if adx_val < C.ADX_WEAK:
                mult = 0.82      # weak trend → reduce
            elif adx_val < C.ADX_NORMAL:
                mult = 1.00
            elif adx_val < C.ADX_STRONG:
                mult = 1.12      # strong trend → boost
            else:
                mult = 1.20      # very strong

            # ── Direction + confidence ────────────────────────
            if buy_pct > sell_pct:
                direction  = "BUY"
                confidence = min(buy_pct * mult, 97.0)
            else:
                direction  = "SELL"
                confidence = min(sell_pct * mult, 97.0)

            # ── Confirming / opposing ─────────────────────────
            confirming = [r.label for r in ind_results
                          if r.signal == direction and r.label]
            opposing   = [r.label for r in ind_results
                          if r.signal != direction and r.signal != "NEUTRAL" and r.label]

            # ── Pattern name ──────────────────────────────────
            pat = next((r for r in ind_results if r.name == "pattern"), None)
            pat_name = pat.label if pat and pat.signal != "NEUTRAL" else "—"

            return AnalysisResult(
                asset=asset, timeframe=timeframe,
                direction=direction,
                confidence=round(confidence, 2),
                buy_pct=round(buy_pct, 2),
                sell_pct=round(sell_pct, 2),
                price=price,
                adx=round(adx_val, 2),
                atr_pct=round(atr_pct * 100, 4),
                low_vol=low_vol,
                pattern=pat_name,
                indicators=ind_results,
                confirming=confirming,
                opposing=opposing,
                timestamp=ts,
            )

        except Exception as exc:
            logger.error("analyze(%s/%s): %s", asset, timeframe, exc, exc_info=True)
            return None

    @staticmethod
    def _calc_all(df: pd.DataFrame):
        """Add all indicator columns to df in-place using `ta` library."""
        high = df["high"]
        low = df["low"]
        close = df["close"]
        volume = df.get("volume", pd.Series(0, index=df.index))

        # RSI
        try:
            df["rsi"] = ta.momentum.RSIIndicator(close=close, window=C.RSI_LEN).rsi()
        except: pass

        # MACD
        try:
            macd = ta.trend.MACD(close=close, window_slow=C.MACD_S, window_fast=C.MACD_F, window_sign=C.MACD_G)
            df["macd"] = macd.macd()
            df["macd_signal"] = macd.macd_signal()
            df["macd_hist"] = macd.macd_diff()
        except: pass

        # Bollinger Bands
        try:
            bb = ta.volatility.BollingerBands(close=close, window=C.BB_LEN, window_dev=C.BB_STD)
            df["bb_upper"] = bb.bollinger_hband()
            df["bb_lower"] = bb.bollinger_lband()
            df["bb_mid"] = bb.bollinger_mavg()
        except: pass

        # Stochastic
        try:
            stoch = ta.momentum.StochasticOscillator(high=high, low=low, close=close, window=C.STOCH_K, smooth_window=C.STOCH_D)
            df["stoch_k"] = stoch.stoch()
            df["stoch_d"] = stoch.stoch_signal()
        except: pass

        # EMA
        try:
            df["ema_fast"] = ta.trend.EMAIndicator(close=close, window=C.EMA_FAST).ema_indicator()
        except: pass
        try:
            df["ema_med"] = ta.trend.EMAIndicator(close=close, window=C.EMA_MED).ema_indicator()
        except: pass
        try:
            df["ema_slow"] = ta.trend.EMAIndicator(close=close, window=C.EMA_SLOW).ema_indicator()
        except: pass

        # ADX
        try:
            adx_ind = ta.trend.ADXIndicator(high=high, low=low, close=close, window=C.ADX_LEN)
            df["adx"] = adx_ind.adx()
        except: pass

        # Williams %R
        try:
            df["willr"] = ta.momentum.WilliamsRIndicator(high=high, low=low, close=close, lbp=C.WILLR_LEN).williams_r()
        except: pass

        # CCI
        try:
            df["cci"] = ta.trend.CCIIndicator(high=high, low=low, close=close, window=C.CCI_LEN).cci()
        except: pass

        # ATR
        try:
            df["atr"] = ta.volatility.AverageTrueRange(high=high, low=low, close=close, window=C.ATR_LEN).average_true_range()
        except: pass

        # Parabolic SAR
        try:
            psar = ta.trend.PSARIndicator(high=high, low=low, close=close)
            df["psar_up"] = psar.psar_up()      # NaN when bearish
            df["psar_down"] = psar.psar_down()   # NaN when bullish
        except: pass

    # ── Individual indicator evaluators ──────────────────────────────

    def _rsi(self, df):
        w = C.WEIGHTS["rsi"]
        col = "rsi"
        if col not in df.columns or df[col].isna().all():
            return IndResult("rsi", "NEUTRAL", 0)
        v = float(df[col].iloc[-1])
        if v < 30:
            return IndResult("rsi", "BUY", w, v, f"RSI {v:.1f} — Oversold ↑")
        if v > 70:
            return IndResult("rsi", "SELL", w, v, f"RSI {v:.1f} — Overbought ↓")
        if v < 40:
            return IndResult("rsi", "BUY", w//2, v, f"RSI {v:.1f} — Near Oversold")
        if v > 60:
            return IndResult("rsi", "SELL", w//2, v, f"RSI {v:.1f} — Near Overbought")
        return IndResult("rsi", "NEUTRAL", 0, v)

    def _macd(self, df):
        w = C.WEIGHTS["macd"]
        if "macd" not in df.columns or len(df["macd"].dropna()) < 2:
            return IndResult("macd", "NEUTRAL", 0)
        m = float(df["macd"].iloc[-1])
        s = float(df["macd_signal"].iloc[-1])
        mp = float(df["macd"].iloc[-2])
        sp = float(df["macd_signal"].iloc[-2])
        h = float(df["macd_hist"].iloc[-1])
        hp = float(df["macd_hist"].iloc[-2])
        if mp < sp and m > s:
            return IndResult("macd", "BUY", w, m, "MACD — Bullish Crossover ✦")
        if mp > sp and m < s:
            return IndResult("macd", "SELL", w, m, "MACD — Bearish Crossover ✦")
        if h > 0 and h > hp > 0:
            return IndResult("macd", "BUY", w//2, m, "MACD Histogram Rising")
        if h < 0 and h < hp < 0:
            return IndResult("macd", "SELL", w//2, m, "MACD Histogram Falling")
        return IndResult("macd", "NEUTRAL", 0, m)

    def _bollinger(self, df, price):
        w = C.WEIGHTS["bollinger"]
        if "bb_upper" not in df.columns:
            return IndResult("bollinger", "NEUTRAL", 0)
        u = float(df["bb_upper"].iloc[-1])
        l = float(df["bb_lower"].iloc[-1])
        mid = float(df["bb_mid"].iloc[-1])
        bw = u - l
        if price <= l:
            return IndResult("bollinger", "BUY", w, price, f"BB — Below Lower Band ({l:.5f})")
        if price >= u:
            return IndResult("bollinger", "SELL", w, price, f"BB — Above Upper Band ({u:.5f})")
        if price < mid and bw > 0 and (mid-price)/bw > 0.25:
            return IndResult("bollinger", "BUY", w//2, price, "BB — Near Lower Band")
        if price > mid and bw > 0 and (price-mid)/bw > 0.25:
            return IndResult("bollinger", "SELL", w//2, price, "BB — Near Upper Band")
        return IndResult("bollinger", "NEUTRAL", 0, price)

    def _stochastic(self, df):
        w = C.WEIGHTS["stochastic"]
        if "stoch_k" not in df.columns or df["stoch_k"].isna().all():
            return IndResult("stochastic", "NEUTRAL", 0)
        k = float(df["stoch_k"].iloc[-1])
        kp = float(df["stoch_k"].iloc[-2])
        if k < 20 and k > kp:
            return IndResult("stochastic", "BUY", w, k, f"Stoch K={k:.1f} — Oversold Turning Up ↑")
        if k > 80 and k < kp:
            return IndResult("stochastic", "SELL", w, k, f"Stoch K={k:.1f} — Overbought Turning Down ↓")
        if k < 20:
            return IndResult("stochastic", "BUY", w//2, k, f"Stoch K={k:.1f} — Oversold")
        if k > 80:
            return IndResult("stochastic", "SELL", w//2, k, f"Stoch K={k:.1f} — Overbought")
        return IndResult("stochastic", "NEUTRAL", 0, k)

    def _ema(self, df, price):
        w = C.WEIGHTS["ema"]
        if "ema_fast" not in df.columns or "ema_med" not in df.columns:
            return IndResult("ema", "NEUTRAL", 0)
        e21 = float(df["ema_fast"].iloc[-1])
        e50 = float(df["ema_med"].iloc[-1])
        e200 = float(df["ema_slow"].iloc[-1]) if "ema_slow" in df.columns and not df["ema_slow"].isna().all() else e50
        if price > e21 > e50 > e200:
            return IndResult("ema", "BUY", w, e21, "EMA21 > 50 > 200 — Full Bullish Alignment")
        if price < e21 < e50 < e200:
            return IndResult("ema", "SELL", w, e21, "EMA21 < 50 < 200 — Full Bearish Alignment")
        if price > e21 and e21 > e50:
            return IndResult("ema", "BUY", int(w*0.7), e21, "EMA21 > EMA50 — Bullish")
        if price < e21 and e21 < e50:
            return IndResult("ema", "SELL", int(w*0.7), e21, "EMA21 < EMA50 — Bearish")
        return IndResult("ema", "NEUTRAL", 0, e21)

    def _williams_r(self, df):
        w = C.WEIGHTS["williams_r"]
        if "willr" not in df.columns or df["willr"].isna().all():
            return IndResult("williams_r", "NEUTRAL", 0)
        v = float(df["willr"].iloc[-1])
        if v < -80:
            return IndResult("williams_r", "BUY", w, v, f"Williams %R {v:.1f} — Oversold")
        if v > -20:
            return IndResult("williams_r", "SELL", w, v, f"Williams %R {v:.1f} — Overbought")
        return IndResult("williams_r", "NEUTRAL", 0, v)

    def _cci(self, df):
        w = C.WEIGHTS["cci"]
        if "cci" not in df.columns or df["cci"].isna().all():
            return IndResult("cci", "NEUTRAL", 0)
        v = float(df["cci"].iloc[-1])
        if v < -100:
            return IndResult("cci", "BUY", w, v, f"CCI {v:.0f} — Oversold")
        if v > 100:
            return IndResult("cci", "SELL", w, v, f"CCI {v:.0f} — Overbought")
        return IndResult("cci", "NEUTRAL", 0, v)

    def _psar(self, df, price):
        w = C.WEIGHTS["psar"]
        if "psar_up" not in df.columns:
            return IndResult("psar", "NEUTRAL", 0)
        pup = df["psar_up"].iloc[-1]
        pdn = df["psar_down"].iloc[-1]
        if pd.notna(pup) and price > float(pup):
            return IndResult("psar", "BUY", w, float(pup), "PSAR Bullish (dots below price)")
        if pd.notna(pdn) and price < float(pdn):
            return IndResult("psar", "SELL", w, float(pdn), "PSAR Bearish (dots above price)")
        # If psar_up is not NaN, it's bullish; if psar_down is not NaN, it's bearish
        if pd.notna(pup):
            return IndResult("psar", "BUY", w, float(pup), "PSAR Bullish (dots below price)")
        if pd.notna(pdn):
            return IndResult("psar", "SELL", w, float(pdn), "PSAR Bearish (dots above price)")
        return IndResult("psar", "NEUTRAL", 0, price)

    def _pattern(self, df) -> IndResult:
        """16 candlestick pattern detector."""
        w = C.WEIGHTS["pattern"]
        if len(df) < 3:
            return IndResult("pattern", "NEUTRAL", 0)

        c0, c1, c2 = df.iloc[-1], df.iloc[-2], df.iloc[-3]
        o0,h0,l0,cl0 = float(c0.open),float(c0.high),float(c0.low),float(c0.close)
        o1,h1,l1,cl1 = float(c1.open),float(c1.high),float(c1.low),float(c1.close)
        o2,h2,l2,cl2 = float(c2.open),float(c2.high),float(c2.low),float(c2.close)

        b0=abs(cl0-o0); b1=abs(cl1-o1); b2=abs(cl2-o2)
        uw0=h0-max(cl0,o0); lw0=min(cl0,o0)-l0
        sb = max(b0, 1e-8)

        bull0=cl0>o0; bear0=cl0<o0
        bull1=cl1>o1; bear1=cl1<o1
        bull2=cl2>o2; bear2=cl2<o2

        def R(name, sig, wt=None): return IndResult("pattern", sig, wt or w, 0, f"🕯 {name}")

        # ── BULLISH ──────────────────────────────────────────
        if bear1 and bull0 and b0>b1 and cl0>o1 and o0<cl1:
            return R("Bullish Engulfing", "BUY")
        if lw0 > 2*sb and uw0 < sb*0.5:
            return R("Hammer", "BUY")
        if lw0 > 3*sb and cl0 > (h0+l0)/2:
            return R("Bullish Pin Bar", "BUY")
        if bear2 and b1<(b0+b2)*0.3 and bull0 and cl0>(o2+cl2)/2:
            return R("Morning Star", "BUY")
        if bull0 and bull1 and bull2 and cl0>cl1>cl2 and o0>o1>o2:
            return R("Three White Soldiers", "BUY")
        if bull1 and bear0 and o0>cl1 and cl0<o1 and b0<b1:  # harami reversed
            return R("Bullish Harami", "BUY", int(w*0.7))
        if uw0>2*sb and lw0<sb*0.3 and bear1:
            return R("Inverted Hammer", "BUY", int(w*0.8))
        if b0<(h0-l0)*0.1 and lw0>uw0*2 and bear1:
            return R("Dragonfly Doji", "BUY", int(w*0.75))

        # ── BEARISH ──────────────────────────────────────────
        if bull1 and bear0 and b0>b1 and cl0<o1 and o0>cl1:
            return R("Bearish Engulfing", "SELL")
        if uw0 > 2*sb and lw0 < sb*0.5 and bull1:
            return R("Shooting Star", "SELL")
        if uw0 > 3*sb and cl0 < (h0+l0)/2:
            return R("Bearish Pin Bar", "SELL")
        if bull2 and b1<(b0+b2)*0.3 and bear0 and cl0<(o2+cl2)/2:
            return R("Evening Star", "SELL")
        if bear0 and bear1 and bear2 and cl0<cl1<cl2:
            return R("Three Black Crows", "SELL")
        if bear1 and bull0 and o0<cl1 and cl0>o1 and b0<b1:
            return R("Bearish Harami", "SELL", int(w*0.7))
        if b0<(h0-l0)*0.1 and uw0>lw0*2 and bull1:
            return R("Gravestone Doji", "SELL", int(w*0.75))
        if bull1 and bear0 and o0>h1 and cl0<(o1+cl1)/2:
            return R("Dark Cloud Cover", "SELL", int(w*0.9))

        return IndResult("pattern", "NEUTRAL", 0, 0, "")

    def _volume(self, df) -> IndResult:
        w = C.WEIGHTS["volume"]
        if "volume" not in df.columns or df["volume"].sum() == 0:
            return IndResult("volume", "NEUTRAL", 0)
        avg = float(df["volume"].iloc[-20:].mean())
        cur = float(df["volume"].iloc[-1])
        ratio = cur/avg if avg > 0 else 1.0
        if ratio >= 1.5:
            sig = "BUY" if df["close"].iloc[-1] > df["open"].iloc[-1] else "SELL"
            return IndResult("volume", sig, w, ratio, f"Volume Spike {ratio:.1f}× avg")
        return IndResult("volume", "NEUTRAL", 0, ratio)
