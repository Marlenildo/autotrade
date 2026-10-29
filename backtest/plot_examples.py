"""Gráficos de exemplo de operações (PETR4 diário) para explicar a regra."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from engine2 import *
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

m = Market(load_tf("PETR4", "1d"), "1d"); d = m.df; s = Sim(m)
i0 = d.index.searchsorted(pd.Timestamp("2012-01-01"))
UP, DN, MA1, MA2, ST, AC, FG, MU = "#18794e", "#b4332a", "#2f6fd6", "#a2489d", "#b26b00", "#0b5d7a", "#13202a", "#5a6a77"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": "#c9d3da",
                     "xtick.color": MU, "ytick.color": MU, "axes.labelcolor": FG})
br = lambda v: f"R$ {v:.2f}".replace(".", ",")
nf = lambda v: f"{v:.1f}".replace(".", ",")
pc = lambda r: f"{r*100:+.1f}%".replace(".", ",")
dt = lambda i: d.index[i].strftime("%d/%m")

def trades(rsi):
    eq, nt, _ = s.run(Cfg("rev", "both", "both", "any", rsi, "fast", "p3"), i0)
    t = s.trades(nt); return t[t.side == "C"]

def badge(ax, x, y, n, col):
    ax.annotate(str(n), (x, y), fontsize=8.5, color="white", fontweight="bold", ha="center", va="center", zorder=9,
                bbox=dict(boxstyle="circle,pad=0.25", fc=col, ec="none"))

def draw(a, b, trs, title, fn, notes_fn):
    sl = slice(a, b); x = np.arange(b - a)
    o, h, l, c = (d[k].values[sl] for k in ("open", "high", "low", "close"))
    f = plt.figure(figsize=(7.2, 7.6), dpi=150)
    gs = f.add_gridspec(3, 1, height_ratios=[3.2, 1, 1.25], hspace=.12)
    ax = f.add_subplot(gs[0]); ar = f.add_subplot(gs[1], sharex=ax); tx = f.add_subplot(gs[2]); tx.axis("off")
    for i in x:
        col = UP if c[i] >= o[i] else DN
        ax.plot([i, i], [l[i], h[i]], color=col, lw=1.1, zorder=2)
        ax.add_patch(Rectangle((i - .32, min(o[i], c[i])), .64, max(abs(c[i] - o[i]), .012), color=col, zorder=3))
    ax.plot(x, m.f[sl], color=MA1, lw=1.6, label="MM5"); ax.plot(x, m.s[sl], color=MA2, lw=1.6, label="MM10")
    lines = []; n = 1
    span = h.max() - l.min()
    for _, t in trs.iterrows():
        E, X = t.ei - a, t.xi - a
        stop = t.entry_px * .97
        col = UP if t.ret > 0 else DN
        ax.axvspan(E - 1 - .45, E - 1 + .45, color=AC, alpha=.09, zorder=0)
        ax.plot([E - .5, X + .5], [stop, stop], ls="--", color=ST, lw=1.2, zorder=4)
        ax.scatter([E - .4], [t.entry_px], marker=">", s=55, color=UP, zorder=6)
        xe = X + .4 if t.why == "sinal" else X
        ax.scatter([xe], [t.exit_px], marker="o", s=48, facecolor="white", edgecolor=col, lw=2, zorder=7)
        badge(ax, E - 1, l[E - 1] - span * .06, n, AC)
        ar.scatter([E - 1], [m.r[t.ei - 1]], color=AC, s=20, zorder=5)
        badge(ar, E - 1, m.r[t.ei - 1] - 11, n, AC)
        lines.append(notes_fn(n, t, stop, col)); n += 1
    ax.set_title(title, loc="left", fontsize=12.5, color=FG, fontweight="bold", pad=10)
    ax.legend(loc="upper right", frameon=False, fontsize=9); ax.grid(axis="y", color="#e6ebef"); ax.set_ylabel("R$")
    ax.tick_params(labelbottom=False); ax.margins(y=.14)
    ax.set_ylim(l.min() - span * .14, h.max() + span * .08)
    ar.plot(x, m.r[sl], color=AC, lw=1.4); ar.axhline(30, color=DN, ls=":", lw=1); ar.axhline(70, color=UP, ls=":", lw=1)
    ar.text(x[-1] + .4, 30, "30", color=DN, va="center", fontsize=8); ar.text(x[-1] + .4, 70, "70", color=UP, va="center", fontsize=8)
    ar.set_ylim(5, 80); ar.set_yticks([30, 50, 70]); ar.set_ylabel("IFR(14)"); ar.grid(axis="y", color="#e6ebef")
    ar.set_xticks(x[::2]); ar.set_xticklabels([dt(i) for i in range(a, b)][::2])
    for s_ in (ax, ar):
        for k in ("top", "right"): s_.spines[k].set_visible(False)
    leg = "▶ compra na abertura   ○ saída   - - stop 3%   faixa azul = candle do sinal"
    tx.text(0, .90, leg, fontsize=8.5, color=MU, transform=tx.transAxes, va="top")
    y = .70
    for txt, col in lines:
        tx.text(0, y, txt.replace("$", r"\$"), fontsize=9.2, color=col, transform=tx.transAxes, va="top"); y -= .70 / max(len(lines), 1) if len(lines) > 2 else .38
    f.savefig(fn, bbox_inches="tight", facecolor="white"); plt.close(f); print(fn)

def note_full(n, t, stop, col):
    sig = t.ei - 1
    a = (f"{n}. Sinal {dt(sig)}: fechou {br(d.close.iloc[sig])}, abaixo da MM5 {br(m.f[sig])} e da MM10 {br(m.s[sig])}, IFR {nf(m.r[sig])}.\n"
         f"   Compra {dt(t.ei)} na abertura a {br(t.entry_px)}, stop em {br(stop)}.\n")
    if t.why == "sinal":
        q = t.xi - 1
        a += f"   {dt(q)} fechou {br(d.close.iloc[q])}, acima da MM5 {br(m.f[q])}: vende {dt(t.xi)} na abertura a {br(t.exit_px)}.  Resultado {pc(t.ret)}"
    else:
        a += f"   {dt(t.xi)} a mínima {br(d.low.iloc[t.xi])} furou o stop: vende a {br(t.exit_px)}.  Resultado {pc(t.ret)}"
    return a, col

def note_short(n, t, stop, col):
    sig = t.ei - 1
    w = "sinal (fechou acima da MM5)" if t.why == "sinal" else "stop"
    return (f"{n}. Sinal {dt(sig)} (IFR {m.r[sig]:.0f}) → compra {dt(t.ei)} a {br(t.entry_px)} → sai {dt(t.xi)} por {w} a {br(t.exit_px)}: {pc(t.ret)}"), col

def fix(s_):  # vírgula decimal sem estragar o ponto final das frases
    return s_

if "sar" not in sys.argv:
  os.makedirs("report/exemplos", exist_ok=True)
  c30, c0 = trades(30), trades(0)
  g = c30[c30.entry == "2025-06-05"]; p = c30[c30.entry == "2025-04-23"]
  draw(g.ei.iloc[0] - 9, g.xi.iloc[0] + 4, g, "Com IFR · compra com ganho · PETR4 jun/2025", "report/exemplos/1_com_ifr_ganho.png", note_full)
  draw(p.ei.iloc[0] - 9, p.xi.iloc[0] + 4, p, "Com IFR · compra com perda · PETR4 abr/2025", "report/exemplos/2_com_ifr_perda.png", note_full)
  w = c0[(c0.entry >= "2025-05-23") & (c0.entry <= "2025-06-05")]
  draw(w.ei.min() - 4, w.xi.max() + 4, w, "Sem IFR · mesma regra, mesma época · PETR4 mai–jun/2025", "report/exemplos/3_sem_ifr.png", note_short)


def draw_sar(a, b, trs, title, fn, mirror_tr=None):
    """Regra exata do usuário: sempre posicionado, vira a mão quando fecha do outro lado das duas médias."""
    sl = slice(a, b); x = np.arange(b - a)
    o, h, l, c = (d[k].values[sl] for k in ("open", "high", "low", "close"))
    f = plt.figure(figsize=(7.4, 7.0), dpi=150)
    gs = f.add_gridspec(2, 1, height_ratios=[3.3, 1.1], hspace=.20)
    ax = f.add_subplot(gs[0]); tx = f.add_subplot(gs[1]); tx.axis("off")
    for i in x:
        col = UP if c[i] >= o[i] else DN
        ax.plot([i, i], [l[i], h[i]], color=col, lw=1.1, zorder=2)
        ax.add_patch(Rectangle((i - .32, min(o[i], c[i])), .64, max(abs(c[i] - o[i]), .012), color=col, zorder=3))
    ax.plot(x, m.f[sl], color=MA1, lw=1.6, label="MM5"); ax.plot(x, m.s[sl], color=MA2, lw=1.6, label="MM10")
    span = h.max() - l.min(); lines = []
    for n, (_, t) in enumerate(trs.iterrows(), 1):
        E, X = t.ei - a, t.xi - a
        if E < 0: continue
        isL = t.side == "C"; col = UP if isL else DN
        ax.axvspan(max(E - .5, -.5), min(X - .5, x[-1] + .5), color=col, alpha=.06, zorder=0)
        ax.scatter([E - .4], [t.entry_px], marker="^" if isL else "v", s=60, color=col, zorder=6)
        yb = l[E - 1] - span * .07 if isL else h[E - 1] + span * .07
        badge(ax, E - 1, yb, n, col)
        res = pc(t.ret) if t.why != "fim" else pc(t.ret) + " (aberta)"
        side = "Compra" if isL else "Venda"
        mm = mirror_tr[mirror_tr.ei == t.ei]
        mirror = pc(mm.ret.iloc[0]) if len(mm) else "—"
        lines.append((f"{n}. {dt(t.ei - 1)} fechou {'abaixo' if isL else 'acima'} das duas → {side.lower()} {dt(t.ei)} a {br(t.entry_px)} → "
                      f"{'vira' if t.why == 'sinal' else 'até'} {dt(t.xi)} a {br(t.exit_px)}: {res}   | sentido oposto: {mirror}", UP if t.ret > 0 else DN))
    ax.set_title(title, loc="left", fontsize=12, color=FG, fontweight="bold", pad=10)
    ax.legend(loc="upper left", frameon=False, fontsize=9); ax.grid(axis="y", color="#e6ebef"); ax.set_ylabel("R$")
    ax.set_ylim(l.min() - span * .14, h.max() + span * .14)
    ax.set_xticks(x[::3]); ax.set_xticklabels([dt(i) for i in range(a, b)][::3])
    for k in ("top", "right"): ax.spines[k].set_visible(False)
    tx.text(0, 1.0, "▲ compra   ▼ venda   fundo verde = comprado, vermelho = vendido   número = candle do sinal", fontsize=8.3, color=MU, transform=tx.transAxes, va="top")
    y = .90
    for txt, col in lines:
        tx.text(0, y, txt.replace("$", r"\$"), fontsize=7.9, color=col, transform=tx.transAxes, va="top"); y -= .125
    f.savefig(fn, bbox_inches="tight", facecolor="white"); plt.close(f); print(fn)


if __name__ == "__main__" and "sar" in sys.argv:
    eq, nt, _ = s.run(Cfg("rev", "both", "both", "any", 0, "both", "none", reverse=True), i0)
    t = s.trades(nt)
    a = d.index.searchsorted(pd.Timestamp(sys.argv[2])); b = len(d)
    w = t[t.xi >= a]
    w = w[w.ei > a]
    draw_sar(a, b, w, f"Sua regra exata · PETR4 {d.index[a].strftime('%d/%m')}–{d.index[-1].strftime('%d/%m/%Y')}",
             "report/exemplos/4_regra_exata_vira_mao.png",
             mirror_tr=s.trades(s.run(Cfg("trend", "both", "both", "any", 0, "both", "none", reverse=True), i0)[1]))


def draw_cross(a, b, trs, title, fn):
    """Regra v2: cruzamento MM5 x MM10 dá a direção, candle dá o gatilho, para quando fecha do outro lado das duas."""
    sl = slice(a, b); x = np.arange(b - a)
    o, h, l, c = (d[k].values[sl] for k in ("open", "high", "low", "close"))
    f5, f10 = m.f[sl], m.s[sl]
    f = plt.figure(figsize=(7.4, 7.6), dpi=150)
    gs = f.add_gridspec(3, 1, height_ratios=[3.3, .18, 1.35], hspace=.16)
    ax = f.add_subplot(gs[0]); rb = f.add_subplot(gs[1], sharex=ax); tx = f.add_subplot(gs[2]); tx.axis("off")
    for i in x:
        col = UP if c[i] >= o[i] else DN
        ax.plot([i, i], [l[i], h[i]], color=col, lw=1.1, zorder=2)
        ax.add_patch(Rectangle((i - .32, min(o[i], c[i])), .64, max(abs(c[i] - o[i]), .012), color=col, zorder=3))
        rb.add_patch(Rectangle((i - .5, 0), 1, 1, color=UP if f5[i] > f10[i] else DN, alpha=.55, lw=0))
    ax.plot(x, f5, color=MA1, lw=1.6, label="MM5"); ax.plot(x, f10, color=MA2, lw=1.6, label="MM10")
    cross = [i for i in x[1:] if (f5[i] > f10[i]) != (f5[i - 1] > f10[i - 1])]
    for i in cross:
        ax.scatter([i], [(f5[i] + f10[i]) / 2], marker="X", s=70, color=FG, zorder=8)
    rb.set_yticks([]); rb.set_ylim(0, 1)
    span = h.max() - l.min(); lines = []
    for n, (_, t) in enumerate(trs.iterrows(), 1):
        E, X = t.ei - a, t.xi - a
        isL = t.side == "C"; col = UP if isL else DN
        ax.axvspan(E - .5, X - .5, color=col, alpha=.07, zorder=0)
        ax.scatter([E - .4], [t.entry_px], marker="^" if isL else "v", s=60, color=col, zorder=6)
        ax.scatter([X - .4 if t.why != "fim" else X], [t.exit_px], marker="o", s=44, facecolor="white", edgecolor=UP if t.ret > 0 else DN, lw=2, zorder=7)
        badge(ax, E - 1, l[E - 1] - span * .07 if isL else h[E - 1] + span * .07, n, col)
        cx = max([i for i in cross if i <= E - 1] or [None]) if cross else None
        cr = f"cruzou p/ {'cima' if isL else 'baixo'} {dt(a + cx)}; " if cx is not None else ""
        fim = "ainda aberta" if t.why == "fim" else f"{dt(t.xi - 1)} fechou {'abaixo' if isL else 'acima'} das duas → sai {dt(t.xi)} a {br(t.exit_px)}"
        lines.append((f"{n}. {cr}{dt(t.ei - 1)} fechou {'acima' if isL else 'abaixo'} das duas → {'compra' if isL else 'venda'} {dt(t.ei)} a {br(t.entry_px)}; {fim}: {pc(t.ret)}",
                      UP if t.ret > 0 else DN))
    ax.set_title(title, loc="left", fontsize=12, color=FG, fontweight="bold", pad=10)
    ax.legend(loc="upper left", frameon=False, fontsize=9); ax.grid(axis="y", color="#e6ebef"); ax.set_ylabel("R$")
    ax.set_ylim(l.min() - span * .14, h.max() + span * .14); ax.tick_params(labelbottom=False)
    rb.set_xticks(x[::3]); rb.set_xticklabels([dt(i) for i in range(a, b)][::3])
    rb.text(-.6, .5, "MM5>MM10 ", ha="right", va="center", fontsize=7.5, color=MU)
    for s_ in (ax, rb):
        for k in ("top", "right"): s_.spines[k].set_visible(False)
    tx.text(0, 1.0, "✕ cruzamento   faixa: verde = MM5 acima da MM10 (só compra), vermelho = abaixo (só venda)   ▲ compra ▼ venda ○ saída",
            fontsize=7.8, color=MU, transform=tx.transAxes, va="top")
    y = .86
    for txt, col in lines:
        tx.text(0, y, txt.replace("$", r"\$"), fontsize=7.6, color=col, transform=tx.transAxes, va="top"); y -= .135
    f.savefig(fn, bbox_inches="tight", facecolor="white"); plt.close(f); print(fn)


if __name__ == "__main__" and "cross" in sys.argv:
    import user_rule2
    L, S, LX, SX = user_rule2.sigs(m, "duas", "any")
    eq, nt, _ = s.run(Cfg("trend", "both", "both", "any", 0, "both", "none", reverse=True), i0, sig=(L, S, LX, SX))
    t = s.trades(nt)
    a = d.index.searchsorted(pd.Timestamp(sys.argv[2]))
    w = t[(t.ei > a)]
    print(w[["entry", "exit", "side", "entry_px", "exit_px", "ret", "why"]].to_string())
    draw_cross(a, len(d), w, f"Sua regra (cruzamento + candle) · PETR4 {d.index[a].strftime('%d/%m')}–{d.index[-1].strftime('%d/%m/%Y')}",
               "report/exemplos/5_cruzamento_candle.png")


def draw_cross2(a, b, trs, eqv, title, fn):
    """Versão didática: resultado escrito em cada operação, perdas destacadas e patrimônio embaixo."""
    sl = slice(a, b); x = np.arange(b - a)
    o, h, l, c = (d[k].values[sl] for k in ("open", "high", "low", "close"))
    f5, f10 = m.f[sl], m.s[sl]
    f = plt.figure(figsize=(7.4, 8.4), dpi=150)
    gs = f.add_gridspec(4, 1, height_ratios=[3.4, .16, 1.15, 1.25], hspace=.14)
    ax = f.add_subplot(gs[0]); rb = f.add_subplot(gs[1], sharex=ax); ae = f.add_subplot(gs[2], sharex=ax); tx = f.add_subplot(gs[3]); tx.axis("off")
    for i in x:
        col = UP if c[i] >= o[i] else DN
        ax.plot([i, i], [l[i], h[i]], color=col, lw=1.1, zorder=2, alpha=.85)
        ax.add_patch(Rectangle((i - .32, min(o[i], c[i])), .64, max(abs(c[i] - o[i]), .012), color=col, zorder=3, alpha=.85))
        rb.add_patch(Rectangle((i - .5, 0), 1, 1, color=UP if f5[i] > f10[i] else DN, alpha=.55, lw=0))
    ax.plot(x, f5, color=MA1, lw=1.6, label="MM5"); ax.plot(x, f10, color=MA2, lw=1.6, label="MM10")
    for i in x[1:]:
        if (f5[i] > f10[i]) != (f5[i - 1] > f10[i - 1]):
            ax.scatter([i], [(f5[i] + f10[i]) / 2], marker="X", s=60, color=FG, zorder=8)
    span = h.max() - l.min(); top = h.max() + span * .10
    lines = []; tot = 1.0; prev_mid = -99; lvl = 0
    for n, (_, t) in enumerate(trs.iterrows(), 1):
        E, X = t.ei - a, t.xi - a
        isL = t.side == "C"; win = t.ret > 0; rc = UP if win else DN
        ax.axvspan(E - .5, X - .5 if t.why != "fim" else X + .5, color=rc, alpha=.13 if not win else .08, zorder=0,
                   hatch=None if win else "///", ec=rc, lw=0)
        ax.annotate("", xy=(E - .4, t.entry_px), xytext=(E - .4, t.entry_px + (-1 if isL else 1) * span * .09),
                    arrowprops=dict(arrowstyle="-|>", color=FG, lw=1.3), zorder=9)
        ax.scatter([X - .4 if t.why != "fim" else X], [t.exit_px], marker="o", s=46, facecolor="white", edgecolor=rc, lw=2, zorder=9)
        mid = (E + (X if t.why != "fim" else X + 1)) / 2 - .5
        lvl = (1 - lvl) if mid - prev_mid < 5 else 0; prev_mid = mid
        ax.text(mid, top + lvl * span * .13, f"{n}\n{'C' if isL else 'V'} {pc(t.ret)}", ha="center", va="bottom", fontsize=8.6, fontweight="bold", color=rc,
                bbox=dict(boxstyle="round,pad=.25", fc="white", ec=rc, lw=1))
        dur = t.xi - t.ei
        tot *= 1 + t.ret
        why = ("cruzou para baixo e o candle fechou abaixo; no dia seguinte voltou acima das duas" if not isL else
               "cruzou para cima e o candle fechou acima; logo depois fechou abaixo das duas") if (not win and dur <= 4) else \
              ("ainda aberta, %d pregões até agora" % dur if t.why == "fim" else "a tendência continuou e a operação durou %d pregões" % dur if win else "durou %d pregões e terminou contra" % dur)
        lines.append((f"{n}. {'Compra' if isL else 'Venda'} {dt(t.ei)} a {br(t.entry_px)} → {'em aberto, ' if t.why == 'fim' else 'sai ' + dt(t.xi) + ' a '}{br(t.exit_px)}  {pc(t.ret)}  ({why})", rc))
    ax.set_title(title, loc="left", fontsize=12, color=FG, fontweight="bold", pad=10)
    ax.legend(loc="lower right", frameon=False, fontsize=9); ax.grid(axis="y", color="#e6ebef"); ax.set_ylabel("R$")
    ax.set_ylim(l.min() - span * .12, h.max() + span * .44); ax.tick_params(labelbottom=False)
    rb.set_yticks([]); rb.set_ylim(0, 1); rb.tick_params(labelbottom=False)
    rb.text(-.7, .5, "MM5>MM10", ha="right", va="center", fontsize=7.5, color=MU)
    ev = eqv[sl] / eqv[a] * 10000
    ae.plot(x, ev, color=AC, lw=1.8); ae.axhline(10000, color=MU, lw=.8, ls=":")
    ae.fill_between(x, 10000, ev, where=ev >= 10000, color=UP, alpha=.15); ae.fill_between(x, 10000, ev, where=ev < 10000, color=DN, alpha=.15)
    ae.set_ylabel("Patrimônio"); ae.grid(axis="y", color="#e6ebef")
    ae.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:.1f} mil".replace(".", ",")))
    ae.text(x[-1], ev[-1], f"  {br(ev[-1])}", va="center", fontsize=8.5, color=AC, fontweight="bold")
    ae.set_xticks(x[::5]); ae.set_xticklabels([dt(i) for i in range(a, b)][::5])
    for s_ in (ax, rb, ae):
        for k in ("top", "right"): s_.spines[k].set_visible(False)
    tx.text(0, 1.0, "Caixa no topo = resultado de cada operação (C compra, V venda). Faixa listrada vermelha = operação com perda.\n"
                    "✕ = cruzamento das médias. Seta = entrada na abertura. ○ = saída. Faixa fina: verde = só compra, vermelho = só venda.",
            fontsize=7.6, color=MU, transform=tx.transAxes, va="top")
    y = .70
    for txt, col in lines:
        tx.text(0, y, txt.replace("$", r"\$"), fontsize=7.3, color=col, transform=tx.transAxes, va="top"); y -= .135
    f.savefig(fn, bbox_inches="tight", facecolor="white"); plt.close(f); print(fn)


def draw_dur(t, fn):
    """Onde está a perda na história toda: resultado por duração da operação."""
    t = t.copy(); t["dur"] = t.xi - t.ei
    bins = [-1, 1, 2, 4, 9, 10000]; labs = ["0–1", "2", "3–4", "5–9", "10 ou mais"]
    g = t.groupby(pd.cut(t.dur, bins, labels=labs), observed=False).agg(n=("ret", "size"), acerto=("ret", lambda x: (x > 0).mean()), soma=("pnl", "sum"))
    f, ax = plt.subplots(figsize=(7.2, 4.0), dpi=150)
    cols = [UP if v > 0 else DN for v in g.soma]
    ax.bar(range(len(g)), g.soma, color=cols, width=.62)
    for i, (n, ac, sm) in enumerate(zip(g.n, g.acerto, g.soma)):
        ax.text(i, sm + (900 if sm > 0 else -900), (f"{'+' if sm > 0 else '−'}R$ {abs(sm)/1000:.1f} mil".replace(".", ",") + f"\n{n} operações\nacerto {ac*100:.0f}%").replace("$", r"\$"), ha="center",
                va="bottom" if sm > 0 else "top", fontsize=8.2, color=FG)
    ax.axhline(0, color=MU, lw=.8)
    ax.set_xticks(range(len(g))); ax.set_xticklabels(labs); ax.set_xlabel("Duração da operação (pregões)")
    ax.set_ylabel("Lucro ou prejuízo somado")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:.0f} mil"))
    ax.set_title("Onde está a perda · sua regra na PETR4, 2012–2026", loc="left", fontsize=12, fontweight="bold", color=FG, pad=10)
    lo, hi = g.soma.min(), g.soma.max(); ax.set_ylim(lo * 2.0, hi * 1.45)
    for k in ("top", "right"): ax.spines[k].set_visible(False)
    ax.grid(axis="y", color="#e6ebef")
    f.savefig(fn, bbox_inches="tight", facecolor="white"); plt.close(f); print(fn)


if __name__ == "__main__" and "cross2" in sys.argv:
    import user_rule2
    L, S, LX, SX = user_rule2.sigs(m, "duas", "any")
    eqv, nt, _ = s.run(Cfg("trend", "both", "both", "any", 0, "both", "none", reverse=True), i0, sig=(L, S, LX, SX))
    t = s.trades(nt)
    full = np.r_[np.full(i0, eqv[0]), eqv]
    a = d.index.searchsorted(pd.Timestamp(sys.argv[2]))
    w = t[t.ei > a]
    draw_cross2(a, len(d), w, full, f"Sua regra · PETR4 {d.index[a].strftime('%d/%m')}–{d.index[-1].strftime('%d/%m/%Y')}",
                "report/exemplos/5_cruzamento_candle.png")
    draw_dur(t, "report/exemplos/6_onde_perde.png")
