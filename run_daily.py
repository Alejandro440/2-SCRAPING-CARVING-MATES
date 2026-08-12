"""Orquestador del análisis diario de VWCE.

Uso:  python run_daily.py

Descarga datos, calcula indicadores y nota de entrada, corre los backtests
y la simulación Monte Carlo, y escribe:
  - reports/latest.md            (informe del día, con gráficos en reports/img/)
  - reports/YYYY/YYYY-MM-DD.md   (archivo histórico)
  - data/score_history.csv       (serie diaria de la nota de entrada)
"""

from __future__ import annotations

import datetime as dt
import json
import os

import pandas as pd

from src import backtest, context, fundamental, levels, report, signals
from src.data import freshness, get_history
from src.indicators import enrich

ROOT = os.path.dirname(os.path.abspath(__file__))


def load_cfg() -> dict:
    with open(os.path.join(ROOT, "config.json")) as f:
        return json.load(f)


def run_backtests(cfg: dict, vix_rank_full: pd.Series,
                  extra_signals: dict | None = None) -> tuple[list, dict]:
    """Backtest sobre VWCE (2019-) y los proxies de histórico largo."""
    datasets = [
        (cfg["instrument"]["ticker"], "VWCE desde 2019 (EUR)", "backtest_vwce.png"),
        (cfg["proxies"]["long_history_eur"], "Proxy VWRL Ámsterdam desde 2012 (EUR)", "backtest_vwrl.png"),
        (cfg["proxies"]["long_history_usd"], "Proxy VT desde 2008 (USD, incluye crisis 2008)", "backtest_vt.png"),
    ]
    out = []
    cash_carry_info = {}
    for ticker, label, fname in datasets:
        df = enrich(get_history(ticker))
        score = signals.entry_score(df, vix_rank_full)
        strats = backtest.run_window_strategies(
            df, amount=cfg["dca"]["amount_eur"], interval_days=cfg["dca"]["interval_days"],
            score=score, score_threshold=cfg["dca"]["score_buy_threshold"],
            extra_signals=extra_signals,
        )
        summary = backtest.summarize(strats, df["close"].iloc[-1])
        img = report.chart_backtest(summary, label, fname)
        cols = ["estrategia", "compras", "precio_medio", "mejora_vs_base_bps", "captura_oraculo_pct"]
        tbl = summary[cols].rename(columns={
            "estrategia": "Estrategia", "compras": "Compras", "precio_medio": "Precio medio",
            "mejora_vs_base_bps": "Mejora (pb)", "captura_oraculo_pct": "Captura oráculo %",
        })
        out.append((label, tbl.to_markdown(index=False), img))

        if ticker == cfg["instrument"]["ticker"]:
            cc = backtest.run_cash_carry(df, score, amount=cfg["dca"]["amount_eur"],
                                         interval_days=cfg["dca"]["interval_days"])
            base_avg = strats["primer_dia"].avg_price
            delta_bps = (base_avg / cc.avg_price - 1) * 1e4
            verdict = (
                "En este histórico, esperar mejoró ligeramente el precio medio."
                if delta_bps > 5 else
                "En este histórico, esperar NO compensó: en un activo con deriva alcista, el coste de estar fuera supera el descuento que se consigue."
                if delta_bps < -5 else
                "Resultado prácticamente neutro: elegir el día importa mucho menos que aportar con disciplina."
            )
            cash_carry_info = {
                "avg_price": cc.avg_price, "base_avg": base_avg,
                "delta_bps": delta_bps, "verdict": verdict,
            }
    return out, cash_carry_info


def append_score_history(date, close, score, components):
    path = os.path.join(ROOT, "data", "score_history.csv")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    row = {"date": date.strftime("%Y-%m-%d"), "close": round(float(close), 2),
           "score": round(float(score), 1)}
    row.update({f"c_{k}": round(float(v), 1) for k, v in components.items()})
    if os.path.exists(path):
        hist = pd.read_csv(path)
        hist = hist[hist["date"] != row["date"]]
        hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True)
    else:
        hist = pd.DataFrame([row])
    hist.to_csv(path, index=False)


