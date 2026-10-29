import sys, json; sys.path.insert(0, 'backtest')
from engine import *
from validate import CANDS
df = load("PETR4"); a, b = "2012-01-01", "2026-12-31"
out = {}
series = {}
for name, cfg, cdi in [("Sua estratégia (A)", CANDS["A_original"], False),
                       ("Pullback (B)", CANDS["B_pullback"], False),
                       ("Pullback + CDI no caixa", CANDS["B_pullback"], True)]:
    eq, tr, ex = run(df, cfg, a, b, cdi=cdi)
    series[name] = eq
    m = metrics(eq, tr, ex); out[name] = {k: float(v) for k, v in m.items()}
    if name == "Sua estratégia (A)":
        out["A_why"] = tr.why.value_counts().to_dict()
bh = buy_hold(df, a, b); series["Comprar e segurar"] = bh
cdi = pd.Series(np.cumprod(1 + cdi_daily(bh.index) * .85) * 1e4, index=bh.index); series["CDI líquido"] = cdi
w = pd.DataFrame(series).resample("W").last().dropna()
out["dates"] = [d.strftime("%Y-%m-%d") for d in w.index]
out["eq"] = {k: [round(x) for x in w[k]] for k in w}
out["dd"] = {k: [round(x * 100, 1) for x in (w[k] / w[k].cummax() - 1)] for k in ["Sua estratégia (A)", "Pullback + CDI no caixa", "Comprar e segurar"]}
for k in ["Comprar e segurar", "CDI líquido"]:
    s = series[k]; yrs = (s.index[-1]-s.index[0]).days/365.25
    out[k] = dict(final=float(s.iloc[-1]), cagr=float((s.iloc[-1]/1e4)**(1/yrs)-1), max_dd=float((s/s.cummax()-1).min()))
json.dump(out, open("results/report_petr4.json", "w"))
print(json.dumps({k: {kk: round(vv, 3) for kk, vv in v.items()} if isinstance(v, dict) and k not in ("eq","dd") else None for k, v in out.items() if k not in ("dates","eq","dd")}, indent=1, ensure_ascii=False))
