"""Motor v2 — grade ampla, vários timeframes, compilado com numba.

Mesmas regras de execução do engine.py (sinal no fechamento do candle, ordem na
abertura do candle seguinte, stop/alvo dentro do candle com gap executando na
abertura) e, além disso:
- entrada acima/abaixo da média rápida, da lenta, das duas ou de qualquer uma;
- candle a favor, contra ou indiferente; IFR opcional;
- saída por cruzamento de média(s), por IFR, por stop (% fixo ou ATR) e alvo (múltiplo do stop);
- operação única ou até N entradas na mesma direção (piramidação);
- day trade: zera no último candle do pregão, sem aluguel no vendido e IR 20%;
- caixa parado no CDI opcional.
"""
from __future__ import annotations
import itertools
from dataclasses import dataclass, asdict, replace
import numpy as np
import pandas as pd
from numba import njit

CDI_ANUAL = {2010: .0975, 2011: .1160, 2012: .0840, 2013: .0806, 2014: .1081, 2015: .1324, 2016: .1400,
             2017: .0993, 2018: .0642, 2019: .0596, 2020: .0276, 2021: .0442, 2022: .1237, 2023: .1304,
             2024: .1087, 2025: .1430, 2026: .1450}
BARS_YEAR = {"1wk": 52, "1d": 252, "60m": 252 * 7, "15m": 252 * 28, "5m": 252 * 84}

# ---------------------------------------------------------------- dados
def load_tf(ticker: str, tf: str) -> pd.DataFrame:
    if tf in ("1d", "1wk"):
        df = pd.read_csv(f"data/{ticker}.csv", parse_dates=["date"]).set_index("date")
        df = df[(df.volume > 0) & (df.close > 0)][["open", "high", "low", "close", "volume", "dividends"]]
        if tf == "1wk":
            df = df.resample("W-FRI").agg(dict(open="first", high="max", low="min", close="last",
                                                volume="sum", dividends="sum")).dropna()
    else:
        df = pd.read_csv(f"data/intraday/{ticker}_{tf}.csv", parse_dates=["date"]).set_index("date")
        df = df[(df.close > 0)].copy()
        # só pregão regular (10h–17h); descarta leilões e candles vazios
        t = df.index.hour + df.index.minute / 60
        df = df[(t >= 10) & (t < 17)]
        df["dividends"] = 0.0
    return df


