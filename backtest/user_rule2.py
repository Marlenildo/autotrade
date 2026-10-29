"""Regra do usuário (v2): o cruzamento MM5 x MM10 define a direção; o candle dá o gatilho.
- MM5 > MM10 (após cruzar para cima): compra quando o candle fecha acima das duas médias.
- MM5 < MM10 (após cruzar para baixo): vende quando o candle fecha abaixo das duas médias.
- Encerra quando o candle fecha do outro lado (variações: das duas / de qualquer uma / da MM5).
- Ao encerrar, pode entrar de novo na mesma direção ou na oposta (vira a mão se houver sinal oposto).
"""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(__file__))
from engine2 import *
from grid2 import DAILY_T, INTRA_T, bounds_for

def sigs(m: Market, exit_kind: str, candle: str):
    bull, bear = m.f > m.s, m.f < m.s
    cv = m.c.values
    above, below = m.af & m.as_, m.bf & m.bs
    L = bull & above & m.valid; S = bear & below & m.valid
    if candle == "with":
        L &= m.green; S &= m.red
    LX = {"duas": below, "uma": m.bf | m.bs, "mm5": m.bf}[exit_kind]
    SX = {"duas": above, "uma": m.af | m.as_, "mm5": m.af}[exit_kind]
    return L, S, LX, SX

VARS = list(itertools.product(["duas", "uma", "mm5"], ["any", "with"], ["both", "long"], ["none", "p3"], [False, True]))
if __name__ == "__main__":
    rows = []
    for tf, dtf, ticks in [("1d", False, DAILY_T), ("1wk", False, DAILY_T), ("60m", False, INTRA_T), ("60m", True, INTRA_T), ("15m", True, INTRA_T), ("5m", True, INTRA_T)]:
        for t in ticks:
            m = Market(load_tf(t, tf), tf); s = Sim(m); b = bounds_for(m)
            for ex, cand, side, stop, cdi in VARS:
                L, S, LX, SX = sigs(m, ex, cand)
                if side == "long":
                    S = np.zeros_like(S)
                cfg = Cfg("trend", "both", side, cand, 0, "both", stop, cdi=cdi, reverse=(side == "both"), daytrade=dtf)
                eq, nt, cost = s.run(cfg, i0=b[0], sig=(L, S, LX, SX))
                full = s.seg(eq, nt, [0, len(eq)])[0]; seg = s.seg(eq, nt, [x - b[0] for x in b])
                rows.append(dict(tf=tf + ("_dt" if dtf else ""), ticker=t, saida=ex, candle=cand, lado=side, stop=stop, cdi=cdi,
                                 final=eq[-1], cagr=full[1], cdi_cagr=full[7], dd=full[3], trades=full[4], win=full[5],
                                 tr_cagr=seg[0, 1], va_cagr=seg[1, 1], te_cagr=seg[2, 1], te_cdi=seg[2, 7], cost=cost))
    df = pd.DataFrame(rows); df.to_csv("results/regra_usuario_v2.csv", index=False)
    df["exc"] = df.cagr - df.cdi_cagr; df["te_exc"] = df.te_cagr - df.te_cdi
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 500)
    g = df.groupby(["tf", "lado", "saida", "candle", "stop", "cdi"]).agg(final=("final", "median"), cagr=("cagr", "median"), exc=("exc", "median"),
          te_exc=("te_exc", "median"), dd=("dd", "median"), trades=("trades", "median"), win=("win", "median"),
          bateu=("te_exc", lambda x: (x > 0).mean()), quebrou=("final", lambda x: (x < 5000).mean()))
    print(g[g.index.get_level_values("tf").isin(["1d", "1wk"])].round(3).to_string())
    print(g[~g.index.get_level_values("tf").isin(["1d", "1wk"])].query("cdi == True and stop == 'none'").round(3).to_string())
    p = df[(df.ticker == "PETR4") & (df.tf == "1d") & (df.stop == "none")]
    print(p[["lado", "saida", "candle", "cdi", "final", "cagr", "dd", "trades", "win", "cost"]].round(3).to_string())
