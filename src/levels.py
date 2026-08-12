"""Niveles de entrada ("levels to watch") y probabilidades de alcanzarlos.

Dos preguntas que responde cada día:

  1. ¿A qué precio se dispararía la nota de entrada? Se recalcula la nota
     técnica suponiendo que mañana el precio cae hasta P (manteniendo el
     VIX de hoy) y se busca a qué niveles cruzaría los umbrales 65 y 80.
  2. ¿Qué probabilidad histórica hay de ver una caída de x% en las
     próximas 2/4/13 semanas? Frecuencia empírica sobre todo el histórico
     del índice (proxy largo en EUR).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .indicators import enrich
from .signals import WEIGHTS, component_scores


def score_if_price(df_raw: pd.DataFrame, price: float, vix_score: float) -> float:
    """Nota técnica si mañana el cierre fuese `price` (VIX congelado en hoy)."""
    close = df_raw["close"]
    synth = df_raw.iloc[[-1]].copy()
    synth.index = [df_raw.index[-1] + pd.Timedelta(days=1)]
    for col in ("open", "high", "low", "close", "adjclose"):
        if col in synth:
            synth[col] = price
    ext = pd.concat([df_raw, synth])
    # basta la cola para SMA200/z60/bandas; el drawdown usa el máximo global
    tail = enrich(ext.tail(420))
    tail.loc[tail.index[-1], "drawdown"] = price / close.cummax().iloc[-1] - 1
    comps = component_scores(tail).iloc[-1]
    comps["vix"] = vix_score
    return float(sum(comps[k] * w for k, w in WEIGHTS.items()))


def find_trigger_levels(df_raw: pd.DataFrame, vix_score: float,
                        thresholds: tuple[float, ...] = (65.0, 80.0),
                        max_drop: float = 0.30, step: float = 0.005) -> dict[float, dict]:
    """Primer precio (escaneando caídas crecientes) donde la nota cruza cada umbral."""
    last = float(df_raw["close"].iloc[-1])
    out: dict[float, dict] = {}
    pending = list(thresholds)
    drop = 0.0
    while pending and drop <= max_drop:
        price = last * (1 - drop)
        s = score_if_price(df_raw, price, vix_score)
        for t in list(pending):
            if s >= t:
                out[t] = {"price": price, "drop_pct": drop * 100, "score": s}
                pending.remove(t)
        drop += step
    return out


def dip_probabilities(close: pd.Series, drops=(0.01, 0.02, 0.03, 0.05, 0.08, 0.10),
                      horizons=((10, "2 semanas"), (21, "1 mes"), (63, "3 meses"))) -> pd.DataFrame:
    """P(mínimo de las próximas h sesiones ≤ precio_hoy·(1−x)), frecuencia histórica."""
    c = close.dropna()
    rows = []
    for h, label in horizons:
        fwd_min = c[::-1].rolling(h).min()[::-1].shift(-1)  # mínimo de las h sesiones siguientes
        ratio = (fwd_min / c).dropna()
        rows.append({"horizonte": label, **{f"≥{int(x*100)}%": f"{(ratio <= 1 - x).mean()*100:.0f}%" for x in drops}})
    return pd.DataFrame(rows)
