"""Acertos e erros da regra F (só compra + médias afastadas 0,5% + 2 fechamentos + candle verde) na PETR4."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from engine2 import *
from grid2 import bounds_for
from user_rule3 import sigs
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
UP, DN, MA1, MA2, AC, FG, MU = "#18794e", "#b4332a", "#2f6fd6", "#a2489d", "#0b5d7a", "#13202a", "#5a6a77"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#c9d3da", "xtick.color": MU, "ytick.color": MU})
T = sys.argv[1] if len(sys.argv) > 1 else "PETR4"
m = Market(load_tf(T, "1d"), "1d"); s = Sim(m); b = bounds_for(m); d = m.df
L, S, LX, SX = sigs(m, "pct", .5, False, True, "with"); S = np.zeros_like(S)
eq, nt, _ = s.run(Cfg("trend", "both", "long", "with", 0, "both", "none", cdi=True), i0=b[0], sig=(L, S, LX, SX))
t = s.trades(nt); t["dur"] = t.xi - t.ei
W, Lo = t[t.ret > 0], t[t.ret <= 0]
pc = lambda r: f"{r*100:+.1f}%".replace(".", ",")
# ---------- 1) história completa
f = plt.figure(figsize=(7.4, 8.4), dpi=150)
gs = f.add_gridspec(3, 1, height_ratios=[2.2, 1.5, .9], hspace=.12)
ax = f.add_subplot(gs[0]); ar = f.add_subplot(gs[1], sharex=ax); tx = f.add_subplot(gs[2]); tx.axis("off")
idx = d.index[b[0]:]
ax.plot(idx, d.close.values[b[0]:], color=FG, lw=.8)
for _, x in t.iterrows():
    ax.axvspan(x.entry, x.exit, color=UP if x.ret > 0 else DN, alpha=.28, lw=0)
ax.set_yscale("log"); ax.set_ylabel("Preço (R$, log)")
ax.yaxis.set_major_locator(matplotlib.ticker.LogLocator(base=10, subs=(1, 2, 5))); ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",")))
ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
ax.set_title(f"Acertos e erros · regra F · {T} 2012–2026", loc="left", fontsize=12.5, fontweight="bold", color=FG, pad=10)
ax.text(.0, 1.0, "faixa verde = operação com lucro · vermelha = com prejuízo · branco = fora, no CDI", transform=ax.transAxes, fontsize=8, color=MU, va="bottom")
cols = [UP if r > 0 else DN for r in t.ret]
ar.bar(t.entry + (t.exit - t.entry) / 2, t.ret * 100, width=18, color=cols)
ar.axhline(0, color=MU, lw=.8)
for _, x in t.nlargest(3, "ret").iterrows():
    ar.text(x.entry, x.ret * 100 + 1, pc(x.ret), fontsize=7.5, color=UP, ha="center", va="bottom")
for _, x in t.nsmallest(2, "ret").iterrows():
    ar.text(x.entry, x.ret * 100 - 1, pc(x.ret), fontsize=7.5, color=DN, ha="center", va="top")
ar.set_ylabel("Resultado de cada\noperação (%)"); ar.grid(axis="y", color="#e6ebef")
ar.set_ylim(min(t.ret.min() * 100 * 1.4, -15), t.ret.max() * 100 * 1.2)
for s_ in (ax, ar):
    for k in ("top", "right"): s_.spines[k].set_visible(False)
br = lambda v: f"R\\$ {v:,.0f}".replace(",", ".")
lines = [
    (f"{len(t)} operações · {len(W)} acertos ({len(W)/len(t)*100:.0f}%) · {len(Lo)} erros ({len(Lo)/len(t)*100:.0f}%)", FG),
    (f"Acerto médio {pc(W.ret.mean())}  ·  erro médio {pc(Lo.ret.mean())}  ·  um acerto paga {W.ret.mean()/-Lo.ret.mean():.1f} erros".replace(".", ","), FG),
    (f"Acertos duram {W.dur.median():.0f} pregões na mediana; erros, {Lo.dur.median():.0f}  ·  maior sequência de erros: {max(len(list(g)) for k, g in __import__('itertools').groupby(t.ret > 0) if not k)} seguidos", FG),
    (f"R\\$ 10 mil em 2012 → {br(eq[-1])} em 29/10/2026 (com CDI no caixa)", AC),
]
y = .95
for txt, c in lines:
    tx.text(0, y, txt, fontsize=9, color=c, transform=tx.transAxes, va="top", fontweight="bold" if c == AC else "normal"); y -= .24
f.savefig(f"report/exemplos/10_acertos_erros_{T}.png", bbox_inches="tight", facecolor="white"); plt.close(f)
# ---------- 2) candles dos últimos meses
a = d.index.searchsorted(pd.Timestamp(sys.argv[2] if len(sys.argv) > 2 else "2026-03-02")); bb = len(d)
sl = slice(a, bb); x = np.arange(bb - a)
o, h, l, c = (d[k].values[sl] for k in ("open", "high", "low", "close"))
f, ax = plt.subplots(figsize=(7.4, 5.4), dpi=150)
for i in x:
    col = UP if c[i] >= o[i] else DN
    ax.plot([i, i], [l[i], h[i]], color=col, lw=.9, alpha=.8)
    ax.add_patch(Rectangle((i - .33, min(o[i], c[i])), .66, max(abs(c[i] - o[i]), .01), color=col, alpha=.8))
ax.plot(x, m.f[sl], color=MA1, lw=1.3, label="MM5"); ax.plot(x, m.s[sl], color=MA2, lw=1.3, label="MM10")
span = h.max() - l.min(); prev = -99; lvl = 0
w = t[t.xi >= a]
for n, (_, z) in enumerate(w.iterrows(), 1):
    E, X = max(z.ei - a, 0), z.xi - a; win = z.ret > 0; rc = UP if win else DN
    ax.axvspan(E - .5, X - .5 if z.why != "fim" else X + .5, color=rc, alpha=.14, lw=0)
    ax.scatter([E - .4], [z.entry_px], marker="^", s=40, color=FG, zorder=6)
    ax.scatter([X - .4 if z.why != "fim" else X], [z.exit_px], marker="o", s=36, facecolor="white", edgecolor=rc, lw=2, zorder=7)
    mid = (E + X) / 2 - .5; lvl = (1 - lvl) if mid - prev < 14 else 0; prev = mid
    lab = ("✓ " if win else "✗ ") + pc(z.ret) + (" aberta" if z.why == "fim" else "")
    ax.text(mid, h.max() + span * (.05 + .10 * lvl), lab, ha="center", va="bottom", fontsize=8.3, fontweight="bold", color=rc,
            bbox=dict(boxstyle="round,pad=.22", fc="white", ec=rc, lw=1))
ax.set_ylim(l.min() - span * .05, h.max() + span * .36)
step = max(1, len(x) // 9)
ax.set_xticks(x[::step]); ax.set_xticklabels([d.index[i].strftime("%d/%m") for i in range(a, bb)][::step])
ax.legend(loc="lower right", frameon=False, fontsize=8.5); ax.grid(axis="y", color="#e6ebef"); ax.set_ylabel("R$")
for k in ("top", "right"): ax.spines[k].set_visible(False)
nw, nl = int((w.ret > 0).sum()), int((w.ret <= 0).sum())
ax.set_title(f"Regra F · {T} {d.index[a].strftime('%d/%m/%Y')}–{d.index[-1].strftime('%d/%m/%Y')} · {nw} acertos, {nl} erros", loc="left", fontsize=12, fontweight="bold", color=FG, pad=10)
f.savefig(f"report/exemplos/11_candles_acertos_{T}.png", bbox_inches="tight", facecolor="white")
print(len(t), len(W), len(Lo)); print(w[["entry", "exit", "entry_px", "exit_px", "ret", "why"]].to_string())
