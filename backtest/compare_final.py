"""Comparação final: regra pura do usuário x cada filtro isolado x combinação, 11 ativos, diário, caixa no CDI."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from engine2 import *
from grid2 import DAILY_T, bounds_for
from user_rule3 import sigs
C = [("A. Pura, compra e venda", ("pct", 0, False, False, "any"), "both"),
     ("B. Pura, só compra", ("pct", 0, False, False, "any"), "long"),
     ("C. Só compra + médias afastadas 0,5%", ("pct", .5, False, False, "any"), "long"),
     ("D. Só compra + 2 fechamentos", ("pct", 0, False, True, "any"), "long"),
     ("E. Só compra + candle verde", ("pct", 0, False, False, "with"), "long"),
     ("F. Só compra + os três filtros", ("pct", .5, False, True, "with"), "long"),
     ("G. Compra e venda + os três filtros", ("pct", .5, False, True, "with"), "both")]
rows = []
for t in DAILY_T:
    m = Market(load_tf(t, "1d"), "1d"); s = Sim(m); b = bounds_for(m)
    for name, v, side in C:
        L, S, LX, SX = sigs(m, *v)
        if side == "long": S = np.zeros_like(S)
        eq, nt, cost = s.run(Cfg("trend", "both", side, v[4], 0, "both", "none", cdi=True, reverse=side == "both"), i0=b[0], sig=(L, S, LX, SX))
        tr = s.trades(nt); full = s.seg(eq, nt, [0, len(eq)])[0]; seg = s.seg(eq, nt, [x - b[0] for x in b])
        rows.append(dict(ticker=t, v=name, final=eq[-1], cagr=full[1], dd=full[3], trades=full[4], win=full[5], pf=full[6],
                         trn=seg[0, 1] - seg[0, 7], val=seg[1, 1] - seg[1, 7], tst=seg[2, 1] - seg[2, 7], tst_dd=seg[2, 3],
                         after_tax=eq[-1] - after_tax_total(tr, .15), cost=cost))
df = pd.DataFrame(rows); df.to_csv("results/comparacao_final.csv", index=False)
df["calmar"] = df.cagr / -df.dd
pd.set_option("display.width", 250)
g = df.groupby("v").agg(final=("final", "median"), apos_ir=("after_tax", "median"), cagr=("cagr", "median"), dd=("dd", "median"), calmar=("calmar", "median"),
                        trades=("trades", "median"), acerto=("win", "median"), trn=("trn", "median"), val=("val", "median"), tst=("tst", "median"),
                        tst_dd=("tst_dd", "median"), bateu_cdi_teste=("tst", lambda x: int((x > 0).sum())), periodos_pos=("trn", lambda x: 0))
g["periodos_pos"] = [sum(int(g.loc[i, k] > 0) for k in ("trn", "val", "tst")) for i in g.index]
pure = df[df.v == "B. Pura, só compra"].set_index("ticker")
for name, *_ in C:
    x = df[df.v == name].set_index("ticker")
    g.loc[name, "vence_B_total"] = int((x.final > pure.final).sum()); g.loc[name, "vence_B_teste"] = int((x.tst > pure.tst).sum())
    g.loc[name, "menor_queda_que_B"] = int((x.dd > pure.dd).sum())
print(g.round(3).to_string())
print(df.pivot(index="ticker", columns="v", values="final").round(-2).astype(int).to_string())
