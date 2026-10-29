"""Grade ampla em todos os timeframes e ativos.
Saída: results/grid2/<ticker>_<tf>[_dt].parquet com uma linha por configuração e
métricas de treino / validação / teste.
"""
import sys, os, time, itertools
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
from engine2 import *

DAILY_T = ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "WEGE3", "MGLU3", "B3SA3", "PRIO3", "BOVA11"]
INTRA_T = ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "BOVA11", "PRIO3", "WEGE3"]
SEGS = ["treino", "validacao", "teste"]
MET = ["ret", "cagr", "sharpe", "dd", "trades", "acerto", "pf", "cdi", "expo"]


def bounds_for(m: Market):
    idx = m.df.index
    if m.tf in ("1d", "1wk"):
        a = idx.searchsorted(pd.Timestamp("2012-01-01"))
        return [a, idx.searchsorted(pd.Timestamp("2020-01-01")), idx.searchsorted(pd.Timestamp("2023-01-01")), len(idx)]
    # intradiário: corta por dia de pregão em 50% / 25% / 25%, depois de 1 dia de aquecimento
    days = idx.normalize().unique()
    d1 = days[1]; n = len(days) - 1
    cut = lambda f: idx.searchsorted(days[1 + int(n * f)])
    return [idx.searchsorted(d1), cut(.5), cut(.75), len(idx)]


def job(args):
    ticker, tf, daytrade = args
    out = f"results/grid2/{ticker}_{tf}{'_dt' if daytrade else ''}.parquet"
    if os.path.exists(out):
        return out
    m = Market(load_tf(ticker, tf), tf)
    s = Sim(m)
    b = bounds_for(m)
    rows = []
    base = itertools.product(["trend", "rev"], ["fast", "slow", "both", "either"], ["long", "short", "both"],
                             ["any", "with", "against"], [0, 30, 40, 50], ["fast", "slow", "both", "either", "rsi"])
    for mode, eref, side, cand, rsi, xref in base:
        c0 = Cfg(mode, eref, side, cand, rsi, xref, daytrade=daytrade)
        sig = signals(m, c0)
        if not (sig[0][b[0]:].any() or sig[1][b[0]:].any()):
            continue
        for stop, tp, units, cdi in itertools.product(["none", "p1", "p2", "p3", "p5", "atr1", "atr2", "atr3"], [0, 2], [1, 3], [False, True]):
            if tp and stop == "none":
                continue
            cfg = Cfg(mode, eref, side, cand, rsi, xref, stop, tp, units, daytrade, cdi)
            eq, nt, _ = s.run(cfg, i0=b[0], sig=sig)
            seg = s.seg(eq, nt, [x - b[0] for x in b])
            rows.append((mode, eref, side, cand, rsi, xref, stop, tp, units, cdi, *seg.ravel()))
    cols = ["mode", "entry_ref", "side", "candle", "rsi_th", "exit_ref", "stop", "tp", "units", "cdi"] + \
           [f"{p}_{k}" for p in SEGS for k in MET]
    df = pd.DataFrame(rows, columns=cols)
    df.to_parquet(out, index=False)
    return out


if __name__ == "__main__":
    os.makedirs("results/grid2", exist_ok=True)
    jobs = [(t, tf, False) for tf in ("1d", "1wk") for t in DAILY_T] + \
           [(t, "60m", dt) for t in INTRA_T for dt in (True, False)] + \
           [(t, tf, True) for tf in ("15m", "5m") for t in INTRA_T]
    if len(sys.argv) > 1:
        jobs = [j for j in jobs if j[0] == sys.argv[1]]
    t0 = time.time()
    with Pool(2) as p:
        for i, r in enumerate(p.imap_unordered(job, jobs)):
            print(f"{i+1}/{len(jobs)} {r} {time.time()-t0:.0f}s", flush=True)
