"""Controle de sorte: roda a grade diária em 6 séries sintéticas de PETR4 construídas por
bootstrap em blocos dos candles reais (mesma volatilidade e tamanho de candle, sem padrão).
Qualquer "estratégia vencedora" aqui é puro acaso, então serve de régua para os resultados reais."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
import grid2
from engine2 import *

def synth(df, seed, block=20):
    rng = np.random.default_rng(seed)
    c = df.close.values
    rel = np.c_[df.open.values / np.r_[c[0], c[:-1]], df.high.values / c, df.low.values / c, c / np.r_[c[0], c[:-1]]]
    n = len(df); out = []
    while len(out) < n:
        s = rng.integers(1, n - block); out.extend(range(s, s + block))
    rel = rel[out[:n]]
    close = c[0] * np.cumprod(rel[:, 3])
    prev = np.r_[c[0], close[:-1]]
    o = prev * rel[:, 0]
    s = pd.DataFrame(dict(open=o, close=close), index=df.index)
    s["high"] = np.maximum(close * rel[:, 1], np.maximum(o, close))
    s["low"] = np.minimum(close * rel[:, 2], np.minimum(o, close))
    s["volume"] = 1; s["dividends"] = 0.0
    return s

if __name__ == "__main__":
    real = load_tf("PETR4", "1d")
    orig = grid2.load_tf
    for k in range(6):
        sd = synth(real, k)
        grid2.load_tf = lambda t, tf, sd=sd: sd
        out = grid2.job((f"SINT{k}", "1d", False))
        print(out, flush=True)
