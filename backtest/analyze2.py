import glob, json, os, sys
import numpy as np, pandas as pd
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
KEY = ["mode", "entry_ref", "side", "candle", "rsi_th", "exit_ref", "stop", "tp", "units", "cdi"]
MINT = {"1d": 30, "1wk": 15, "60m": 30, "60m_dt": 30, "15m_dt": 20, "5m_dt": 20}

def load(tf):
    fs = [f for f in glob.glob(f"results/grid2/*_{tf}.parquet") if "SINT" not in f]
    return pd.concat([pd.read_parquet(f).assign(ticker=os.path.basename(f).split("_")[0]) for f in fs])

def robust(df, mint):
    ok = (df.treino_trades >= mint) & (df.treino_sharpe > 0) & (df.validacao_sharpe > 0) & (df.treino_expo >= .05)
    d = df[ok].copy(); d["score"] = d[["treino_sharpe", "validacao_sharpe"]].min(axis=1)
    return d.sort_values("score", ascending=False)

summary = {}
for tf in ["1wk", "1d", "60m", "60m_dt", "15m_dt", "5m_dt"]:
    df = load(tf); mint = MINT[tf]
    for p in ("treino", "validacao", "teste"):
        df[f"{p}_exc"] = df[f"{p}_cagr"] - df[f"{p}_cdi"]
    print(f"\n################ {tf}  ({df.ticker.nunique()} ativos, {len(df)//df.ticker.nunique()} configs/ativo)")
    s = {}
    for cdi in (False, True):
        d = df[df.cdi == cdi]
        s[f"pos_test_cdi{int(cdi)}"] = float((d.teste_ret > 0).mean())
        s[f"beat_cdi_test_cdi{int(cdi)}"] = float((d.teste_exc > 0).mean())
        s[f"med_test_sh_cdi{int(cdi)}"] = float(d.teste_sharpe.median())
    # topo do treino por ativo -> teste
    d = df[(df.treino_trades >= mint)]
    top = d.sort_values("treino_sharpe", ascending=False).groupby("ticker").head(20)
    s["top_train_sharpe_train"] = float(top.treino_sharpe.median()); s["top_train_sharpe_test"] = float(top.teste_sharpe.median())
    s["corr_train_test"] = float(d.groupby("ticker").apply(lambda x: x.treino_sharpe.corr(x.teste_sharpe)).median())
    r = robust(df, mint).groupby("ticker").head(20)
    s["robust_test_sharpe"] = float(r.teste_sharpe.median()); s["robust_test_cagr"] = float(r.teste_cagr.median())
    s["robust_test_pos"] = float((r.teste_ret > 0).mean())
    s["robust_test_exc"] = float(r.teste_exc.median()); s["robust_beat_cdi"] = float((r.teste_exc > 0).mean())
    s["robust_train_sharpe"] = float(r.treino_sharpe.median())
    # seleção entre ativos: mediana entre ativos de min(treino, validação)
    g = df.assign(sc=df[["treino_sharpe", "validacao_sharpe"]].min(axis=1)).groupby(KEY)
    agg = g.agg(sc=("sc", "median"), ntr=("treino_trades", "median"), test_sh=("teste_sharpe", "median"),
                test_cagr=("teste_cagr", "median"), test_exc=("teste_exc", "median"), expo=("teste_expo", "median"), test_dd=("teste_dd", "median"), pos=("teste_ret", lambda x: (x > 0).mean()),
                tr_sh=("treino_sharpe", "median"), va_sh=("validacao_sharpe", "median"), n=("ticker", "count"))
    agg = agg[(agg.ntr >= mint) & (agg.expo >= .05)].sort_values("sc", ascending=False)
    print(agg.head(12).round(3).to_string())
    s["xasset_top"] = agg.head(10).reset_index().to_dict("records")
    # efeito de cada parâmetro no teste (mediana do Sharpe no teste)
    eff = {}
    for k in ["mode", "entry_ref", "side", "candle", "rsi_th", "exit_ref", "stop", "tp", "units", "cdi"]:
        eff[k] = d.groupby(k).teste_sharpe.median().round(3).to_dict()
    s["effects"] = {k: {str(a): b for a, b in v.items()} for k, v in eff.items()}
    for k, v in s["effects"].items(): print(" ", k, v)
    print({k: round(v, 3) for k, v in s.items() if isinstance(v, float)})
    summary[tf] = s

# controle de sorte
sn = pd.concat([pd.read_parquet(f) for f in glob.glob("results/grid2/SINT*_1d.parquet")])
sn["t"] = np.concatenate([np.full(len(pd.read_parquet(f)), k) for k, f in enumerate(glob.glob("results/grid2/SINT*_1d.parquet"))])
for p in ("treino", "validacao", "teste"):
    sn[f"{p}_exc"] = sn[f"{p}_cagr"] - sn[f"{p}_cdi"]
d = sn[sn.treino_trades >= 30]
top = d.sort_values("treino_sharpe", ascending=False).groupby("t").head(20)
r = robust(sn.rename(columns={"t": "tt"}), 30)
noise = dict(pos_test=float((sn[~sn.cdi].teste_ret > 0).mean()), best_train=float(d.groupby("t").treino_sharpe.max().median()),
             top_train_sharpe_test=float(top.teste_sharpe.median()), robust_frac=float(len(r) / len(sn)),
             robust_test_sharpe=float(r.groupby("tt").head(20).teste_sharpe.median()),
             robust_beat_cdi=float((r.groupby("tt").head(20).teste_exc > 0).mean()),
             p95_test_sharpe=float(sn[~sn.cdi].teste_sharpe.quantile(.95)))
real = load("1d")
for p in ("treino", "validacao", "teste"):
    real[f"{p}_exc"] = real[f"{p}_cagr"] - real[f"{p}_cdi"]
noise["real_robust_frac"] = float(len(robust(real, 30)) / len(real))
noise["real_best_train"] = float(real[real.treino_trades >= 30].groupby("ticker").treino_sharpe.max().median())
print("\nRUÍDO", {k: round(v, 3) for k, v in noise.items()})
summary["noise"] = noise
json.dump(summary, open("results/summary2.json", "w"), default=str, indent=1)
