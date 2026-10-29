import sys, itertools, time
sys.path.insert(0, 'backtest')
from engine import *

PERIODS = {"treino": ("2012-01-01", "2019-12-31"),
           "validacao": ("2020-01-01", "2022-12-31"),
           "teste": ("2023-01-01", "2026-12-31")}

def grid():
    for mode, side, rsi, cand, ex, st in itertools.product(
            ["rev", "trend"], ["long", "short", "both"], [None, 30, 40, 50],
            ["any", "with", "against"], ["ma5", "ma10", "both", "rsi"], [None, 0.02, 0.03, 0.05]):
        yield Config(mode=mode, side=side, rsi_th=rsi, candle=cand, exit=ex, stop=st)

def evaluate(ticker, cfgs, periods=PERIODS):
    df = load(ticker)
    rows = []
    for cfg in cfgs:
        sig = prepare(df, cfg)
        row = asdict(cfg); row["ticker"] = ticker
        for p, (a, b) in periods.items():
            eq, tr, ex = run(df, cfg, a, b, sig=sig)
            m = metrics(eq, tr, ex)
            for k in ("cagr", "ret_pos_ir", "max_dd", "sharpe", "trades", "acerto", "profit_factor"):
                row[f"{p}_{k}"] = m[k]
        rows.append(row)
    return pd.DataFrame(rows)

if __name__ == "__main__":
    t = time.time()
    tick = sys.argv[1] if len(sys.argv) > 1 else "PETR4"
    res = evaluate(tick, list(grid()))
    res.to_csv(f"results/grid_{tick}.csv", index=False)
    print(len(res), "configs em", round(time.time() - t), "s")
