"""Testa o que a brapi entrega (com ou sem BRAPI_TOKEN) para cada intervalo e período.
Grava data/brapi_probe.json e imprime um resumo."""
import os, json, urllib.request, urllib.error
import pandas as pd

TOK = os.environ.get("BRAPI_TOKEN", "")
TICKERS = ["PETR4", "BBAS3"]  # PETR4 é grátis sem token; BBAS3 exige token
INTERVALS = ["1d", "1h", "15m", "5m", "1m"]
RANGES = ["max", "5y", "2y", "1y", "6mo", "3mo", "1mo", "5d", "1d"]
out = {"token": bool(TOK), "results": []}
for t in TICKERS:
    for iv in INTERVALS:
        for rg in RANGES:
            url = f"https://brapi.dev/api/quote/{t}?range={rg}&interval={iv}" + (f"&token={TOK}" if TOK else "")
            row = dict(ticker=t, interval=iv, range=rg)
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "autotrade"}), timeout=60) as r:
                    j = json.load(r)
                h = j["results"][0].get("historicalDataPrice") or []
                row["rows"] = len(h)
                if h:
                    d = pd.to_datetime([x["date"] for x in h], unit="s")
                    row["first"], row["last"] = str(d.min()), str(d.max())
                    os.makedirs("data/brapi", exist_ok=True)
                    if rg in ("max", "5y", "2y", "1y", "3mo") and iv != "1d":
                        pd.DataFrame(h).to_csv(f"data/brapi/{t}_{iv}_{rg}.csv", index=False)
            except urllib.error.HTTPError as e:
                row["error"] = f"HTTP {e.code}: {e.read()[:160].decode(errors='ignore')}"
            except Exception as e:
                row["error"] = str(e)[:160]
            out["results"].append(row)
            print(row, flush=True)
json.dump(out, open("data/brapi_probe.json", "w"), indent=1)
