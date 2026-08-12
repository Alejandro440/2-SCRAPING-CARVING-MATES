"""Generación del informe diario en Markdown + gráficos PNG (matplotlib).

Estilo de los gráficos: paleta categórica validada (azul/naranja/aqua),
rejilla recesiva, un solo eje por panel, líneas finas, leyenda cuando hay
más de una serie.
"""

from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# Paleta (modo claro)
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
YELLOW = "#eda100"
BAND = "#cde2fb"
RED = "#e34948"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(ROOT, "reports")
IMG_DIR = os.path.join(REPORT_DIR, "img")


def _style_ax(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.7)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelsize=9)
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color(MUTED)


def _fig(nrows=1, height=4.0, sharex=False):
    fig, axes = plt.subplots(nrows, 1, figsize=(10, height), sharex=sharex, facecolor=SURFACE)
    return fig, axes


def _save(fig, name: str) -> str:
    os.makedirs(IMG_DIR, exist_ok=True)
    path = os.path.join(IMG_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=130, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return os.path.join("img", name)


def chart_price(df: pd.DataFrame, lookback: int = 260) -> str:
    d = df.tail(lookback)
    fig, ax = _fig(height=4.6)
    _style_ax(ax)
    ax.fill_between(d.index, d["bb_low"], d["bb_up"], color=BAND, alpha=0.55, linewidth=0, label="Bandas Bollinger (20, 2σ)")
    ax.plot(d.index, d["close"], color=BLUE, linewidth=2.0, label="VWCE (cierre)")
    ax.plot(d.index, d["sma50"], color=ORANGE, linewidth=1.6, label="SMA 50")
    ax.plot(d.index, d["sma200"], color=AQUA, linewidth=1.6, label="SMA 200")
    ax.set_title("VWCE — último año: precio, medias y bandas", color=INK, fontsize=12, loc="left")
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    ax.set_ylabel("EUR", color=MUTED, fontsize=9)
    return _save(fig, "precio.png")


def chart_oscillators(df: pd.DataFrame, score: pd.Series, cfg: dict, lookback: int = 260) -> str:
    d = df.tail(lookback)
    s = score.reindex(d.index)
    fig, (ax1, ax2) = _fig(nrows=2, height=5.6, sharex=True)
    for ax in (ax1, ax2):
        _style_ax(ax)

    ax1.plot(d.index, d["rsi14"], color=BLUE, linewidth=1.8)
    ax1.axhline(70, color=BASELINE, linewidth=1.0, linestyle="--")
    ax1.axhline(30, color=BASELINE, linewidth=1.0, linestyle="--")
    ax1.set_ylim(0, 100)
    ax1.set_title("RSI(14)", color=INK, fontsize=11, loc="left")

    buy_t = cfg["dca"]["score_buy_threshold"]
    ax2.plot(s.index, s.values, color=ORANGE, linewidth=1.8)
    ax2.axhline(buy_t, color=BASELINE, linewidth=1.0, linestyle="--")
    ax2.annotate(f"umbral compra ({buy_t})", xy=(s.index[5], buy_t), xytext=(0, 4),
                 textcoords="offset points", color=MUTED, fontsize=8)
    ax2.set_ylim(0, 100)
    ax2.set_title("Nota de entrada (0-100)", color=INK, fontsize=11, loc="left")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %y"))
    return _save(fig, "osciladores.png")


def chart_drawdown(df: pd.DataFrame) -> str:
    fig, ax = _fig(height=3.6)
    _style_ax(ax)
    dd = df["drawdown"] * 100
    ax.fill_between(dd.index, dd, 0, color=BAND, alpha=0.8, linewidth=0)
    ax.plot(dd.index, dd, color=BLUE, linewidth=1.6)
    ax.set_title("Caída desde máximos históricos (%)", color=INK, fontsize=12, loc="left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    return _save(fig, "drawdown.png")


def chart_backtest(summary: pd.DataFrame, dataset_label: str, fname: str) -> str:
    d = summary.drop(index=[k for k in ("peor_dia",) if k in summary.index])
    d = d.sort_values("mejora_vs_base_bps")
    fig, ax = _fig(height=0.6 * len(d) + 1.6)
    _style_ax(ax)
    ax.grid(True, axis="x", color=GRID, linewidth=0.7)
    ax.grid(False, axis="y")
    colors = [ORANGE if k == "regla_nota" else BLUE for k in d.index]
    bars = ax.barh(np.arange(len(d)), d["mejora_vs_base_bps"], color=colors, height=0.62)
    for b in bars:
        b.set_linewidth(0)
    ax.set_yticks(np.arange(len(d)))
    ax.set_yticklabels(d["estrategia"], fontsize=9, color=INK)
    ax.axvline(0, color=BASELINE, linewidth=1.0)
    for i, v in enumerate(d["mejora_vs_base_bps"]):
        ax.annotate(f"{v:+.0f}", xy=(v, i), xytext=(4 if v >= 0 else -4, 0),
                    textcoords="offset points", va="center",
                    ha="left" if v >= 0 else "right", fontsize=8.5, color=INK)
    ax.set_title(f"Mejora del precio medio de compra vs comprar el primer día (pb) — {dataset_label}",
                 color=INK, fontsize=11, loc="left")
    return _save(fig, fname)


def chart_montecarlo(mc: dict) -> str:
    fig, ax = _fig(height=3.8)
    _style_ax(ax)
    qs = [5, 25, 50, 75, 95]
    vals = [mc["final_value_pct"][q] for q in qs]
    ax.bar([f"p{q}" for q in qs], vals, color=[BAND, "#86b6ef", BLUE, "#86b6ef", BAND], linewidth=0, width=0.62)
    ax.axhline(mc["invested"], color=RED, linewidth=1.4, linestyle="--")
    ax.annotate(f"capital aportado €{mc['invested']:,.0f}", xy=(0.02, mc["invested"]),
                xycoords=("axes fraction", "data"), xytext=(0, 5), textcoords="offset points",
                color=RED, fontsize=8.5)
    for i, v in enumerate(vals):
        ax.annotate(f"€{v/1000:,.0f}k", xy=(i, v), xytext=(0, 4), textcoords="offset points",
                    ha="center", fontsize=8.5, color=INK)
    ax.set_title(f"Monte Carlo {mc['years']} años · €500/quincena · {mc['n_paths']} escenarios — valor final",
                 color=INK, fontsize=11, loc="left")
    return _save(fig, "montecarlo.png")


def _pct(x, digits=1):
    return "n/d" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x*100:+.{digits}f}%"


def build_markdown(ctx: dict) -> str:
    """Compone el informe diario en Markdown a partir del contexto calculado."""
    cfg = ctx["cfg"]
    last = ctx["last"]
    comps = ctx["components"]
    score = ctx["score_today"]
    date_str = ctx["date"].strftime("%Y-%m-%d")

    md = []
    md.append(f"# Informe diario VWCE — {date_str}")
    md.append("")
    md.append(f"**{cfg['instrument']['name']}** · {cfg['instrument']['exchange']} · ISIN {cfg['instrument']['isin']}")
    md.append("")

    # --- Resumen ejecutivo ---
    md.append("## 1 · Resumen ejecutivo")
    md.append("")
    md.append(f"| | |")
    md.append(f"|---|---|")
    md.append(f"| Cierre | **{last['close']:.2f} €** ({_pct(last['ret_1d'], 2)} vs día anterior) |")
    md.append(f"| Nota técnica de entrada | **{score:.0f} / 100** |")
    md.append(f"| Nota fundamental | **{ctx['fund']['score']:.0f} / 100** |")
    md.append(f"| Régimen | {ctx['regime']} |")
    md.append(f"| Caída desde máximos | {last['drawdown']*100:.1f}% |")
    md.append(f"| Datos a | {ctx['data_date']} ({ctx['staleness']} días) |")
    md.append("")
    md.append(f"> **Decisión sugerida:** {ctx['recommendation']}")
    md.append("")

    # --- Nota de entrada ---
    md.append("## 2 · Nota de entrada — desglose")
    md.append("")
    md.append("Cada componente puntúa 0-100 (más alto = punto de entrada más favorable).")
    md.append("")
    md.append("| Componente | Valor bruto | Nota | Peso |")
    md.append("|---|---|---|---|")
    raw = ctx["raw_values"]
    from .signals import WEIGHTS
    labels = {
        "drawdown": ("Caída desde máximos", f"{last['drawdown']*100:.1f}%"),
        "rsi": ("RSI(14)", f"{last['rsi14']:.1f}"),
        "sma200_gap": ("Distancia a SMA200", f"{raw['sma200_gap']*100:+.1f}%"),
        "bollinger": ("Bollinger %B", f"{last['bb_pctb']:.2f}"),
        "zscore": ("Z-score 60 días", f"{last['z60']:+.2f}σ"),
        "vix": ("Percentil VIX 5 años", f"{ctx['vix']['pct_rank_5y']*100:.0f}% (VIX {ctx['vix']['level']:.1f})"),
    }
    for k, w in WEIGHTS.items():
        name, rawv = labels[k]
        md.append(f"| {name} | {rawv} | {comps[k]:.0f} | {w:.0%} |")
    md.append(f"| **Total** | | **{score:.0f}** | 100% |")
    md.append("")

    # --- Técnico ---
    md.append("## 3 · Cuadro técnico")
    md.append("")
    md.append("| Indicador | Valor | Lectura |")
    md.append("|---|---|---|")
    gap50 = last["close"] / last["sma50"] - 1
    gap200 = last["close"] / last["sma200"] - 1
    macd_state = "alcista" if last["macd_hist"] > 0 else "bajista"
    md.append(f"| SMA 50 / SMA 200 | {last['sma50']:.2f} / {last['sma200']:.2f} | precio {_pct(gap50)} vs SMA50, {_pct(gap200)} vs SMA200 |")
    md.append(f"| RSI(14) | {last['rsi14']:.1f} | {'sobreventa' if last['rsi14']<30 else 'sobrecompra' if last['rsi14']>70 else 'neutral'} |")
    md.append(f"| MACD (12,26,9) | hist {last['macd_hist']:+.3f} | momentum {macd_state} |")
    md.append(f"| Bollinger %B | {last['bb_pctb']:.2f} | {'zona baja' if last['bb_pctb']<0.2 else 'zona alta' if last['bb_pctb']>0.8 else 'zona media'} |")
    md.append(f"| Volatilidad 20d (anualizada) | {last['vol20']*100:.1f}% | ATR14 {last['atr14']:.2f} € |")
    md.append(f"| Máx / mín 52 semanas | {ctx['hi52']:.2f} / {ctx['lo52']:.2f} | precio al {(last['close']/ctx['hi52'])*100:.1f}% del máximo |")
    md.append("")
    md.append(f"![Precio]({ctx['charts']['price']})")
    md.append("")
    md.append(f"![Osciladores]({ctx['charts']['osc']})")
    md.append("")
    md.append(f"![Drawdown]({ctx['charts']['dd']})")
    md.append("")

    # --- Niveles de entrada ---
    md.append("## 4 · Niveles de entrada y probabilidad de verlos")
    md.append("")
    lv = ctx["levels"]
    md.append("¿A qué precio se dispararía la nota técnica? (recalculada suponiendo que el precio cae hasta ese nivel, con el VIX de hoy):")
    md.append("")
    md.append("| Umbral | Precio aproximado | Caída necesaria |")
    md.append("|---|---|---|")
    for t in sorted(lv):
        md.append(f"| Nota ≥ {t:.0f} | ~{lv[t]['price']:.2f} € | −{lv[t]['drop_pct']:.1f}% |")
    if not lv:
        md.append("| — | no se alcanza ni con −30% (mercado en régimen extremo) | |")
    md.append("")
    md.append(f"Referencias técnicas cercanas: SMA50 {last['sma50']:.2f} € ({(last['sma50']/last['close']-1)*100:+.1f}%), "
              f"banda inferior de Bollinger {last['bb_low']:.2f} € ({(last['bb_low']/last['close']-1)*100:+.1f}%), "
              f"SMA200 {last['sma200']:.2f} € ({(last['sma200']/last['close']-1)*100:+.1f}%).")
    md.append("")
    md.append("Probabilidad histórica de ver una caída de al menos x% desde el precio de hoy (frecuencia empírica, índice mundial en EUR desde 2012):")
    md.append("")
    md.append(ctx["dip_probs"])
    md.append("")

    # --- Fundamental ---
    md.append("## 5 · Análisis fundamental")
    md.append("")
    f = ctx["fund"]
    md.append(f"**Nota fundamental: {f['score']:.0f} / 100** — modelo multi-señal tipo desk bancario (valoración + régimen de riesgo).")
    md.append("")
    md.append("| Componente | Valor bruto | Nota | Peso |")
    md.append("|---|---|---|---|")
    from .fundamental import WEIGHTS as FW
    fc = f["components"]
    erp_raw = (f"earnings yield {f['earnings_yield_pct']:.2f}% − 10a {ctx['rates']['level_pct']:.2f}% = **{f['erp_pct']:+.2f} pp**"
               if f.get("erp_pct") is not None else "n/d")
    flabels = {
        "erp": ("Prima de riesgo (Fed model)", erp_raw),
        "trend": ("Desviación del canal de tendencia", f"{ctx['trend']['deviation_sigma']:+.1f}σ ({ctx['trend']['deviation_pct']:+.1f}%)"),
        "vix_term": ("Estructura temporal VIX/VIX3M", f"{ctx['vix_ts']:.3f} ({'backwardation: pánico' if ctx['vix_ts']>1 else 'contango: calma'})"),
        "credit": ("Estrés de crédito (z HYG/LQD 120d)", f"{ctx['credit_z']:+.2f}σ"),
    }
    for k, w in FW.items():
        name, rawv = flabels[k]
        nota = f"{fc[k]:.0f}" if fc[k] is not None else "n/d"
        md.append(f"| {name} | {rawv} | {nota} | {w:.0%} |")
    md.append(f"| **Total** | | **{f['score']:.0f}** | 100% |")
    md.append("")
    if f.get("valuation"):
        val = f["valuation"]
        pb = f" · P/B {val['pb']:.1f}" if val.get("pb") else ""
        dy = f" · rentabilidad por dividendo {val['div_yield']*100:.2f}%" if val.get("div_yield") else ""
        md.append(f"Valoración del índice mundial (vía VT): **P/E {val['pe']:.1f}**{pb}{dy} · fuente: {f['val_source']}.")
        md.append("")
    md.append(f"Ciclo (contexto, no puntúa): pendiente de la curva EEUU 10a − 3m = {ctx['curve_slope']:+.2f} pp "
              f"({'invertida — señal clásica de fin de ciclo' if ctx['curve_slope']<0 else 'positiva — sin señal de recesión inminente por curva'}).")
    md.append("")
    md.append("Lectura: la nota fundamental se mueve despacio (valoración y ciclo); la técnica, rápido (precio). "
              "Las mejores entradas históricas coinciden cuando **ambas** están altas — pánico con valoraciones comprimidas.")
    md.append("")

    # --- Contexto macro / fundamental ---
    md.append("## 6 · Contexto macro")
    md.append("")
    v, fx, rt, tc, dec = ctx["vix"], ctx["fx"], ctx["rates"], ctx["trend"], ctx["decomp"]
    md.append("| Métrica | Valor | Comentario |")
    md.append("|---|---|---|")
    md.append(f"| VIX | {v['level']:.1f} (percentil 5a: {v['pct_rank_5y']*100:.0f}%) | {'calma' if v['pct_rank_5y']<0.4 else 'estrés elevado' if v['pct_rank_5y']>0.75 else 'nerviosismo moderado'} |")
    md.append(f"| EURUSD | {fx['level']:.4f} ({_pct(fx['chg_3m'])} 3m, {_pct(fx['chg_1y'])} 1a) | euro fuerte abarata VWCE en EUR |")
    md.append(f"| Tipos EEUU 10 años | {rt['level_pct']:.2f}% ({rt['chg_3m_pp']:+.2f} pp 3m) | tipos al alza presionan valoraciones |")
    md.append(f"| Tendencia largo plazo (CAGR desde 2019) | {tc['cagr_pct']:.1f}% anual | precio {tc['deviation_pct']:+.1f}% vs tendencia ({tc['deviation_sigma']:+.1f}σ) |")
    md.append("")
    md.append(f"**Descomposición de la rentabilidad a 1 año:** VWCE en EUR {_pct(dec['ret_eur'])} ≈ índice mundial en USD {_pct(dec['ret_usd_proxy'])} "
              f"con EURUSD {_pct(dec['eurusd_chg'])} (euro {'fortaleciéndose (viento en contra)' if dec['eurusd_chg']>0 else 'debilitándose (viento a favor)'}).")
    md.append("")
    ins = cfg["instrument"]
    md.append(f"**Ficha del fondo:** índice {ins['index']} (~3.900 empresas, todo el mundo desarrollado y emergente) · TER {ins['ter_pct']}% · "
              f"acumulación · réplica {ins['replication'].lower()} · domicilio {ins['domicile']}.")
    md.append("")

    # --- Posición personal ---
    md.append("## 7 · Tu posición y próxima entrada")
    md.append("")
    pos = cfg["position"]
    mkt_val = pos["shares"] * last["close"]
    cost = pos["shares"] * pos["avg_cost_eur"]
    pnl = mkt_val - cost
    md.append(f"| | |")
    md.append(f"|---|---|")
    md.append(f"| Participaciones | {pos['shares']:.4f} |")
    md.append(f"| Precio medio | {pos['avg_cost_eur']:.2f} € |")
    md.append(f"| Valor de mercado | {mkt_val:,.2f} € |")
    md.append(f"| P&L latente | {pnl:+,.2f} € ({_pct(pnl/cost)}) |")
    new_shares = cfg["dca"]["amount_eur"] / last["close"]
    new_avg = (cost + cfg["dca"]["amount_eur"]) / (pos["shares"] + new_shares)
    md.append(f"| Si compras hoy 500 € | +{new_shares:.4f} part. → precio medio {new_avg:.2f} € |")
    md.append("")

    # --- Backtest ---
    md.append("## 8 · Backtest de estrategias de entrada quincenal")
    md.append("")
    md.append("Cada estrategia invierte **500 € una vez por ventana de 14 días**; solo cambia el día elegido. "
              "\"pb\" = puntos básicos de mejora del precio medio de compra frente a comprar siempre el primer día. "
              "El *oráculo* (mejor día con información perfecta) marca el techo teórico de lo que se puede ganar eligiendo el día.")
    md.append("")
    for label, table_md, img in ctx["backtests"]:
        md.append(f"### {label}")
        md.append("")
        md.append(table_md)
        md.append("")
        md.append(f"![Backtest]({img})")
        md.append("")
    cc = ctx["cash_carry"]
    md.append(f"**¿Y esperar la gran caída?** La variante que acumula el efectivo hasta ver nota ≥ 70 (máx. 3 ventanas) "
              f"terminó con precio medio {cc['avg_price']:.2f} € frente a {cc['base_avg']:.2f} € comprando cada quincena "
              f"({cc['delta_bps']:+.0f} pb). {cc['verdict']}")
    md.append("")

    # --- Monte Carlo ---
    mc = ctx["mc"]
    md.append("## 9 · Simulación Monte Carlo (plan actual a 5 años)")
    md.append("")
    md.append(f"Bootstrap por bloques de los rendimientos diarios históricos ({mc['n_paths']} escenarios, "
              f"aportando 500 € cada 14 días durante {mc['years']} años = {mc['invested']:,.0f} € aportados):")
    md.append("")
    md.append("| Percentil | Valor final | TIR anualizada |")
    md.append("|---|---|---|")
    for q in (5, 25, 50, 75, 95):
        md.append(f"| p{q} | {mc['final_value_pct'][q]:,.0f} € | {_pct(mc['irr_pct'][q])} |")
    md.append("")
    md.append(f"Probabilidad de acabar por debajo del capital aportado: **{mc['prob_loss']*100:.1f}%**.")
    md.append("")
    md.append(f"![Monte Carlo]({ctx['charts']['mc']})")
    md.append("")

    # --- Metodología ---
    md.append("---")
    md.append("")
    md.append("### Metodología y avisos")
    md.append("")
    md.append("- Datos: Yahoo Finance (VWCE.DE; proxies VWRL.AS desde 2012 y VT desde 2008 para histórico largo; EURUSD, VIX, ^TNX).")
    md.append("- La nota de entrada es un modelo de reversión a la media: mide lo *barato que está hoy respecto a su propia historia reciente*, no predice el futuro.")
    md.append("- Rentabilidades pasadas no garantizan rentabilidades futuras. Esto es una herramienta de apoyo, **no asesoramiento financiero**.")
    md.append("- Generado automáticamente por el workflow diario de este repositorio.")
    md.append("")
    return "\n".join(md)
