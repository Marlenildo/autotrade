import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from engine2 import *
from grid2 import DAILY_T, bounds_for
from user_rule3 import sigs
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
UP, DN, AC, FG, MU, OR = "#18794e", "#b4332a", "#0b5d7a", "#13202a", "#5a6a77", "#b26b00"
VERS = [("Compra e venda, sem filtro", ("pct", 0, False, False, "any"), "both", DN, 1.3),
        ("Só compra, sem filtro", ("pct", 0, False, False, "with"), "long", MU, 1.3),
        ("Só compra + filtro", ("pct", .5, False, True, "with"), "long", AC, 2.2)]
def runv(t, v):
    m = Market(load_tf(t, "1d"), "1d"); s = Sim(m); b = bounds_for(m)
    L, S, LX, SX = sigs(m, *v[1])
    if v[2] == "long": S = np.zeros_like(S)
    eq, nt, cost = s.run(Cfg("trend", "both", v[2], v[1][4], 0, "both", "none", cdi=True, reverse=v[2] == "both"), i0=b[0], sig=(L, S, LX, SX))
    tr = s.trades(nt); full = s.seg(eq, nt, [0, len(eq)])[0]; seg = s.seg(eq, nt, [x - b[0] for x in b])
    return m, b, eq, tr, full, seg
rows = []
for t in DAILY_T:
    for v in VERS:
        m, b, eq, tr, full, seg = runv(t, v)
        rows.append(dict(ticker=t, v=v[0], final=eq[-1], cagr=full[1], dd=full[3], trades=full[4], win=full[5],
                         te_x=seg[2, 1] - seg[2, 7], tr_x=seg[0, 1] - seg[0, 7], va_x=seg[1, 1] - seg[1, 7]))
df = pd.DataFrame(rows); df.to_csv("results/filtro_validacao.csv", index=False)
pd.set_option("display.width", 220)
print(df.pivot(index="ticker", columns="v", values="te_x").round(3))
print(df.pivot(index="ticker", columns="v", values="dd").round(2))
print(df.groupby("v")[["final", "cagr", "dd", "trades", "win", "tr_x", "va_x", "te_x"]].median().round(3))
print(df.groupby("v").te_x.apply(lambda x: (x > 0).sum()))
print(df[df.ticker == "PETR4"].round(3).to_string())
# gráfico PETR4
f, (ax, ad) = plt.subplots(2, 1, figsize=(7.4, 6.6), dpi=150, sharex=True, gridspec_kw=dict(height_ratios=[2.4, 1], hspace=.08))
for v in VERS:
    m, b, eq, tr, full, seg = runv("PETR4", v)
    idx = m.df.index[b[0]:]
    ax.plot(idx, eq, color=v[3], lw=v[4], label=f"{v[0]}: R$ {eq[-1]/1000:.1f} mil".replace(".", ","))
    ad.plot(idx, (eq / np.maximum.accumulate(eq) - 1) * 100, color=v[3], lw=v[4] * .7)
cdi = np.cumprod(1 + m.cdi[b[0]:] * .85) * 10000
ax.plot(idx, cdi, color=UP, lw=1, ls="--", label=f"CDI líquido: R$ {cdi[-1]/1000:.1f} mil".replace(".", ","))
for a_ in (ax, ad):
    a_.axvspan(pd.Timestamp("2023-01-01"), idx[-1], color=OR, alpha=.07)
    for k in ("top", "right"): a_.spines[k].set_visible(False)
    a_.grid(axis="y", color="#e6ebef")
ax.text(pd.Timestamp("2023-02-01"), ax.get_ylim()[1] * .02 if False else 1, "", fontsize=8)
ax.set_yscale("log"); ax.set_yticks([5000, 10000, 20000, 50000, 100000]); ax.set_yticklabels(["5 mil", "10 mil", "20 mil", "50 mil", "100 mil"])
ax.legend(loc="upper left", frameon=False, fontsize=8.3)
ax.set_title("Sua regra na PETR4 · R$ 10 mil em 2012 · com e sem filtro", loc="left", fontsize=12, fontweight="bold", color=FG, pad=10)
ax.annotate("2023–26: teste\n(fora da escolha)", (pd.Timestamp("2023-03-01"), 6000), fontsize=8, color=OR)
ad.set_ylabel("Queda desde o topo (%)"); ax.set_ylabel("Patrimônio (escala log)")
f.savefig("report/exemplos/7_filtro_petr4.png", bbox_inches="tight", facecolor="white"); print("ok")
