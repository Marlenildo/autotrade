import sys; sys.path.insert(0, 'backtest')
from engine import *
from grid import PERIODS
from validate import TICKERS, CANDS
rows = []
for t in TICKERS:
    df = load(t)
    for name in ["A_original", "B_pullback", "D_pullback_mm50"]:
        for p, (a, b) in PERIODS.items():
            for cdi in (False, True):
                eq, tr, ex = run(df, CANDS[name], a, b, cdi=cdi); m = metrics(eq, tr, ex)
                rows.append(dict(ticker=t, cand=name + ("+CDI" if cdi else ""), periodo=p, **m))
    for p, (a, b) in PERIODS.items():
        eq = buy_hold(df, a, b); m = metrics(eq, pd.DataFrame(columns=["pnl","ret","days","why","exit"]), dict(costs=0,dividends=0,btc=0))
        rows.append(dict(ticker=t, cand="BH", periodo=p, **m))
for p, (a, b) in PERIODS.items():
    yrs = range(int(a[:4]), int(b[:4]) + 1)
    g = np.prod([(1 + CDI_ANUAL[y]*.85) for y in yrs]) ** (1/len(yrs)) - 1
    print(p, "CDI líquido médio a.a.:", round(g, 3))
res = pd.DataFrame(rows); res.to_csv("results/validacao_cdi.csv", index=False)
pd.set_option("display.width", 250)
print(res.groupby(["cand", "periodo"])[["cagr", "sharpe", "max_dd"]].median().unstack().round(3).to_string())
print(res[res.cand=="B_pullback+CDI"].pivot_table(index="ticker", columns="periodo", values="cagr").round(3).join(
      res[res.cand=="BH"].pivot_table(index="ticker", columns="periodo", values="cagr").round(3), rsuffix="_BH").to_string())
