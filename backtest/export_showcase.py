"""Exporta as estratégias de destaque para o relatório: métricas por ativo e
candles + indicadores + operações para o gráfico com replay."""
import sys, os, json
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
from engine2 import *
from grid2 import DAILY_T, INTRA_T, bounds_for

OUT = "report/data"; os.makedirs(OUT, exist_ok=True)
U = "Sua regra (IFR 30/70, médias 5/10, stop 3%)"
STRATS = {
 "1d": {
   "orig": (U, Cfg("rev", "both", "both", "any", 30, "fast", "p3")),
   "pull": ("Pullback em tendência + CDI", Cfg("trend", "both", "long", "against", 0, "slow", "none", cdi=True)),
   "revatr": ("Reversão IFR 30→70, stop ATR, até 3 entradas + CDI", Cfg("rev", "fast", "long", "against", 30, "rsi", "atr1", 0, 3, cdi=True)),
   "trifr": ("Tendência com IFR > 60 + CDI", Cfg("trend", "both", "long", "any", 40, "both", "none", cdi=True)),
 },
 "1wk": {
   "orig": (U, Cfg("rev", "both", "both", "any", 30, "fast", "p3")),
   "wk": ("Semanal: tendência, candle a favor, sai no IFR 70 + CDI", Cfg("trend", "either", "long", "with", 0, "rsi", "atr1", 2, 3, cdi=True)),
 },
 "60m": {
   "orig": (U + " · day trade", Cfg("rev", "both", "both", "any", 30, "fast", "p3", daytrade=True)),
   "dt60": ("Day trade 1h: pullback com IFR + CDI", Cfg("trend", "both", "long", "against", 30, "both", "atr2", 0, 3, daytrade=True, cdi=True)),
   "sw60": ("Swing 1h: pullback compra/venda, stop 3×ATR + CDI", Cfg("trend", "both", "both", "against", 30, "slow", "atr3", 2, 1, cdi=True)),
 },
 "15m": {
   "orig": (U + " · day trade", Cfg("rev", "both", "both", "any", 30, "fast", "p3", daytrade=True)),
   "dt15": ("Day trade 15min: reversão IFR 50, candle contra", Cfg("rev", "fast", "both", "against", 50, "rsi", "none", 0, 1, daytrade=True, cdi=True)),
 },
 "5m": {
   "orig": (U + " · day trade", Cfg("rev", "both", "both", "any", 30, "fast", "p3", daytrade=True)),
   "dt5": ("Day trade 5min: tendência com IFR, stop 2%", Cfg("trend", "fast", "long", "any", 30, "both", "p2", 0, 1, daytrade=True, cdi=True)),
 },
}
TF_LABEL = {"1wk": "Semanal", "1d": "Diário", "60m": "1 hora", "15m": "15 min", "5m": "5 min"}

def bh(df, a, b):
    c = df.close.values; dv = df.dividends.values
    units = 1.0; v = []
    for i in range(a, b):
        if i > a and dv[i] > 0:
            units += units * dv[i] * .9 / c[i]
        v.append(units * c[i])
    v = np.array(v); return v / v[0] - 1

meta = {"tfs": {}, "metrics": []}
for tf, strats in STRATS.items():
    tickers = DAILY_T if tf in ("1d", "1wk") else INTRA_T
    meta["tfs"][tf] = dict(label=TF_LABEL[tf], tickers=tickers, strats={k: v[0] for k, v in strats.items()},
                           cfg={k: v[1].label() for k, v in strats.items()})
    for t in tickers:
        df = load_tf(t, tf); m = Market(df, tf); s = Sim(m); b = bounds_for(m)
        idx = df.index
        rows = dict(t=(idx.view("int64") // 10**9).tolist() if tf not in ("1d", "1wk") else [int(pd.Timestamp(x).timestamp()) for x in idx],
                    o=np.round(df.open.values, 2).tolist(), h=np.round(df.high.values, 2).tolist(),
                    l=np.round(df.low.values, 2).tolist(), c=np.round(df.close.values, 2).tolist(),
                    f=np.round(np.nan_to_num(m.f), 2).tolist(), s=np.round(np.nan_to_num(m.s), 2).tolist(),
                    r=np.round(np.nan_to_num(m.r, nan=50), 1).tolist(), start=int(b[0]), split=[int(x) for x in b])
        if tf not in ("1d", "1wk"):  # intradiário: horário local como se fosse UTC, para o eixo mostrar a hora do pregão
            rows["t"] = [int(pd.Timestamp(x).tz_localize("UTC").timestamp()) for x in idx]
        rows["strats"] = {}
        for key, (name, cfg) in strats.items():
            eq, nt, cost = s.run(cfg, i0=b[0])
            tr = s.trades(nt)
            sk, sv = stop_params(cfg)
            stp, tgt = [], []
            for _, x in tr.iterrows():
                d = x.entry_px * sv if sk == 1 else (m.atr[x.ei - 1] * sv if sk == 2 else 0)
                sg = 1 if x.side == "C" else -1
                stp.append(round(x.entry_px - sg * d, 2) if d else None)
                tgt.append(round(x.entry_px + sg * d * cfg.tp, 2) if d and cfg.tp else None)
            rows["strats"][key] = dict(
                eq=np.round(eq[::max(1, len(eq) // 700)], 0).tolist(), eqs=max(1, len(eq) // 700),
                tr=[[int(a), int(bb), sd, round(ep, 2), round(xp, 2), round(p, 0), round(r_ * 100, 2), w, st, tg]
                    for a, bb, sd, ep, xp, p, r_, w, st, tg in zip(tr.ei, tr.xi, tr.side, tr.entry_px, tr.exit_px, tr.pnl, tr.ret, tr.why, stp, tgt)])
            seg = s.seg(eq, nt, [x - b[0] for x in b])
            full = s.seg(eq, nt, [0, len(eq)])[0]
            tax = after_tax_total(tr, .20 if cfg.daytrade else .15)
            meta["metrics"].append(dict(tf=tf, ticker=t, key=key, final=float(eq[-1]), after_tax=float(eq[-1] - tax),
                cagr=float(full[1]), cdi=float(full[7]), dd=float(full[3]), trades=int(full[4]), win=float(full[5]) if full[4] else None,
                pf=float(full[6]) if not np.isnan(full[6]) else None, expo=float(full[8]),
                test_cagr=float(seg[2, 1]), test_cdi=float(seg[2, 7]), test_dd=float(seg[2, 3]),
                train_cagr=float(seg[0, 1]), val_cagr=float(seg[1, 1]), cost=float(cost)))
        bhv = bh(df, b[0], len(df))
        rows["bh"] = np.round(10000 * (1 + bhv[::max(1, len(bhv) // 700)]), 0).tolist()
        yrs = (idx[-1] - idx[b[0]]).days / 365.25
        meta["metrics"].append(dict(tf=tf, ticker=t, key="bh", final=float(10000 * (1 + bhv[-1])),
                                    cagr=float((1 + bhv[-1]) ** (1 / yrs) - 1) if yrs > 0.05 else None))
        json.dump(rows, open(f"{OUT}/{t}_{tf}.json", "w"), separators=(",", ":"))
    print(tf, "ok", flush=True)
json.dump(meta, open(f"{OUT}/meta.json", "w"), ensure_ascii=False, separators=(",", ":"))