def rsi_wilder(c: pd.Series, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


class Market:
    """Pré-calcula tudo que não depende da configuração."""
    def __init__(self, df: pd.DataFrame, tf: str, fast=5, slow=10, rsi_n=14):
        self.df, self.tf = df, tf
        c = df.close
        self.c = c
        self.f = c.rolling(fast).mean().values
        self.s = c.rolling(slow).mean().values
        self.r = rsi_wilder(c, rsi_n).values
        cv = c.values
        self.green = (cv > df.open.values)
        self.red = (cv < df.open.values)
        self.af, self.as_ = cv > self.f, cv > self.s
        self.bf, self.bs = cv < self.f, cv < self.s
        tr = np.maximum(df.high - df.low, np.maximum((df.high - c.shift()).abs(), (df.low - c.shift()).abs()))
        self.atr = tr.rolling(14).mean().values
        self.valid = ~(np.isnan(self.f) | np.isnan(self.s) | np.isnan(self.r) | np.isnan(self.atr))
        day = df.index.normalize()
        intraday = tf not in ("1d", "1wk")
        self.day_end = np.r_[day[1:] != day[:-1], True] if intraday else np.zeros(len(df), bool)
        first = np.r_[True, day[1:] != day[:-1]]
        rates = np.array([(1 + CDI_ANUAL.get(d.year, .10)) ** (1 / 252) - 1 for d in df.index])
        if tf == "1wk":
            rates = (1 + rates) ** 5 - 1
            first = np.ones(len(df), bool)
        self.cdi = np.where(first, rates, 0.0)
        self.arr = tuple(np.ascontiguousarray(df[k].values, dtype=np.float64) for k in ("open", "high", "low", "close", "dividends"))

    def ref(self, side_above: bool, which: str):
        a = (self.af, self.as_) if side_above else (self.bf, self.bs)
        return {"fast": a[0], "slow": a[1], "both": a[0] & a[1], "either": a[0] | a[1]}[which]


@dataclass(frozen=True)
class Cfg:
    mode: str = "trend"      # trend: compra acima das médias | rev: compra abaixo
    entry_ref: str = "both"  # fast | slow | both | either
    side: str = "long"       # long | short | both
    candle: str = "any"      # any | with | against
    rsi_th: float = 0        # 0 = sem IFR; rev compra se IFR<th; trend compra se IFR>100-th
    exit_ref: str = "slow"   # fast | slow | both | either | rsi
    stop: str = "none"       # none | p1 p2 p3 p5 (percentual) | atr1 atr2 atr3
    tp: float = 0            # alvo = tp × distância do stop (0 = sem alvo)
    units: int = 1           # 1 = operação única; >1 = aceita novas entradas na mesma direção
    daytrade: bool = False
    cdi: bool = False

    def label(self):
        m = {"trend": "Tendência", "rev": "Reversão"}[self.mode]
        ref = {"fast": "MM5", "slow": "MM10", "both": "MM5 e MM10", "either": "MM5 ou MM10"}
        sd = {"long": "compra", "short": "venda", "both": "compra e venda"}[self.side]
        cd = {"any": "qualquer candle", "with": "candle a favor", "against": "candle contra"}[self.candle]
        r = "sem IFR" if not self.rsi_th else f"IFR {self.rsi_th:g}"
        ex = "IFR 70/30" if self.exit_ref == "rsi" else ref[self.exit_ref]
        st = "sem stop" if self.stop == "none" else (f"stop {self.stop[1:]}%" if self.stop[0] == "p" else f"stop {self.stop[3:]}×ATR")
        tp = f", alvo {self.tp:g}×stop" if self.tp else ""
        u = "" if self.units == 1 else f", até {self.units} entradas"
        return f"{m} · {sd} · entra {ref[self.entry_ref]} · {cd} · {r} · sai {ex} · {st}{tp}{u}" + (" · CDI" if self.cdi else "")


def signals(m: Market, cfg: Cfg):
    up = cfg.mode == "trend"
    L = m.ref(up, cfg.entry_ref).copy()
    S = m.ref(not up, cfg.entry_ref).copy()
    if cfg.rsi_th:
        if up:
            L &= m.r > 100 - cfg.rsi_th; S &= m.r < cfg.rsi_th
        else:
            L &= m.r < cfg.rsi_th; S &= m.r > 100 - cfg.rsi_th
    if cfg.candle == "with":
        L &= m.green; S &= m.red
    elif cfg.candle == "against":
        L &= m.red; S &= m.green
    if cfg.side == "long":
        S[:] = False
    elif cfg.side == "short":
        L[:] = False
    L &= m.valid; S &= m.valid
    if cfg.exit_ref == "rsi":
        LX, SX = m.r > 70, m.r < 30
    else:
        # tendência comprada sai quando fecha abaixo da(s) média(s);
        # reversão comprada sai quando volta para cima delas (vendido espelhado)
        LX, SX = m.ref(not up, cfg.exit_ref), m.ref(up, cfg.exit_ref)
    return L, S, LX, SX


def stop_params(cfg: Cfg):
    if cfg.stop == "none":
        return 0, 0.0
    if cfg.stop[0] == "p":
        return 1, float(cfg.stop[1:]) / 100
    return 2, float(cfg.stop[3:])


# ---------------------------------------------------------------- simulação
MAXU = 4
MAXT = 200000

@njit(cache=True)
def _sim(o, h, l, c, div, cdi, day_end, atr, L, S, LX, SX, stop_kind, stop_val, tp_mult,
         max_units, daytrade, use_cdi, fee, slip, btc_bar, div_net, i0, i1, capital,
         t_ent, t_ex, t_side, t_pnl, t_ret, t_why, t_epx, t_xpx):
    n = i1 - i0 + 1
    eq = np.empty(n)
    cash = capital
    pos = 0
    qty = np.zeros(MAXU); epx = np.zeros(MAXU); spx = np.zeros(MAXU); tpx = np.zeros(MAXU)
    ent = np.zeros(MAXU, np.int64); extra = np.zeros(MAXU); act = np.zeros(MAXU, np.bool_)
    nact = 0
    pend = 0
    nt = 0
    tcost = 0.0
    k = fee + slip
    for i in range(i0, i1 + 1):
        # proventos (data-com no candle anterior)
        if nact > 0 and div[i] > 0:
            for u in range(MAXU):
                if act[u]:
                    v = div[i] * qty[u]
                    if pos == 1:
                        v *= div_net; cash += v; extra[u] += v
                    else:
                        cash -= v; extra[u] -= v
        # ordens na abertura
        if pend == 2 and nact > 0:
            for u in range(MAXU):
                if act[u]:
                    px = o[i]; val = qty[u] * px; cost = val * k; tcost += cost
                    if pos == 1:
                        cash += val - cost; g = (px - epx[u]) * qty[u]
                    else:
                        cash -= val + cost; g = (epx[u] - px) * qty[u]
                    pnl = g - cost - epx[u] * qty[u] * k + extra[u]
                    if nt < MAXT:
                        t_ent[nt] = ent[u]; t_ex[nt] = i; t_side[nt] = pos; t_pnl[nt] = pnl
                        t_ret[nt] = pnl / (epx[u] * qty[u]); t_why[nt] = 0; t_epx[nt] = epx[u]; t_xpx[nt] = px; nt += 1
                    act[u] = False; extra[u] = 0.0
            nact = 0; pos = 0
        elif (pend == 1 or pend == -1) and nact < max_units and (pos == 0 or pos == pend):
            px = o[i]
            # tamanho: patrimônio / max_units, limitado ao caixa disponível na compra
            m2m = cash
            for u in range(MAXU):
                if act[u]:
                    m2m += qty[u] * o[i] * pos
            budget = m2m / max_units
            if pend == 1 and budget > cash:
                budget = cash
            q = np.floor(budget / (px * (1 + k)))
            if q > 0:
                for u in range(MAXU):
                    if not act[u]:
                        break
                cost = q * px * k; tcost += cost
                if pend == 1:
                    cash -= q * px + cost
                else:
                    cash += q * px - cost
                pos = pend; act[u] = True; qty[u] = q; epx[u] = px; ent[u] = i; extra[u] = 0.0; nact += 1
                d = 0.0
                if stop_kind == 1:
                    d = px * stop_val
                elif stop_kind == 2:
                    d = atr[i - 1] * stop_val
                spx[u] = px - d * pos if stop_kind > 0 else 0.0
                tpx[u] = px + d * tp_mult * pos if (stop_kind > 0 and tp_mult > 0) else 0.0
        pend = 0
        # stop / alvo dentro do candle (stop primeiro, conservador)
        if nact > 0:
            for u in range(MAXU):
                if not act[u]:
                    continue
                px = -1.0; why = 0
                if stop_kind > 0:
                    if pos == 1 and l[i] <= spx[u]:
                        px = min(o[i], spx[u]) if i > ent[u] else spx[u]; why = 1
                    elif pos == -1 and h[i] >= spx[u]:
                        px = max(o[i], spx[u]) if i > ent[u] else spx[u]; why = 1
                if px < 0 and tpx[u] > 0:
                    if pos == 1 and h[i] >= tpx[u]:
                        px = max(o[i], tpx[u]) if i > ent[u] else tpx[u]; why = 2
                    elif pos == -1 and l[i] <= tpx[u]:
                        px = min(o[i], tpx[u]) if i > ent[u] else tpx[u]; why = 2
                if px < 0 and daytrade and day_end[i]:
                    px = c[i]; why = 3
                if px >= 0:
                    val = qty[u] * px; cost = val * k; tcost += cost
                    if pos == 1:
                        cash += val - cost; g = (px - epx[u]) * qty[u]
                    else:
                        cash -= val + cost; g = (epx[u] - px) * qty[u]
                    pnl = g - cost - epx[u] * qty[u] * k + extra[u]
                    if nt < MAXT:
                        t_ent[nt] = ent[u]; t_ex[nt] = i; t_side[nt] = pos; t_pnl[nt] = pnl
                        t_ret[nt] = pnl / (epx[u] * qty[u]); t_why[nt] = why; t_epx[nt] = epx[u]; t_xpx[nt] = px; nt += 1
                    act[u] = False; extra[u] = 0.0; nact -= 1
            if nact == 0:
                pos = 0
        # aluguel do vendido (só swing)
        if pos == -1 and not daytrade:
            for u in range(MAXU):
                if act[u]:
                    b = qty[u] * c[i] * btc_bar; cash -= b; extra[u] -= b
        if use_cdi and pos != -1 and cash > 0:
            cash *= 1 + cdi[i] * 0.85
        v = cash
        for u in range(MAXU):
            if act[u]:
                v += qty[u] * c[i] * pos
        eq[i - i0] = v
        # sinais no fechamento
        if i < i1 and not (daytrade and day_end[i]):
            if nact > 0 and ((pos == 1 and LX[i]) or (pos == -1 and SX[i])):
                pend = 2
            elif L[i] and (pos == 0 or pos == 1):
                pend = 1
            elif S[i] and (pos == 0 or pos == -1):
                pend = -1
    # fecha o que sobrou
    if nact > 0:
        for u in range(MAXU):
            if act[u]:
                px = c[i1]; val = qty[u] * px; cost = val * k
                if pos == 1:
                    cash += val - cost; g = (px - epx[u]) * qty[u]
                else:
                    cash -= val + cost; g = (epx[u] - px) * qty[u]
                pnl = g - cost - epx[u] * qty[u] * k + extra[u]
                if nt < MAXT:
                    t_ent[nt] = ent[u]; t_ex[nt] = i1; t_side[nt] = pos; t_pnl[nt] = pnl
                    t_ret[nt] = pnl / (epx[u] * qty[u]); t_why[nt] = 4; t_epx[nt] = epx[u]; t_xpx[nt] = px; nt += 1
        eq[n - 1] = cash
    return eq, nt, tcost


@njit(cache=True)
def _seg_metrics(eq, t_ent, t_ex, t_ret, nt, bounds, bars_year, cdi):
    """Métricas por segmento [a,b) (índices relativos a eq):
    0 retorno, 1 cagr, 2 sharpe do excesso sobre o CDI, 3 queda máx., 4 trades,
    5 acerto, 6 profit factor, 7 cagr do CDI líquido no segmento, 8 exposição (fração de candles posicionado)."""
    ns = len(bounds) - 1
    out = np.full((ns, 9), np.nan)
    for s in range(ns):
        a, b = bounds[s], bounds[s + 1]
        if b - a < 3:
            continue
        base = eq[a - 1] if a > 0 else eq[a]
        tot = eq[b - 1] / base - 1
        yrs = (b - a) / bars_year
        cagr = (1 + tot) ** (1 / yrs) - 1 if tot > -1 else -1.0
        m = 0.0; m2 = 0.0; peak = base; dd = 0.0; prev = base; cg = 1.0
        for i in range(a, b):
            rf = cdi[i] * 0.85
            cg *= 1 + rf
            r = eq[i] / prev - 1 - rf; prev = eq[i]
            m += r; m2 += r * r
            if eq[i] > peak:
                peak = eq[i]
            x = eq[i] / peak - 1
            if x < dd:
                dd = x
        cnt = b - a
        mu = m / cnt; var = m2 / cnt - mu * mu
        sh = mu / np.sqrt(var) * np.sqrt(bars_year) if var > 1e-14 else 0.0
        n = 0; w = 0; gp = 0.0; gl = 0.0; inm = 0
        for t in range(nt):
            if t_ex[t] >= a and t_ex[t] < b:
                n += 1
                if t_ret[t] > 0:
                    w += 1; gp += t_ret[t]
                else:
                    gl -= t_ret[t]
            e0 = max(t_ent[t], a); e1 = min(t_ex[t], b - 1)
            if e1 >= e0:
                inm += e1 - e0 + 1
        out[s, 0] = tot; out[s, 1] = cagr; out[s, 2] = sh; out[s, 3] = dd; out[s, 4] = n
        out[s, 5] = w / n if n > 0 else np.nan
        out[s, 6] = gp / gl if gl > 0 else np.nan
        out[s, 7] = cg ** (1 / yrs) - 1
        out[s, 8] = min(inm / cnt, 1.0)
    return out


class Sim:
    def __init__(self, m: Market, fee=0.0003, slip=0.0005, btc_year=0.02, div_net=0.9):
        self.m = m
        self.fee, self.slip, self.div_net = fee, slip, div_net
        self.btc_bar = btc_year / BARS_YEAR[m.tf]
        self.buf = [np.zeros(MAXT, np.int64), np.zeros(MAXT, np.int64), np.zeros(MAXT, np.int64),
                    np.zeros(MAXT), np.zeros(MAXT), np.zeros(MAXT, np.int64), np.zeros(MAXT), np.zeros(MAXT)]

    def run(self, cfg: Cfg, i0=0, i1=None, capital=10_000.0, sig=None):
        m = self.m
        i1 = len(m.c) - 1 if i1 is None else i1
        self._i0 = i0
        L, S, LX, SX = sig if sig is not None else signals(m, cfg)
        sk, sv = stop_params(cfg)
        o, h, l, c, div = m.arr
        eq, nt, tcost = _sim(o, h, l, c, div, m.cdi, m.day_end, m.atr, L, S, LX, SX, sk, sv, float(cfg.tp),
                             cfg.units, cfg.daytrade, cfg.cdi, self.fee, self.slip, self.btc_bar, self.div_net,
                             i0, i1, capital, *self.buf)
        return eq, nt, tcost

    def trades(self, nt, i0=0):
        idx = self.m.df.index
        b = self.buf
        why = np.array(["sinal", "stop", "alvo", "fim do dia", "fim"])
        return pd.DataFrame(dict(entry=idx[b[0][:nt]], exit=idx[b[1][:nt]], ei=b[0][:nt], xi=b[1][:nt],
                                 side=np.where(b[2][:nt] == 1, "C", "V"), pnl=b[3][:nt].copy(), ret=b[4][:nt].copy(),
                                 why=why[b[5][:nt]], entry_px=b[6][:nt].copy(), exit_px=b[7][:nt].copy()))

    def seg(self, eq, nt, bounds):
        off = int(self._i0)
        b = self.buf
        return _seg_metrics(eq, b[0][:nt] - off, b[1][:nt] - off, b[4], nt, np.asarray(bounds, np.int64),
                            BARS_YEAR[self.m.tf], self.m.cdi[off:])


def after_tax_total(tr: pd.DataFrame, rate: float) -> float:
    if tr.empty:
        return 0.0
    mth = tr.groupby(tr.exit.dt.to_period("M")).pnl.sum()
    carry = tax = 0.0
    for v in mth:
        v += carry
        if v > 0:
            tax += v * rate; carry = 0.0
        else:
            carry = v
    return tax


def full_grid(intraday: bool):
    for mode, eref, side, cand, rsi, xref, stop, tp, units in itertools.product(
            ["trend", "rev"], ["fast", "slow", "both", "either"], ["long", "short", "both"],
            ["any", "with", "against"], [0, 30, 40, 50], ["fast", "slow", "both", "either", "rsi"],
            ["none", "p1", "p2", "p3", "p5", "atr1", "atr2", "atr3"], [0, 2], [1, 3]):
        if tp and stop == "none":
            continue
        yield Cfg(mode, eref, side, cand, rsi, xref, stop, tp, units, daytrade=intraday)
