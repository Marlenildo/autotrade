"""Regra pura do usuário na PETR4: cruzamento dá a direção, primeiro fechamento fora das duas médias entra,
fechamento do outro lado das duas sai. Sem filtros."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from engine2 import *
from grid2 import bounds_for
import user_rule2
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
UP, DN, AC, FG, MU, OR = "#18794e", "#b4332a", "#0b5d7a", "#13202a", "#5a6a77", "#b26b00"
m = Market(load_tf("PETR4", "1d"), "1d"); s = Sim(m); b = bounds_for(m); idx = m.df.index[b[0]:]
def run(side, cdi):
    L, S, LX, SX = user_rule2.sigs(m, "duas", "any")
    if side == "long": S = np.zeros_like(S)
    eq, nt, _ = s.run(Cfg("trend", "both", side, "any", 0, "both", "none", cdi=cdi, reverse=side == "both"), i0=b[0], sig=(L, S, LX, SX))
    return eq
c = m.df.close.values[b[0]:]; dv = m.df.dividends.values[b[0]:]; u = 1.0; bh = []
for i in range(len(c)):
    if i and dv[i] > 0: u += u * dv[i] * .9 / c[i]
    bh.append(u * c[i])
bh = np.array(bh) / bh[0] * 10000
cdi = np.cumprod(1 + m.cdi[b[0]:] * .85) * 10000
S = [("Compra e venda (sua regra)", run("both", False), DN, 1.6), ("Compra e venda + CDI no caixa", run("both", True), "#e08a80", 1.1),
     ("Só compra + CDI no caixa", run("long", True), AC, 2.2), ("Comprar e segurar", bh, MU, 1.0), ("CDI líquido", cdi, UP, 1.0)]
f, (ax, ad) = plt.subplots(2, 1, figsize=(7.4, 6.8), dpi=150, sharex=True, gridspec_kw=dict(height_ratios=[2.4, 1], hspace=.08))
for name, eq, col, lw in S:
    ls = "--" if name.startswith("CDI") else ":" if name.startswith("Comprar") else "-"
    ax.plot(idx, eq, color=col, lw=lw, ls=ls, label=f"{name}: R$ {eq[-1]/1000:.1f} mil".replace(".", ","))
    if not name.startswith("CDI"):
        ad.plot(idx, (eq / np.maximum.accumulate(eq) - 1) * 100, color=col, lw=lw * .6, ls=ls)
for a_ in (ax, ad):
    a_.axvspan(pd.Timestamp("2023-01-01"), idx[-1], color=OR, alpha=.07)
    for k in ("top", "right"): a_.spines[k].set_visible(False)
    a_.grid(axis="y", color="#e6ebef")
ax.set_yscale("log"); ax.set_yticks([3000, 5000, 10000, 20000, 50000, 100000]); ax.set_yticklabels(["3 mil", "5 mil", "10 mil", "20 mil", "50 mil", "100 mil"])
ax.legend(loc="upper left", frameon=False, fontsize=8.2)
ax.set_title("Sua regra, sem filtros · PETR4 · R$ 10 mil em 2012", loc="left", fontsize=12, fontweight="bold", color=FG, pad=10)
ax.annotate("2023–26", (pd.Timestamp("2023-03-01"), 4000), fontsize=8, color=OR)
ad.set_ylabel("Queda desde o topo (%)"); ax.set_ylabel("Patrimônio (escala log)")
f.savefig("report/exemplos/9_regra_pura_petr4.png", bbox_inches="tight", facecolor="white"); print("ok")
