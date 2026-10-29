"""Regra v2 + filtros contra cruzamento falso.
Direção pelo cruzamento MM5 x MM10, gatilho pelo candle fora das duas médias, saída quando o candle
fecha do outro lado das duas. Filtros só na ENTRADA:
- gap: distância mínima entre MM5 e MM10 (em % do preço ou em múltiplos do ATR);
- slope: MM10 subindo (compra) / caindo (venda) em relação a 3 candles antes;
- conf: dois fechamentos seguidos fora das médias.
Seleção feita só com treino (2012–19) + validação (2020–22); teste 2023–26 só para conferir."""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(__file__))
from engine2 import *
from grid2 import DAILY_T, bounds_for

def sigs(m, gap_kind, gap, slope, conf, candle):
    bull, bear = m.f > m.s, m.f < m.s
    above, below = m.af & m.as_, m.bf & m.bs
    dist = np.abs(m.f - m.s)
    ok = np.ones(len(dist), bool) if gap == 0 else (dist / m.c.values * 100 >= gap if gap_kind == "pct" else dist >= gap * m.atr)
    L = bull & above & ok & m.valid; S = bear & below & ok & m.valid
    if slope:
        s10 = pd.Series(m.s); L &= (s10 > s10.shift(3)).values; S &= (s10 < s10.shift(3)).values
    if conf:
        L &= np.r_[False, above[:-1]]; S &= np.r_[False, below[:-1]]
    if candle == "with":
        L &= m.green; S &= m.red
    return L, S, below, above

FILTERS = [("pct", g) for g in (0, .25, .5, .75, 1, 1.5, 2)] + [("atr", k) for k in (.1, .2, .3, .5, .75)]
GRID = [(gk, g, sl, cf, cd, side) for (gk, g) in FILTERS for sl in (False, True) for cf in (False, True)
        for cd in ("any", "with") for side in ("both", "long")]

def run_all(tickers=DAILY_T, tf="1d", cdi=True):
    rows = []
    for t in tickers:
        m = Market(load_tf(t, tf), tf); s = Sim(m); b = bounds_for(m)
        for gk, g, sl, cf, cd, side in GRID:
            L, S, LX, SX = sigs(m, gk, g, sl, cf, cd)
            if side == "long":
                S = np.zeros_like(S)
            cfg = Cfg("trend", "both", side, cd, 0, "both", "none", cdi=cdi, reverse=(side == "both"))
            eq, nt, cost = s.run(cfg, i0=b[0], sig=(L, S, LX, SX))
            seg = s.seg(eq, nt, [x - b[0] for x in b]); full = s.seg(eq, nt, [0, len(eq)])[0]
            rows.append(dict(ticker=t, gk=gk, gap=g, slope=sl, conf=cf, candle=cd, side=side, final=eq[-1],
                             cagr=full[1], cdi_c=full[7], dd=full[3], trades=full[4], win=full[5],
                             tr_x=seg[0, 1] - seg[0, 7], va_x=seg[1, 1] - seg[1, 7], te_x=seg[2, 1] - seg[2, 7],
                             te_cagr=seg[2, 1], te_dd=seg[2, 3], cost=cost))
    return pd.DataFrame(rows)

if __name__ == "__main__":
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
    df = run_all(); df.to_csv("results/regra_usuario_v3.csv", index=False)
    K = ["side", "gk", "gap", "slope", "conf", "candle"]
    g = df.groupby(K).agg(final=("final", "median"), cagr=("cagr", "median"), exc=("cagr", lambda x: 0), dd=("dd", "median"),
                          trades=("trades", "median"), win=("win", "median"), tr_x=("tr_x", "median"), va_x=("va_x", "median"),
                          te_x=("te_x", "median"), te_beat=("te_x", lambda x: (x > 0).mean()), tv_beat=("va_x", lambda x: (x > 0).mean()))
    g["exc"] = df.groupby(K).apply(lambda x: (x.cagr - x.cdi_c).median())
    g["sel"] = g[["tr_x", "va_x"]].min(axis=1)  # critério de escolha: pior entre treino e validação
    for side in ("both", "long"):
        gg = g.loc[side].sort_values("sel", ascending=False)
        print(f"\n===== {side}: base sem filtro")
        print(gg.loc[[("pct", 0, False, False, "any"), ("pct", 0, False, False, "with")]].round(3).to_string())
        print(f"===== {side}: top 12 pelo pior de treino/validação")
        print(gg.head(12).round(3).to_string())
    # efeito isolado da distância mínima (sem outros filtros, candle qualquer)
    print("\n===== efeito da distância mínima (pct), candle qualquer, sem slope/conf")
    print(g.xs(("pct", False, False, "any"), level=["gk", "slope", "conf", "candle"]).round(3)[["final", "cagr", "exc", "dd", "trades", "win", "tr_x", "va_x", "te_x", "te_beat"]].to_string())
