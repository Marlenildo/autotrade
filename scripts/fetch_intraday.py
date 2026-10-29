"""Baixa candles intradiários do Yahoo (limites: 60m ~730 dias, 15m/5m ~60 dias).
Os arquivos são acumulados: cada execução junta o novo ao que já existe, então o
histórico intradiário cresce com o tempo mesmo com o limite do Yahoo.
Uso: python scripts/fetch_intraday.py PETR4 VALE3 ...
"""
import os, sys
import pandas as pd
import yfinance as yf

TICKERS = sys.argv[1:] or ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "BOVA11", "PRIO3", "WEGE3"]
SPECS = {"60m": "730d", "15m": "60d", "5m": "60d"}
os.makedirs("data/intraday", exist_ok=True)
for t in TICKERS:
    for iv, per in SPECS.items():
        try:
            df = yf.Ticker(t + ".SA").history(period=per, interval=iv, auto_adjust=False, actions=False)
            if df.empty:
                print(t, iv, "vazio"); continue
            df.index = df.index.tz_convert("America/Sao_Paulo").tz_localize(None)
            df.index.name = "date"
            df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
            f = f"data/intraday/{t}_{iv}.csv"
            if os.path.exists(f):
                old = pd.read_csv(f, parse_dates=["date"]).set_index("date")
                df = pd.concat([old, df]); df = df[~df.index.duplicated(keep="last")].sort_index()
            df.to_csv(f)
            print(t, iv, len(df), df.index.min(), df.index.max())
        except Exception as e:
            print(t, iv, "falhou:", e)

# brapi: candles de 1 minuto do último mês (o Yahoo só guarda 7 dias). Liberado para os
# ativos de teste da brapi (PETR4, VALE3, ITUB4, MGLU3) em qualquer plano; acumulado a cada execução.
import json, time, urllib.request
tok = os.environ.get("BRAPI_TOKEN", "")
for t in ["PETR4", "VALE3", "ITUB4", "MGLU3"]:
    try:
        time.sleep(1.5)
        url = f"https://brapi.dev/api/quote/{t}?range=1mo&interval=1m" + (f"&token={tok}" if tok else "")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "autotrade"}), timeout=60) as r:
            h = json.load(r)["results"][0]["historicalDataPrice"]
        df = pd.DataFrame(h)
        df["date"] = pd.to_datetime(df["date"], unit="s", utc=True).dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
        df = df.set_index("date")[["open", "high", "low", "close", "volume"]]
        f = f"data/intraday/{t}_1m.csv"
        if os.path.exists(f):
            old = pd.read_csv(f, parse_dates=["date"]).set_index("date")
            df = pd.concat([old, df]); df = df[~df.index.duplicated(keep="last")].sort_index()
        df.to_csv(f)
        print(t, "1m brapi", len(df), df.index.min(), df.index.max())
    except Exception as e:
        print(t, "1m brapi falhou:", e)
