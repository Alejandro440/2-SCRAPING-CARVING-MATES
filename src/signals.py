"""Modelo de puntuación de entrada (0-100) al estilo de un desk sistemático.

La puntuación combina seis componentes de reversión a la media y régimen de
riesgo. 50 ≈ día "normal"; cuanto más alto, mejor punto de entrada relativo.

Componentes (todos normalizados a 0-100, más alto = más barato/mejor):
  - drawdown     caída desde máximo histórico (0% -> 0 pts, -15% o más -> 100)
  - rsi          RSI(14): 70 -> 0 pts, 30 -> 100 pts
  - sma200_gap   distancia a la SMA200: +10% -> 0 pts, -5% -> 100 pts
  - bollinger    %B(20,2): banda superior -> 0, banda inferior -> 100
  - zscore       z-score 60d: +2σ -> 0, -2σ -> 100
  - vix          percentil 5 años del VIX (miedo alto = oportunidad)

El régimen de tendencia (precio vs SMA200) no entra en la nota, pero se
reporta: en tendencia alcista fuerte esperar caídas tiene coste de
oportunidad, y el backtest lo cuantifica.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

WEIGHTS = {
    "drawdown": 0.20,
    "rsi": 0.20,
    "sma200_gap": 0.15,
    "bollinger": 0.15,
    "zscore": 0.15,
    "vix": 0.15,
}


def _clip01(x):
    return np.clip(x, 0.0, 1.0)


def component_scores(df: pd.DataFrame, vix_pct_rank: pd.Series | None = None) -> pd.DataFrame:
    """Devuelve un DataFrame con cada componente 0-100 alineado al índice de df."""
    s = pd.DataFrame(index=df.index)
    dd = -df["drawdown"]  # positivo
    s["drawdown"] = _clip01(dd / 0.15) * 100 + 0.0  # +0.0 evita el "-0" al formatear
    s["rsi"] = _clip01((70 - df["rsi14"]) / 40) * 100
    gap = df["close"] / df["sma200"] - 1
    s["sma200_gap"] = _clip01((0.10 - gap) / 0.15) * 100
    s["bollinger"] = _clip01(1 - df["bb_pctb"]) * 100
    s["zscore"] = _clip01((2 - df["z60"]) / 4) * 100
    if vix_pct_rank is not None:
        s["vix"] = (vix_pct_rank.reindex(s.index).ffill() * 100).fillna(50)
    else:
        s["vix"] = 50.0
    return s


def entry_score(df: pd.DataFrame, vix_pct_rank: pd.Series | None = None) -> pd.Series:
    comps = component_scores(df, vix_pct_rank)
    score = sum(comps[k] * w for k, w in WEIGHTS.items())
    return score.rename("entry_score")


def regime(df: pd.DataFrame) -> str:
    last = df.iloc[-1]
    if pd.isna(last["sma200"]):
        return "indeterminado"
    if last["close"] >= last["sma200"]:
        return "alcista" if last["sma50"] >= last["sma200"] else "alcista débil"
    return "bajista" if last["sma50"] < last["sma200"] else "corrección en tendencia alcista"


def recommendation(score: float, days_since_entry: int | None, cfg: dict) -> str:
    """Texto de decisión para la próxima entrada quincenal."""
    buy_t = cfg["dca"]["score_buy_threshold"]
    strong_t = cfg["dca"]["score_strong_threshold"]
    interval = cfg["dca"]["interval_days"]

    if days_since_entry is not None and days_since_entry >= interval:
        return (
            f"COMPRA HOY: han pasado {days_since_entry} días desde tu última entrada "
            f"(ventana de {interval}). La regla es no dejar pasar la ventana aunque la nota sea baja."
        )
    if score >= strong_t:
        return (
            f"COMPRA HOY (señal fuerte, nota {score:.0f} ≥ {strong_t}). Punto de entrada "
            "estadísticamente muy favorable; considera adelantar la entrada quincenal."
        )
    if score >= buy_t:
        return (
            f"COMPRA (nota {score:.0f} ≥ {buy_t}). Si estás dentro de tu ventana quincenal, "
            "hoy es un día razonable para ejecutar la entrada."
        )
    return (
        f"DÍA NORMAL/CARO según el modelo (nota {score:.0f} < {buy_t}). Ojo: el backtest muestra "
        "que *retrasar* la aportación esperando un día mejor no compensa en media — si hoy toca "
        "aportar según tu calendario, aporta. La nota sirve sobre todo para *adelantar* la entrada "
        f"cuando aparece una señal fuerte (≥ {strong_t}), no para saltarse compras."
    )
