"""Regra do usuário, exata: fechou abaixo das duas médias -> sinal; acima das duas -> sinal contrário;
encerra quando fecha do outro lado das duas (e vira a mão). Variações: sentido, IFR, stop, só compra, CDI."""
import sys, os, itertools, json
sys.path.insert(0, os.path.dirname(__file__))
from engine2 import *
from grid2 import DAILY_T, INTRA_T, bounds_for
VAR = []
for mode, rsi, stop, cdi in itertools.product(["rev", "trend"], [0, 30], ["none", "p3"], [False, True]):
    VAR.append(("compra e venda, vira a mão", Cfg(mode, "both", "both", "any", rsi, "both", stop, cdi=cdi, reverse=True)))
    VAR.append(("só compra", Cfg(mode, "both", "long", "any", rsi, "both", stop, cdi=cdi)))
rows = []
for tf, dtf, ticks in [("1d", False, DAILY_T), ("1wk", False, DAILY_T), ("60m", False, INTRA_T), ("60m", True, INTRA_T), ("15m", True, INTRA_T), ("5m", True, INTRA_T)]:
    for t in ticks:
        m = Market(load_tf(t, tf), tf); s = Sim(m); b = bounds_for(m)
        for kind, c0 in VAR:
            cfg = replace(c0, daytrade=dtf)
            eq, nt, cost = s.run(cfg, i0=b[0]); tr = s.trades(nt)
            full = s.seg(eq, nt, [0, len(eq)])[0]; seg = s.seg(eq, nt, [x - b[0] for x in b])
            rows.append(dict(tf=tf + ("_dt" if dtf else ""), ticker=t, kind=kind, mode=cfg.mode, rsi=cfg.rsi_th, stop=cfg.stop, cdi=cfg.cdi,
                             final=eq[-1], cagr=full[1], cdi_cagr=full[7], dd=full[3], trades=full[4], win=full[5],
                             test_cagr=seg[2, 1], test_cdi=seg[2, 7], cost=cost))
df = pd.DataFrame(rows); df.to_csv("results/regra_usuario.csv", index=False)
df["exc"] = df.cagr - df.cdi_cagr; df["test_exc"] = df.test_cagr - df.test_cdi
pd.set_option("display.width", 250)
g = df.groupby(["tf", "kind", "mode", "rsi", "stop", "cdi"]).agg(final=("final", "median"), cagr=("cagr", "median"), exc=("exc", "median"),
      test_exc=("test_exc", "median"), dd=("dd", "median"), trades=("trades", "median"), win=("win", "median"),
      beat=("test_exc", lambda x: (x > 0).mean()), quebrou=("final", lambda x: (x < 5000).mean()))
print(g.round(3).to_string())
print(df[(df.ticker == "PETR4") & (df.tf == "1d")][["kind", "mode", "rsi", "stop", "cdi", "final", "cagr", "dd", "trades", "win", "cost"]].round(3).to_string())
