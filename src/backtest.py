"""Backtest de estrategias de entrada para un plan DCA quincenal.

La pregunta que responde: dentro de cada ventana de 14 días, ¿qué regla de
elección del día de compra habría dado mejor precio medio que comprar
siempre el primer día? Incluye un "oráculo" (mejor día posible con
información perfecta) como techo teórico y una regla con acumulación de
efectivo entre ventanas para medir el coste de "esperar la gran caída".
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Result:
    name: str
    invested: float = 0.0
    units: float = 0.0
    buys: list = field(default_factory=list)  # (date, price, amount)

    @property
    def avg_price(self) -> float:
        return self.invested / self.units if self.units else np.nan

    def final_value(self, last_price: float) -> float:
        return self.units * last_price


def _windows(index: pd.DatetimeIndex, interval_days: int = 14):
    """Trocea el índice de días de mercado en ventanas de `interval_days` naturales."""
    out = []
    start = index[0]
    while start <= index[-1]:
        end = start + dt.timedelta(days=interval_days - 1)
        mask = (index >= start) & (index <= end)
        days = index[mask]
        if len(days):
            out.append(days)
        start = end + dt.timedelta(days=1)
    return out


def _buy(res: Result, date, price: float, amount: float):
    res.invested += amount
    res.units += amount / price
    res.buys.append((date, float(price), amount))


def run_window_strategies(df: pd.DataFrame, amount: float = 500.0, interval_days: int = 14,
                          score: pd.Series | None = None, score_threshold: float = 65.0,
                          extra_signals: dict[str, tuple[str, pd.Series]] | None = None) -> dict[str, Result]:
    """Estrategias que compran exactamente una vez por ventana (sin saltarse ninguna).

    `extra_signals`: {clave: (etiqueta, serie booleana)} — regla "primer día
    en que la señal es True, si no último día". Sirve para probar señales
    fundamentales (backwardation del VIX, estrés de crédito…).
    """
    close = df["close"]
    windows = _windows(df.index, interval_days)

    strategies = {
        "primer_dia": Result("Primer día de la ventana (base)"),
        "ultimo_dia": Result("Último día de la ventana"),
        "regla_nota": Result(f"Primera nota ≥ {score_threshold:.0f}, si no último día"),
        "caida_1pct": Result("Primer día con caída ≥1% vs inicio de ventana, si no último día"),
        "caida_2pct": Result("Primer día con caída ≥2% vs inicio de ventana, si no último día"),
        "rsi_35": Result("Primer día con RSI ≤ 35, si no último día"),
        "oraculo": Result("Mejor día posible (información perfecta)"),
        "peor_dia": Result("Peor día posible"),
    }
    extra_signals = extra_signals or {}
    for key, (label, _) in extra_signals.items():
        strategies[key] = Result(label)

    for days in windows:
        w_close = close.loc[days]
        ref = w_close.iloc[0]

        _buy(strategies["primer_dia"], days[0], w_close.iloc[0], amount)
        _buy(strategies["ultimo_dia"], days[-1], w_close.iloc[-1], amount)
        _buy(strategies["oraculo"], w_close.idxmin(), w_close.min(), amount)
        _buy(strategies["peor_dia"], w_close.idxmax(), w_close.max(), amount)

        conds = [
            ("caida_1pct", w_close <= ref * 0.99),
            ("caida_2pct", w_close <= ref * 0.98),
            ("rsi_35", df.loc[days, "rsi14"] <= 35),
        ]
        for key, (_, sig) in extra_signals.items():
            conds.append((key, sig.reindex(days).fillna(False).astype(bool)))
        for key, cond in conds:
            hit = cond[cond]
            d = hit.index[0] if len(hit) else days[-1]
            _buy(strategies[key], d, close.loc[d], amount)

        if score is not None:
            w_score = score.loc[days]
            hit = w_score[w_score >= score_threshold]
            d = hit.index[0] if len(hit) else days[-1]
            _buy(strategies["regla_nota"], d, close.loc[d], amount)

    if score is None:
        strategies.pop("regla_nota")
    return strategies


def run_cash_carry(df: pd.DataFrame, score: pd.Series, amount: float = 500.0, interval_days: int = 14,
                   threshold: float = 70.0, max_carry: int = 3) -> Result:
    """Guarda el efectivo hasta ver nota ≥ threshold; compra forzosa tras
    `max_carry` ventanas sin señal. Mide el coste real de "esperar la caída"."""
    close = df["close"]
    res = Result(f"Acumular efectivo hasta nota ≥ {threshold:.0f} (máx {max_carry} ventanas)")
    cash = 0.0
    windows_waiting = 0
    for days in _windows(df.index, interval_days):
        cash += amount
        w_score = score.loc[days]
        hit = w_score[w_score >= threshold]
        if len(hit):
            d = hit.index[0]
            _buy(res, d, close.loc[d], cash)
            cash, windows_waiting = 0.0, 0
        else:
            windows_waiting += 1
            if windows_waiting >= max_carry:
                d = days[-1]
                _buy(res, d, close.loc[d], cash)
                cash, windows_waiting = 0.0, 0
    if cash > 0:  # efectivo sin invertir al final: cómpralo al último precio para comparar en igualdad
        _buy(res, df.index[-1], close.iloc[-1], cash)
    return res


def summarize(strategies: dict[str, Result], last_price: float) -> pd.DataFrame:
    base = strategies["primer_dia"]
    rows = []
    for key, r in strategies.items():
        rows.append(
            {
                "estrategia": r.name,
                "clave": key,
                "compras": len(r.buys),
                "invertido": round(r.invested, 2),
                "precio_medio": round(r.avg_price, 4),
                "valor_final": round(r.final_value(last_price), 2),
                "mejora_vs_base_bps": round((base.avg_price / r.avg_price - 1) * 1e4, 1),
            }
        )
    out = pd.DataFrame(rows).set_index("clave")
    oracle = strategies.get("oraculo")
    if oracle is not None:
        denom = base.avg_price - oracle.avg_price
        out["captura_oraculo_pct"] = [
            round((base.avg_price - r.avg_price) / denom * 100, 1) if denom > 0 else np.nan
            for r in strategies.values()
        ]
    return out


def monte_carlo_dca(returns: pd.Series, years: int = 5, amount: float = 500.0, interval_days: int = 14,
                    n_paths: int = 2000, block: int = 20, seed: int = 42) -> dict:
    """Bootstrap por bloques de rendimientos diarios; simula el plan DCA a futuro.

    Devuelve percentiles del valor final y la TIR anualizada aproximada.
    """
    rng = np.random.default_rng(seed)
    r = returns.dropna().values
    n_days = int(years * 252)
    buy_every = int(round(interval_days / 7 * 5))  # días de mercado entre compras
    n_buys = n_days // buy_every

    finals = np.empty(n_paths)
    invested = amount * n_buys
    for p in range(n_paths):
        idx = []
        while len(idx) < n_days:
            start = rng.integers(0, len(r) - block)
            idx.extend(range(start, start + block))
        path_r = r[np.array(idx[:n_days])]
        prices = 100 * np.cumprod(1 + path_r)
        units = 0.0
        for b in range(n_buys):
            units += amount / prices[b * buy_every]
        finals[p] = units * prices[-1]

    pct = {q: float(np.percentile(finals, q)) for q in (5, 25, 50, 75, 95)}
    irr = {q: _dca_irr(amount, n_buys, buy_every, n_days, v) for q, v in pct.items()}
    return {
        "invested": invested,
        "years": years,
        "n_paths": n_paths,
        "final_value_pct": pct,
        "moic_median": pct[50] / invested,
        "irr_pct": irr,
        "prob_loss": float((finals < invested).mean()),
    }


def _dca_irr(amount: float, n_buys: int, buy_every: int, n_days: int, final_value: float) -> float:
    """TIR anualizada de los flujos DCA (aportaciones periódicas -> valor final), por bisección."""

    def npv(annual: float) -> float:
        d = (1 + annual) ** (1 / 252) - 1
        t_buy = np.arange(n_buys) * buy_every
        pv_in = np.sum(amount / (1 + d) ** t_buy)
        return final_value / (1 + d) ** n_days - pv_in

    lo, hi = -0.95, 5.0
    if npv(lo) * npv(hi) > 0:
        return np.nan
    for _ in range(80):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2
