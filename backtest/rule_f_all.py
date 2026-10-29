"""Regra F em todos os ativos: tabela de acertos/erros, painel de curvas e comparação de timeframes."""
import sys, os, itertools
sys.path.insert(0, os.path.dirname(__file__))
from engine2 import *
from grid2 import DAILY_T, INTRA_T, bounds_for
from user_rule3 import sigs
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt; import matplotlib.dates
UP, DN, AC, FG, MU = "#18794e", "#b4332a", "#0b5d7a", "#13202a", "#5a6a77"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": "#c9d3da", "xtick.color": MU, "ytick.color": MU})
def runF(t, tf, daytrade=False):
    m = Market(load_tf(t, tf), tf); s = Sim(m); b = bounds_for(m)
    L, S, LX, SX = sigs(m, "pct", .5, False, True, "with"); S = np.zeros_like(S)
    eq, nt, cost = s.run(Cfg("trend", "both", "long", "with", 0, "both", "none", cdi=True, daytrade=daytrade), i0=b[0], sig=(L, S, LX, SX))
    tr = s.trades(nt); tr["dur"] = tr.xi - tr.ei
    full = s.seg(eq, nt, [0, len(eq)])[0]; seg = s.seg(eq, nt, [x - b[0] for x in b])
    c = m.df.close.values[b[0]:]; dv = m.df.dividends.values[b[0]:]; u = 1.0; bh = []
    for i in range(len(c)):
        if i and dv[i] > 0: u += u * dv[i] * .9 / c[i]
        bh.append(u * c[i])
    bh = np.array(bh) / bh[0] * 1e4; cdi = np.cumprod(1 + m.cdi[b[0]:] * .85) * 1e4
    return m, b, eq, tr, full, seg, bh, cdi, cost
rows = []; curves = {}
for t in DAILY_T:
    m, b, eq, tr, full, seg, bh, cdi, cost = runF(t, "1d")
    W, Lo = tr[tr.ret > 0], tr[tr.ret <= 0]
    streak = max((len(list(g)) for k, g in itertools.groupby(tr.ret > 0) if not k), default=0)
    rows.append(dict(ativo=t, ops=len(tr), acertos=len(W), erros=len(Lo), taxa=len(W) / len(tr), acerto_medio=W.ret.mean(), erro_medio=Lo.ret.mean(),
                     maior_ganho=tr.ret.max(), maior_perda=tr.ret.min(), seq_erros=streak, dur_acerto=W.dur.median(), dur_erro=Lo.dur.median(),
                     final=eq[-1], apos_ir=eq[-1] - after_tax_total(tr, .15), cdi=cdi[-1], bh=bh[-1], cagr=full[1], queda=full[3], queda_bh=(bh / np.maximum.accumulate(bh) - 1).min(),
                     teste_exc=seg[2, 1] - seg[2, 7], tempo_posicionado=full[8], custos=cost))
    curves[t] = (m.df.index[b[0]:], eq, bh, cdi)
df = pd.DataFrame(rows); df.to_csv("results/regra_f_ativos.csv", index=False)
pd.set_option("display.width", 260)
print(df.round(3).to_string())
# painel
f, axs = plt.subplots(4, 3, figsize=(7.6, 9.6), dpi=150, sharex=True)
for ax, (t, (idx, eq, bh, cdi)) in zip(axs.ravel(), curves.items()):
    r = df[df.ativo == t].iloc[0]
    ax.plot(idx, eq / 1e3, color=AC, lw=1.4); ax.plot(idx, bh / 1e3, color=MU, lw=.7, ls=":"); ax.plot(idx, cdi / 1e3, color=UP, lw=.8, ls="--")
    ax.set_yscale("log"); ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}")); ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    good = r.final > r.cdi
    ax.set_title(f"{t}  R$ {r.final/1e3:.0f} mil".replace(".", ","), fontsize=9.5, fontweight="bold", color=UP if good else DN, loc="left")
    ax.text(.02, .97, f"{r.acertos}✓ {r.erros}✗ · queda {r.queda*100:.0f}%", transform=ax.transAxes, fontsize=7.2, color=FG, va="top")
    for k in ("top", "right"): ax.spines[k].set_visible(False)
    ax.grid(axis="y", color="#eef1f3"); ax.tick_params(labelsize=7)
    ax.set_xticks([pd.Timestamp("2012-01-01"), pd.Timestamp("2019-01-01"), pd.Timestamp("2026-01-01")]); ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
ax = axs.ravel()[-1]; ax.axis("off")
ax.plot([], [], color=AC, lw=1.4, label="Regra F"); ax.plot([], [], color=MU, lw=.7, ls=":", label="Comprar e segurar"); ax.plot([], [], color=UP, lw=.8, ls="--", label="CDI líquido")
ax.legend(loc="center", frameon=False, fontsize=8.5)
ax.text(.5, .12, "R$ 10 mil em 2012, em mil reais\n(escala log). Título verde =\nterminou acima do CDI.", ha="center", fontsize=7.5, color=MU, transform=ax.transAxes)
f.suptitle("Regra F nos 11 ativos · diário · 2012–2026", x=.02, ha="left", fontsize=12.5, fontweight="bold", color=FG)
f.tight_layout(rect=(0, 0, 1, .97)); f.savefig("report/exemplos/12_regra_f_11_ativos.png", facecolor="white"); print("painel ok")
# timeframes
tfr = []
for tf, dtf, ticks in [("1wk", False, DAILY_T), ("1d", False, DAILY_T), ("60m", False, INTRA_T), ("60m", True, INTRA_T)]:
    for t in ticks:
        m, b, eq, tr, full, seg, bh, cdi, cost = runF(t, tf, dtf)
        tfr.append(dict(tf=tf + (" day trade" if dtf else ""), ativo=t, cagr=full[1], cdi=full[7], queda=full[3], ops=len(tr), taxa=(tr.ret > 0).mean() if len(tr) else np.nan,
                        teste_exc=seg[2, 1] - seg[2, 7], periodo=f"{m.df.index[b[0]].date()}–{m.df.index[-1].date()}"))
T = pd.DataFrame(tfr)
print(T.groupby("tf").agg(cagr=("cagr", "median"), cdi=("cdi", "median"), queda=("queda", "median"), ops=("ops", "median"), taxa=("taxa", "median"),
                          teste_exc=("teste_exc", "median"), bateu=("teste_exc", lambda x: f"{(x > 0).sum()}/{len(x)}"), periodo=("periodo", "first")).round(3).to_string())
