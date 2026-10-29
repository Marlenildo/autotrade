"""Exemplo com candles: compras da regra sem filtro x com filtro, PETR4."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from engine2 import *
from grid2 import bounds_for
from user_rule3 import sigs
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
UP, DN, MA1, MA2, AC, FG, MU, OR = "#18794e", "#b4332a", "#2f6fd6", "#a2489d", "#0b5d7a", "#13202a", "#5a6a77", "#b26b00"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#c9d3da", "xtick.color": MU, "ytick.color": MU})
m = Market(load_tf("PETR4", "1d"), "1d"); s = Sim(m); b = bounds_for(m); d = m.df
br = lambda v: f"R\\$ {v:.2f}".replace(".", ","); pc = lambda r: f"{r*100:+.1f}%".replace(".", ","); dt = lambda i: d.index[i].strftime("%d/%m")
def run(v):
    L, S, LX, SX = sigs(m, *v); S = np.zeros_like(S)
    eq, nt, _ = s.run(Cfg("trend", "both", "long", v[4], 0, "both", "none", cdi=True), i0=b[0], sig=(L, S, LX, SX)); return s.trades(nt)
t0 = run(("pct", 0, False, False, "with")); t1 = run(("pct", .5, False, True, "with"))
A, B = sys.argv[1], sys.argv[2]
a = d.index.searchsorted(pd.Timestamp(A)); bb = d.index.searchsorted(pd.Timestamp(B)) + 1
sl = slice(a, bb); x = np.arange(bb - a)
o, h, l, c = (d[k].values[sl] for k in ("open", "high", "low", "close"))
gap = (m.f - m.s) / d.close.values * 100
f = plt.figure(figsize=(7.4, 9.2), dpi=150)
gs = f.add_gridspec(4, 1, height_ratios=[3.2, 1.0, .12, 1.3], hspace=.12)
ax = f.add_subplot(gs[0]); ag = f.add_subplot(gs[1], sharex=ax); sp = f.add_subplot(gs[2]); sp.axis("off"); tx = f.add_subplot(gs[3]); tx.axis("off")
for i in x:
    col = UP if c[i] >= o[i] else DN
    ax.plot([i, i], [l[i], h[i]], color=col, lw=1.1, zorder=2)
    ax.add_patch(Rectangle((i - .32, min(o[i], c[i])), .64, max(abs(c[i] - o[i]), .01), color=col, zorder=3))
ax.plot(x, m.f[sl], color=MA1, lw=1.6, label="MM5"); ax.plot(x, m.s[sl], color=MA2, lw=1.6, label="MM10")
span = h.max() - l.min(); lines = []; n = 0; prev = -99; lvl = 0
w0 = t0[(t0.ei >= a) & (t0.ei < bb)]; keep = set(t1.ei)
for _, t in w0.iterrows():
    n += 1; E, X = t.ei - a, min(t.xi - a, x[-1]); kept = t.ei in keep; rc = UP if t.ret > 0 else DN
    ax.axvspan(E - .5, X - .5, color=rc if kept else MU, alpha=.10 if kept else .10, hatch=None if kept else "xx", ec=MU, lw=0, zorder=0)
    ax.annotate("", xy=(E - .4, t.entry_px), xytext=(E - .4, t.entry_px - span * .10), arrowprops=dict(arrowstyle="-|>", color=FG if kept else MU, lw=1.3, ls="-" if kept else "--"))
    ax.scatter([X - .4], [t.exit_px], marker="o", s=44, facecolor="white", edgecolor=rc, lw=2, zorder=8)
    lab = f"{n}\n{pc(t.ret)}" + ("" if kept else "\nfiltro evita")
    mid = (E + X) / 2 - .5; lvl = (1 - lvl) if mid - prev < 6 else 0; prev = mid
    ax.text(mid, h.max() + span * (.06 + .17 * lvl), lab, ha="center", va="bottom", fontsize=8.4, fontweight="bold", color=rc if kept else MU,
            bbox=dict(boxstyle="round,pad=.25", fc="white", ec=rc if kept else MU, lw=1, ls="-" if kept else "--"))
    q = t.ei - 1
    two = d.close.values[q - 1] > max(m.f[q - 1], m.s[q - 1])
    motivo = []
    if gap[q] < .5: motivo.append(f"MM5 só {gap[q]:.2f}% acima da MM10 (precisa 0,5%)".replace(".", ","))
    if not two: motivo.append("só 1 fechamento acima das médias (precisa 2)")
    if kept:
        txt = (f"{n}. Com e sem filtro: {dt(q)} MM5 {gap[q]:.1f}% acima da MM10, 2º fechamento acima das duas, candle verde → compra {dt(t.ei)} a {br(t.entry_px)}; "
               f"{dt(t.xi - 1)} fechou abaixo das duas → vende {dt(t.xi)} a {br(t.exit_px)}: {pc(t.ret)}").replace("1.", "1,", 0)
        txt = txt.replace(f"{gap[q]:.1f}%", f"{gap[q]:.1f}%".replace(".", ","))
    else:
        txt = f"{n}. Só sem filtro: compra {dt(t.ei)} a {br(t.entry_px)} → vende {dt(t.xi)} a {br(t.exit_px)}: {pc(t.ret)}. Filtro bloqueou: " + "; ".join(motivo)
    lines.append((txt, rc if kept else DN))
ax.set_title(f"Filtro em ação · PETR4 {d.index[a].strftime('%d/%m')}–{d.index[bb-1].strftime('%d/%m/%Y')} · só compra", loc="left", fontsize=12, fontweight="bold", color=FG, pad=10)
ax.legend(loc="upper left", frameon=False, fontsize=9); ax.grid(axis="y", color="#e6ebef"); ax.set_ylabel("R$")
ax.set_ylim(l.min() - span * .14, h.max() + span * .52); ax.tick_params(labelbottom=False)
g = gap[sl]
ag.bar(x, g, color=[UP if v >= .5 else (OR if v > 0 else DN) for v in g], width=.7)
ag.axhline(.5, color=FG, ls="--", lw=1); ag.text(x[-1] + .6, .5, "0,5%", va="center", fontsize=8, color=FG)
ag.axhline(0, color=MU, lw=.8)
ag.set_ylabel("MM5 − MM10\n(% do preço)", fontsize=8.5); ag.grid(axis="y", color="#e6ebef")
ag.set_xticks(x[::4]); ag.set_xticklabels([dt(i) for i in range(a, bb)][::4])
for s_ in (ax, ag):
    for k in ("top", "right"): s_.spines[k].set_visible(False)
tx.text(0, 1.04, "Caixas: resultado de cada compra. Contorno tracejado e faixa cinza xadrez = compra que só a regra sem filtro fez.\n"
                 "Barras de baixo: distância entre as médias. Verde = acima de 0,5% (filtro libera); laranja = médias coladas.",
        fontsize=7.8, color=MU, transform=tx.transAxes, va="top")
y = .80
import textwrap
for t_, col in lines:
    for k, part in enumerate(textwrap.wrap(t_, 118)):
        tx.text(0 if k == 0 else .02, y, part, fontsize=7.6, color=col, transform=tx.transAxes, va="top"); y -= .085
    y -= .03
f.savefig("report/exemplos/8_filtro_em_acao.png", bbox_inches="tight", facecolor="white"); print("ok")
print(w0[["entry", "exit", "ret"]].assign(kept=w0.ei.isin(keep)).to_string())