def main():
    cfg = load_cfg()
    today = dt.date.today()
    print(f"[run] análisis diario VWCE — {today}")

    # --- datos ---
    vwce = enrich(get_history(cfg["instrument"]["ticker"]))
    vt = get_history(cfg["proxies"]["long_history_usd"])
    fx = get_history(cfg["proxies"]["fx"])
    vix = get_history(cfg["proxies"]["vix"])
    vix3m = get_history(cfg["proxies"]["vix3m"])
    tnx = get_history(cfg["proxies"]["us10y"])
    irx = get_history(cfg["proxies"]["us3m"])
    hyg = get_history(cfg["proxies"]["credit_hy"])
    lqd = get_history(cfg["proxies"]["credit_ig"])

    vix_ctx = context.vix_context(vix)
    vix_rank = vix_ctx["series_rank"]

    # --- canal fundamental ---
    vix_ts = fundamental.vix_term_structure(vix, vix3m)
    credit_z = fundamental.credit_stress_z(hyg, lqd)
    curve = fundamental.curve_slope(tnx, irx)
    valuation, val_source = fundamental.valuation_with_fallback(cfg["proxies"]["long_history_usd"])

    # --- señales ---
    score_series = signals.entry_score(vwce, vix_rank)
    comps_df = signals.component_scores(vwce, vix_rank)
    last = vwce.iloc[-1]
    score_today = float(score_series.iloc[-1])
    components = comps_df.iloc[-1].to_dict()

    days_since = None
    if cfg["dca"].get("last_entry_date"):
        days_since = (today - dt.date.fromisoformat(cfg["dca"]["last_entry_date"])).days
    reco = signals.recommendation(score_today, days_since, cfg)

    # --- backtests + monte carlo ---
    extra_signals = {
        "vix_backwardation": ("Primer día con VIX > VIX3M (pánico), si no último día", vix_ts > 1.0),
        "credit_stress": ("Primer día con estrés de crédito (z ≤ −1), si no último día", credit_z <= -1.0),
    }
    backtests_md, cash_carry_info = run_backtests(cfg, vix_rank, extra_signals)
    mc = backtest.monte_carlo_dca(vt["close"].pct_change(), years=5,
                                  amount=cfg["dca"]["amount_eur"],
                                  interval_days=cfg["dca"]["interval_days"])

    # --- fundamental score + niveles de entrada ---
    trend = context.trend_channel(vwce["close"])
    rates = context.rates_context(tnx)
    fund = fundamental.fundamental_score(
        valuation, us10y_pct=rates["level_pct"],
        trend_sigma=trend["deviation_sigma"],
        vix_ts_now=float(vix_ts.iloc[-1]),
        credit_z_now=float(credit_z.iloc[-1]),
    )
    fund["valuation"] = valuation
    fund["val_source"] = val_source

    vwce_raw = get_history(cfg["instrument"]["ticker"])
    trigger_levels = levels.find_trigger_levels(vwce_raw, vix_score=float(components["vix"]))
    vwrl = get_history(cfg["proxies"]["long_history_eur"])
    dip_probs_md = levels.dip_probabilities(vwrl["close"]).to_markdown(index=False)

    # --- gráficos ---
    charts = {
        "price": report.chart_price(vwce),
        "osc": report.chart_oscillators(vwce, score_series, cfg),
        "dd": report.chart_drawdown(vwce),
        "mc": report.chart_montecarlo(mc),
    }

    tail252 = vwce["close"].tail(252)
    ctx = {
        "cfg": cfg,
        "date": today,
        "data_date": vwce.index[-1].date().isoformat(),
        "staleness": freshness(vwce),
        "last": last,
        "score_today": score_today,
        "components": components,
        "raw_values": {"sma200_gap": float(last["close"] / last["sma200"] - 1)},
        "regime": signals.regime(vwce),
        "recommendation": reco,
        "hi52": float(tail252.max()),
        "lo52": float(tail252.min()),
        "vix": vix_ctx,
        "fx": context.fx_context(fx),
        "rates": rates,
        "trend": trend,
        "decomp": context.return_decomposition(vwce, vt, fx),
        "fund": fund,
        "levels": trigger_levels,
        "dip_probs": dip_probs_md,
        "vix_ts": float(vix_ts.iloc[-1]),
        "credit_z": float(credit_z.iloc[-1]),
        "curve_slope": float(curve.iloc[-1]),
        "backtests": backtests_md,
        "cash_carry": cash_carry_info,
        "mc": mc,
        "charts": charts,
    }

    md = report.build_markdown(ctx)

    latest = os.path.join(report.REPORT_DIR, "latest.md")
    os.makedirs(report.REPORT_DIR, exist_ok=True)
    with open(latest, "w") as f:
        f.write(md)
    year_dir = os.path.join(report.REPORT_DIR, str(today.year))
    os.makedirs(year_dir, exist_ok=True)
    archived = os.path.join(year_dir, f"{today.isoformat()}.md")
    # el archivo histórico referencia las mismas imágenes con ruta relativa distinta
    with open(archived, "w") as f:
        f.write(md.replace("](img/", "](../img/"))

    append_score_history(vwce.index[-1], last["close"], score_today, components)

    print(f"[run] nota técnica: {score_today:.1f} · nota fundamental: {fund['score']:.1f} · régimen {ctx['regime']}")
    for t, info in sorted(trigger_levels.items()):
        print(f"[run] nivel nota≥{t:.0f}: ~{info['price']:.2f} € (−{info['drop_pct']:.1f}%)")
    print(f"[run] decisión: {reco}")
    print(f"[run] informe: {latest}")


if __name__ == "__main__":
    main()
