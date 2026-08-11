"""Descarga de datos de mercado (API chart de Yahoo Finance) con caché local.

No depende de yfinance: usa `requests` directamente contra el endpoint
/v8/finance/chart, que es el mismo que consume la web de Yahoo. Cada serie
se cachea en data/cache/<ticker>.csv; si la red falla, se usa la caché.
"""

from __future__ import annotations

import os
import time
import datetime as dt

import pandas as pd
import requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")

_HOSTS = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"]
_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}


def _safe_name(ticker: str) -> str:
    return ticker.replace("^", "_").replace("=", "_").replace(".", "_")


def _cache_path(ticker: str) -> str:
    return os.path.join(CACHE_DIR, f"{_safe_name(ticker)}.csv")


def _fetch_chart(ticker: str, retries: int = 5) -> pd.DataFrame:
    """Baja el histórico diario completo. Lanza excepción si no lo consigue."""
    now = int(time.time())
    params = {
        "period1": 0,
        "period2": now,
        "interval": "1d",
        "events": "div,split",
        "includeAdjustedClose": "true",
    }
    last_err: Exception | None = None
    for attempt in range(retries):
        host = _HOSTS[attempt % len(_HOSTS)]
        url = f"https://{host}/v8/finance/chart/{ticker}"
        try:
            r = requests.get(url, params=params, headers=_UA, timeout=30)
            if r.status_code == 200:
                return _parse_chart(r.json())
            last_err = RuntimeError(f"HTTP {r.status_code} para {ticker}")
        except Exception as e:  # red, TLS, JSON…
            last_err = e
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"No se pudo descargar {ticker}: {last_err}")


def _parse_chart(payload: dict) -> pd.DataFrame:
    result = payload["chart"]["result"][0]
    ts = result["timestamp"]
    quote = result["indicators"]["quote"][0]
    adj = result["indicators"].get("adjclose", [{}])[0].get("adjclose", quote["close"])
    df = pd.DataFrame(
        {
            "open": quote["open"],
            "high": quote["high"],
            "low": quote["low"],
            "close": quote["close"],
            "adjclose": adj,
            "volume": quote["volume"],
        },
        index=pd.to_datetime(ts, unit="s", utc=True).tz_convert("Europe/Berlin").normalize().tz_localize(None),
    )
    df.index.name = "date"
    df = df[~df.index.duplicated(keep="last")]
    df = df.dropna(subset=["close"])
    return df


def get_history(ticker: str) -> pd.DataFrame:
    """Histórico diario con caché: intenta red, cae a caché si falla."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(ticker)
    try:
        df = _fetch_chart(ticker)
        df.to_csv(path)
        return df
    except Exception as e:
        if os.path.exists(path):
            print(f"[data] aviso: fallo de red para {ticker} ({e}); usando caché local")
            df = pd.read_csv(path, index_col="date", parse_dates=["date"])
            return df
        raise


def freshness(df: pd.DataFrame) -> int:
    """Días naturales desde el último dato."""
    return (dt.date.today() - df.index[-1].date()).days
