# VWCE Quant Desk

Sistema de análisis **diario y automático** del ETF **VWCE** (Vanguard FTSE All-World UCITS ETF, IE00BK5BQT80, Xetra), orientado a optimizar un plan de aportaciones periódicas (**DCA de 500 € cada 14 días**).

**➡️ El informe del día está siempre en [`reports/latest.md`](reports/latest.md).** Cada día queda archivado en `reports/<año>/`.

## Qué hace cada día

Un workflow de GitHub Actions (`.github/workflows/daily-analysis.yml`) corre de lunes a viernes a las **07:30 (hora española)**, antes de la apertura de Xetra, y publica un informe con:

1. **Nota de entrada (0–100)** — modelo compuesto de reversión a la media al estilo de un desk sistemático: caída desde máximos, RSI(14), distancia a la SMA200, Bollinger %B, z-score 60d y percentil del VIX. Más alta = punto de entrada más favorable *en términos relativos a su propia historia*.
2. **Cuadro técnico completo** — medias 50/200, MACD, Bollinger, ATR, volatilidad, rango 52 semanas, régimen de tendencia.
3. **Contexto macro/fundamental** — VIX, EURUSD (clave: el subyacente es USD y tú compras en EUR), tipos EEUU a 10 años, canal de tendencia de largo plazo y descomposición de la rentabilidad EUR = índice USD + divisa. Ficha del fondo (TER 0,22 %, ~3.900 empresas, acumulación).
4. **Tu posición** — valor, P&L latente y cómo movería tu precio medio la aportación de hoy (se configura en `config.json`).
5. **Backtest de estrategias de entrada quincenal** sobre tres históricos (VWCE desde 2019, VWRL.AS desde 2012 y VT desde 2008, que incluye la crisis financiera): comprar el primer día vs esperar caídas, RSI, la regla de la nota, y el *oráculo* (mejor día posible) como techo teórico.
6. **Simulación Monte Carlo** — 2.000 escenarios a 5 años del plan de 500 €/quincena (bootstrap por bloques de rendimientos históricos), con percentiles de valor final y TIR.

## La conclusión que ya sale de los backtests (y conviene tener presente)

En un activo con deriva alcista como un indexado mundial, **elegir el día dentro de la ventana quincenal mueve muy poco el resultado** (el techo teórico con información perfecta ronda ~150–230 pb en precio medio, y las reglas realistas capturan una fracción pequeña, a veces negativa). La regla práctica que el informe aplica:

- Si toca aportar, **aporta — no esperes "la caída"**: retrasar sistemáticamente sale caro.
- La nota sirve para **adelantar** la entrada cuando hay señal fuerte (≥ 80: caídas con miedo en el mercado), no para saltarse compras.

## Estructura

```
config.json        ← tu plan: importe, intervalo, umbrales, posición actual
run_daily.py       ← orquestador (python run_daily.py)
src/
  data.py          ← descarga Yahoo Finance + caché en data/cache/
  indicators.py    ← RSI, MACD, Bollinger, ATR, drawdown, z-score…
  signals.py       ← nota de entrada 0-100 y recomendación
  context.py       ← VIX, EURUSD, tipos, canal de tendencia, descomposición FX
  backtest.py      ← estrategias quincenales, oráculo, cash-carry, Monte Carlo
  report.py        ← informe Markdown + gráficos PNG
reports/           ← latest.md + archivo por año + img/
data/              ← caché de precios y score_history.csv (serie diaria de la nota)
```

## Configurar tu plan

Edita `config.json`:

- `dca.amount_eur` / `dca.interval_days` — tu plan de aportación.
- `dca.last_entry_date` — pon la fecha (`"2026-08-04"`) de tu última compra y el informe te dirá en qué día de la ventana estás y cuándo vence.
- `position.shares` / `position.avg_cost_eur` — tu posición, para el P&L diario.
- Umbrales de la nota: `score_buy_threshold` (65) y `score_strong_threshold` (80).

## Ejecutar en local

```bash
pip install -r requirements.txt
python run_daily.py   # escribe reports/latest.md
```

## Avisos

- Datos de Yahoo Finance (con caché local si la red falla). Pueden llevar ~1 día de retardo respecto al tiempo real.
- La nota **no predice el futuro**: mide lo barato que está el ETF respecto a su propia historia reciente y el régimen de riesgo.
- Rentabilidades pasadas no garantizan rentabilidades futuras. Esto es una herramienta de apoyo a la decisión, **no asesoramiento financiero**.
