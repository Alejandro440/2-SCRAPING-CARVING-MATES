"""Indicadores técnicos clásicos sobre series de precios (pandas)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    """RSI de Wilder."""
    delta = s.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_up = up.ewm(alpha=1 / n, adjust=False).mean()
    avg_down = down.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_up / avg_down.replace(0, np.nan)
    out = 100 - 100 / (1 + rs)
    return out.fillna(50)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = ema(s, fast) - ema(s, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0):
    mid = sma(s, n)
    sd = s.rolling(n).std()
    upper, lower = mid + k * sd, mid - k * sd
    pct_b = (s - lower) / (upper - lower)
    return mid, upper, lower, pct_b


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def drawdown(s: pd.Series) -> pd.Series:
    """Caída porcentual (negativa) respecto al máximo histórico acumulado."""
    return s / s.cummax() - 1


def zscore(s: pd.Series, n: int = 60) -> pd.Series:
    m = s.rolling(n).mean()
    sd = s.rolling(n).std()
    return (s - m) / sd


def pct_rank(s: pd.Series, window: int) -> pd.Series:
    """Percentil (0-1) del último valor dentro de la ventana."""
    return s.rolling(window).apply(lambda x: (x <= x[-1]).mean(), raw=True)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Añade todas las columnas de indicadores usadas por señales y backtests."""
    out = df.copy()
    c = out["close"]
    out["sma20"] = sma(c, 20)
    out["sma50"] = sma(c, 50)
    out["sma200"] = sma(c, 200)
    out["rsi14"] = rsi(c, 14)
    out["macd"], out["macd_signal"], out["macd_hist"] = macd(c)
    out["bb_mid"], out["bb_up"], out["bb_low"], out["bb_pctb"] = bollinger(c)
    out["atr14"] = atr(out)
    out["drawdown"] = drawdown(c)
    out["z60"] = zscore(c, 60)
    out["ret_1d"] = c.pct_change()
    out["vol20"] = out["ret_1d"].rolling(20).std() * np.sqrt(252)
    return out
