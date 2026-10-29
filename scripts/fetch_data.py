"""Baixa histórico diário (OHLCV + proventos) de ativos da B3.
Fonte principal: Yahoo Finance (yfinance) — traz dividendos/JCP e splits.
Fonte alternativa: brapi.dev (defina BRAPI_TOKEN para ativos fora do plano grátis).
Uso: python scripts/fetch_data.py PETR4 VALE3 ITUB4 ...
"""
import os, sys, json, urllib.request
import pandas as pd

TICKERS = sys.argv[1:] or ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "WEGE3", "MGLU3", "B3SA3", "PRIO3", "BOVA11"]
os.makedirs("data", exist_ok=True)

def via_yf(t):
    import yfinance as yf
    tk = yf.Ticker(t + ".SA")
    df = tk.history(start="2010-01-01", auto_adjust=False, actions=True)
    if df.empty:
        return None
    df.index = df.index.tz_localize(None).date
    df.index.name = "date"
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "adj close", "volume", "dividends", "stock splits"]]
    df.columns = ["open", "high", "low", "close", "adj_close", "volume", "dividends", "splits"]
    return df

def via_brapi(t):
    tok = os.environ.get("BRAPI_TOKEN", "")
    url = f"https://brapi.dev/api/quote/{t}?range=max&interval=1d&dividends=true" + (f"&token={tok}" if tok else "")
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "autotrade"}), timeout=60) as r:
        j = json.load(r)
    h = pd.DataFrame(j["results"][0]["historicalDataPrice"])
    h["date"] = pd.to_datetime(h["date"], unit="s").dt.date
    return h.set_index("date")

for t in TICKERS:
    try:
        df = via_yf(t)
        df.to_csv(f"data/{t}.csv")
        print(t, "yfinance", len(df), df.index.min(), df.index.max())
    except Exception as e:
        print(t, "yfinance falhou:", e)
    try:
        b = via_brapi(t)
        b.to_csv(f"data/{t}_brapi.csv")
        print(t, "brapi", len(b), b.index.min(), b.index.max())
    except Exception as e:
        print(t, "brapi falhou:", e)
