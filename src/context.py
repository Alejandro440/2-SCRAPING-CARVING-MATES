"""Contexto macro y "fundamental" para un ETF de renta variable mundial.

Para un fondo de ~3.900 empresas el análisis fundamental útil es a nivel de
índice y de régimen de mercado, no de una empresa concreta:

  - VIX: nivel y percentil 5 años (régimen de riesgo / miedo).
  - EURUSD: VWCE cotiza en EUR pero el subyacente es mayoritariamente USD;
    un euro fuerte abarata el ETF en EUR y viceversa.
  - Tipos a 10 años EEUU (^TNX): descuento de valoraciones de renta variable.
  - Canal de tendencia log-lineal: CAGR de largo plazo y desviación actual
    del precio respecto a esa tendencia (proxy de caro/barato).
  - Descomposición de la rentabilidad EUR = índice en USD + efecto divisa.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import pct_rank


def vix_context(vix: pd.DataFrame) -> dict:
    close = vix["close"]
    rank5y = pct_rank(close, min(len(close), 5 * 252))
    return {
        "level": float(close.iloc[-1]),
        "pct_rank_5y": float(rank5y.iloc[-1]),
        "series_rank": rank5y,
    }


def fx_context(fx: pd.DataFrame) -> dict:
    c = fx["close"]
    def chg(days):
        if len(c) <= days:
            return np.nan
        return float(c.iloc[-1] / c.iloc[-1 - days] - 1)
    return {"level": float(c.iloc[-1]), "chg_1m": chg(21), "chg_3m": chg(63), "chg_1y": chg(252)}


def rates_context(tnx: pd.DataFrame) -> dict:
    c = tnx["close"]  # Yahoo sirve ^TNX ya en % (p.ej. 4.68)
    level = float(c.iloc[-1])
    chg_3m = float(c.iloc[-1]) - float(c.iloc[-63]) if len(c) > 63 else np.nan
    return {"level_pct": level, "chg_3m_pp": chg_3m}


def trend_channel(close: pd.Series) -> dict:
    """Regresión log-lineal del precio: CAGR implícito y desviación actual."""
    y = np.log(close.dropna().values)
    x = np.arange(len(y))
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    resid = y - fitted
    sd = resid.std()
    cagr = float(np.exp(slope * 252) - 1)
    dev_now = float(resid[-1])
    return {
        "cagr_pct": cagr * 100,
        "deviation_pct": (np.exp(dev_now) - 1) * 100,
        "deviation_sigma": dev_now / sd if sd > 0 else 0.0,
        "fitted": pd.Series(np.exp(fitted), index=close.dropna().index),
        "sigma_pct": (np.exp(sd) - 1) * 100,
    }


def return_decomposition(vwce: pd.DataFrame, vt: pd.DataFrame, fx: pd.DataFrame, days: int = 252) -> dict:
    """Rentabilidad EUR del ETF ≈ rentabilidad USD del índice + efecto EURUSD."""
    def total_ret(df):
        c = df["close"].dropna()
        n = min(days, len(c) - 1)
        return float(c.iloc[-1] / c.iloc[-1 - n] - 1)
    r_eur = total_ret(vwce)
    r_usd = total_ret(vt)
    c = fx["close"].dropna()
    n = min(days, len(c) - 1)
    r_fx = float(c.iloc[-1] / c.iloc[-1 - n] - 1)  # EURUSD arriba = euro fuerte
    return {"ret_eur": r_eur, "ret_usd_proxy": r_usd, "eurusd_chg": r_fx}
