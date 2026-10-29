import sys; sys.path.insert(0, 'backtest')
from engine import *
from grid import PERIODS
TICKERS = ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "WEGE3", "MGLU3", "B3SA3", "PRIO3", "BOVA11"]
CANDS = {
    "A_original": Config(mode="rev", side="both", rsi_th=30, candle="any", exit="ma5", stop=0.03),
    "B_pullback": Config(mode="trend", side="long", rsi_th=None, candle="against", exit="ma10", stop=None),
    "C_pullback_mm200": Config(mode="trend", side="long", rsi_th=None, candle="against", exit="ma10", stop=None, regime=200),
    "D_pullback_mm50": Config(mode="trend", side="long", rsi_th=None, candle="against", exit="ma10", stop=None, regime=50),
    "E_pullback_stop5": Config(mode="trend", side="long", rsi_th=None, candle="against", exit="ma10", stop=0.05),
    "F_pullback_mm200_stop3": Config(mode="trend", side="long", rsi_th=None, candle="against", exit="ma10", stop=0.03, regime=200),
}
if __name__ == "__main__":
    rows = []
    for t in TICKERS:
        df = load(t)
        for name, cfg in list(CANDS.items()) + [("BH", None)]:
            for p, (a, b) in PERIODS.items():
                if cfg is None:
                    eq = buy_hold(df, a, b); m = metrics(eq, pd.DataFrame(columns=["pnl","ret","days","why","exit"]), dict(costs=0,dividends=0,btc=0))
                else:
                    eq, tr, ex = run(df, cfg, a, b); m = metrics(eq, tr, ex)
                rows.append(dict(ticker=t, cand=name, periodo=p, **m))
    res = pd.DataFrame(rows); res.to_csv("results/validacao_multiativos.csv", index=False)
    pd.set_option("display.width", 250)
    for k in ["cagr", "sharpe", "max_dd"]:
        print("\n==", k); print(res.pivot_table(index=["ticker"], columns=["cand", "periodo"], values=k).round(2).iloc[:, :].to_string())
    print("\n== médias entre ativos")
    print(res.groupby(["cand", "periodo"])[["cagr", "sharpe", "max_dd", "exposicao", "trades", "acerto"]].median().round(3).to_string())
    