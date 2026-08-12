"""Canal de análisis fundamental, al estilo de los modelos de asignación
de los bancos (JPM/GS multi-señal): valoración + régimen de riesgo.

Componentes de la nota fundamental (0-100, más alto = entrada más atractiva):

  1. Prima de riesgo (ERP proxy, "Fed model"): earnings yield del índice
     mundial (vía P/E del ETF VT) menos el tipo a 10 años EEUU. Es el
     clásico "equities vs bonds" de los strategist de bancos.
  2. Desviación del canal de tendencia de largo plazo (caro/barato frente
     a su propia deriva histórica), en sigmas.
  3. Estructura temporal del VIX: ratio VIX/VIX3M. En pánico la curva se
     invierte (backwardation, ratio > 1) — históricamente uno de los
     mejores marcadores de capitulación/entrada.
  4. Estrés de crédito: z-score 120d del ratio HYG/LQD (high yield vs
     investment grade). HY hundiéndose = estrés; para un comprador
     sistemático de largo plazo, estrés = precios rebajados.

La pendiente de la curva de tipos (10a − 3m) se reporta como contexto de
ciclo, sin entrar en la nota (su horizonte es demasiado largo para decidir
la quincena).

La valoración (P/E, P/B, yield) se obtiene del quoteSummary de Yahoo con
el flujo cookie+crumb y se persiste en data/fundamental_history.csv, de
modo que si la fuente falla se usa el último valor conocido.
"""

from __future__ import annotations

import datetime as dt
import os

import numpy as np
import pandas as pd
import requests

from .indicators import pct_rank

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUND_HIST = os.path.join(ROOT, "data", "fundamental_history.csv")

_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

WEIGHTS = {"erp": 0.35, "trend": 0.25, "vix_term": 0.25, "credit": 0.15}


def _clip01(x):
    return float(np.clip(x, 0.0, 1.0))


# ---------------------------------------------------------------- valoración

def fetch_valuation(ticker: str = "VT") -> dict | None:
    """P/E, P/B y yield del fondo vía quoteSummary (cookie + crumb).

    Yahoo devuelve en equityHoldings los ratios a veces como P/E y a veces
    como su inverso (E/P); se normaliza para entregar siempre P/E.
    """
    try:
        s = requests.Session()
        s.headers.update(_UA)
        s.get("https://fc.yahoo.com", timeout=20)
        crumb = s.get("https://query1.finance.yahoo.com/v1/test/getcrumb", timeout=20).text
        if not crumb or "<" in crumb:
            return None
        r = s.get(
            f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{ticker}",
            params={"modules": "summaryDetail,topHoldings", "crumb": crumb},
            timeout=30,
        )
        if r.status_code != 200:
            return None
        res = r.json()["quoteSummary"]["result"][0]
        eq = res.get("topHoldings", {}).get("equityHoldings", {})

        def _ratio(field):
            raw = eq.get(field, {}).get("raw")
            if raw is None or raw <= 0:
                return None
            return 1 / raw if raw < 1 else raw  # normaliza inversos

        pe = _ratio("priceToEarnings")
        pb = _ratio("priceToBook")
        dy = res.get("summaryDetail", {}).get("yield", {}).get("raw")
        if pe is None:
            return None
        return {"pe": pe, "pb": pb, "div_yield": dy}
    except Exception:
        return None


def valuation_with_fallback(ticker: str = "VT") -> tuple[dict | None, str]:
    """Intenta la fuente en vivo; si falla, usa el último valor persistido."""
    val = fetch_valuation(ticker)
    if val is not None:
        _persist_valuation(val)
        return val, "en vivo"
    if os.path.exists(FUND_HIST):
        hist = pd.read_csv(FUND_HIST)
        if len(hist):
            row = hist.iloc[-1]
            return (
                {"pe": row["pe"], "pb": row.get("pb"), "div_yield": row.get("div_yield")},
                f"último conocido ({row['date']})",
            )
    return None, "no disponible"


def _persist_valuation(val: dict):
    row = {
        "date": dt.date.today().isoformat(),
        "pe": round(val["pe"], 2),
        "pb": round(val["pb"], 2) if val.get("pb") else "",
        "div_yield": round(val["div_yield"], 4) if val.get("div_yield") else "",
    }
    os.makedirs(os.path.dirname(FUND_HIST), exist_ok=True)
    if os.path.exists(FUND_HIST):
        hist = pd.read_csv(FUND_HIST, dtype={"date": str})
        hist = hist[hist["date"] != row["date"]]
        hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True)
    else:
        hist = pd.DataFrame([row])
    hist.to_csv(FUND_HIST, index=False)


# ---------------------------------------------------------- señales de serie

def vix_term_structure(vix: pd.DataFrame, vix3m: pd.DataFrame) -> pd.Series:
    """Ratio VIX/VIX3M (>1 = backwardation = pánico)."""
    ratio = vix["close"] / vix3m["close"].reindex(vix.index).ffill()
    return ratio.dropna().rename("vix_ts")


def credit_stress_z(hyg: pd.DataFrame, lqd: pd.DataFrame, window: int = 120) -> pd.Series:
    """Z-score del ratio HYG/LQD: muy negativo = estrés de crédito."""
    ratio = hyg["close"] / lqd["close"].reindex(hyg.index).ffill()
    z = (ratio - ratio.rolling(window).mean()) / ratio.rolling(window).std()
    return z.dropna().rename("credit_z")


def curve_slope(tnx: pd.DataFrame, irx: pd.DataFrame) -> pd.Series:
    """Pendiente 10 años − 3 meses (puntos porcentuales)."""
    slope = tnx["close"] - irx["close"].reindex(tnx.index).ffill()
    return slope.dropna().rename("curve_slope")


# ------------------------------------------------------------------- la nota

def fundamental_score(valuation: dict | None, us10y_pct: float, trend_sigma: float,
                      vix_ts_now: float, credit_z_now: float) -> dict:
    """Nota fundamental 0-100 y desglose por componentes."""
    comps: dict[str, float | None] = {}

    erp = None
    if valuation and valuation.get("pe"):
        ey = 100.0 / valuation["pe"]  # earnings yield en %
        erp = ey - us10y_pct
        # ERP -2% -> 0 pts · +3% -> 100 pts
        comps["erp"] = _clip01((erp + 2.0) / 5.0) * 100
    else:
        comps["erp"] = None

    # desviación del canal: +2σ (muy caro) -> 0 · -2σ (muy barato) -> 100
    comps["trend"] = _clip01((2.0 - trend_sigma) / 4.0) * 100
    # VIX/VIX3M: 0.85 (contango profundo, complacencia) -> 0 · 1.05+ -> 100
    comps["vix_term"] = _clip01((vix_ts_now - 0.85) / 0.20) * 100
    # crédito: z +2 (euforia) -> 0 · z -2 (estrés) -> 100
    comps["credit"] = _clip01((2.0 - credit_z_now) / 4.0) * 100

    total_w = sum(w for k, w in WEIGHTS.items() if comps[k] is not None)
    score = sum(comps[k] * w for k, w in WEIGHTS.items() if comps[k] is not None) / total_w

    return {
        "score": float(score),
        "components": comps,
        "erp_pct": erp,
        "earnings_yield_pct": (100.0 / valuation["pe"]) if valuation and valuation.get("pe") else None,
    }
