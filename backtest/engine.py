"""Motor de backtest — IFR (RSI) + médias móveis, uma operação por vez.

Regras de execução (evitam olhar o futuro):
- O sinal é calculado no FECHAMENTO do candle d.
- A ordem é executada na ABERTURA do candle d+1.
- Stop é intradiário: se a mínima (compra) / máxima (venda) atingir o stop,
  sai no preço do stop — ou na abertura, se o dia já abrir além dele (gap).
- Só uma operação aberta por vez; nenhum sinal é aceito até ela fechar.

Custos e eventos:
- Emolumentos + liquidação B3 ~0,03% por lado; corretagem configurável (padrão 0).
- Slippage configurável (padrão 0,05% por lado).
- Proventos: comprado recebe (líquido aprox. 90%, por conta do IR sobre JCP);
  vendido paga 100% do provento ao doador.
- Vendido paga aluguel (BTC) ~2% a.a. sobre o valor da posição.
- IR swing trade 15% sobre lucro líquido mensal, com compensação de prejuízo
  (isenção de R$20 mil/mês ignorada — vale só para vendas pequenas e não para short).
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd


def load(ticker: str, path: str = "data") -> pd.DataFrame:
    df = pd.read_csv(f"{path}/{ticker}.csv", parse_dates=["date"]).set_index("date")
    df = df[(df.volume > 0) & (df.close > 0)].copy()
    return df


def rsi_wilder(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


@dataclass(frozen=True)
class Config:
    mode: str = "rev"        # rev = reversão (compra abaixo das médias) | trend = tendência (compra acima)
    side: str = "both"       # long | short | both
    rsi_th: float | None = 30  # rev compra se RSI < th (vende se > 100-th); trend compra se RSI > 100-th
    candle: str = "any"      # any | with (candle na cor do trade) | against (cor contrária)
    exit: str = "ma5"        # ma5 | ma10 | both | rsi  (saída quando o fechamento passa para o outro lado)
    stop: float | None = 0.03
    fast: int = 5
    slow: int = 10
    rsi_n: int = 14
    rsi_lo: float = 30
    rsi_hi: float = 70
    regime: int | None = None  # filtro: só compra acima da MM longa (e só vende abaixo)

    def label(self):
        r = "sem IFR" if self.rsi_th is None else f"IFR {self.rsi_th:g}"
        s = "sem stop" if self.stop is None else f"stop {self.stop:.0%}"
        g = "" if self.regime is None else f"/filtro MM{self.regime}"
        return f"{self.mode}/{self.side}/{r}/candle {self.candle}/saída {self.exit}/{s}/MM{self.fast}-{self.slow}{g}"


@dataclass
class Costs:
    fee: float = 0.0003       # emolumentos + liquidação por lado
    slippage: float = 0.0005  # por lado
    brokerage: float = 0.0    # R$ por ordem
    btc_year: float = 0.02    # aluguel a.a. para vendido
    div_net_long: float = 0.90
    tax: float = 0.15


def prepare(df: pd.DataFrame, cfg: Config) -> dict:
    c = df.close
    f = c.rolling(cfg.fast).mean()
    s = c.rolling(cfg.slow).mean()
    r = rsi_wilder(c, cfg.rsi_n)
    green = c > df.open
    red = c < df.open
    below = (c < f) & (c < s)
    above = (c > f) & (c > s)

    if cfg.mode == "rev":
        long_sig, short_sig = below.copy(), above.copy()
        if cfg.rsi_th is not None:
            long_sig &= r < cfg.rsi_th
            short_sig &= r > 100 - cfg.rsi_th
    else:
        long_sig, short_sig = above.copy(), below.copy()
        if cfg.rsi_th is not None:
            long_sig &= r > 100 - cfg.rsi_th
            short_sig &= r < cfg.rsi_th
    if cfg.candle == "with":
        long_sig &= green; short_sig &= red
    elif cfg.candle == "against":
        long_sig &= red; short_sig &= green
    if cfg.regime:
        lt = c.rolling(cfg.regime).mean()
        long_sig &= c > lt
        short_sig &= c < lt
    if cfg.side == "long":
        short_sig[:] = False
    elif cfg.side == "short":
        long_sig[:] = False

    if cfg.exit == "ma5":
        lx, sx = (c > f, c < f) if cfg.mode == "rev" else (c < f, c > f)
    elif cfg.exit == "ma10":
        lx, sx = (c > s, c < s) if cfg.mode == "rev" else (c < s, c > s)
    elif cfg.exit == "both":
        lx, sx = (above, below) if cfg.mode == "rev" else (below, above)
    else:  # rsi: sai no extremo oposto do IFR
        lx, sx = (r > cfg.rsi_hi, r < cfg.rsi_lo)
    valid = f.notna() & s.notna() & r.notna()
    return dict(L=(long_sig & valid).values, S=(short_sig & valid).values,
                LX=lx.values, SX=sx.values)


# CDI anual aproximado (referência; 2026 estimado). Usado para remunerar o caixa parado.
CDI_ANUAL = {2010: .0975, 2011: .1160, 2012: .0840, 2013: .0806, 2014: .1081, 2015: .1324, 2016: .1400,
             2017: .0993, 2018: .0642, 2019: .0596, 2020: .0276, 2021: .0442, 2022: .1237, 2023: .1304,
             2024: .1087, 2025: .1430, 2026: .1450}


def cdi_daily(idx) -> np.ndarray:
    return np.array([(1 + CDI_ANUAL.get(d.year, .10)) ** (1 / 252) - 1 for d in idx])


def run(df: pd.DataFrame, cfg: Config, start=None, end=None, capital=10_000.0,
        costs: Costs = Costs(), sig: dict | None = None, cdi: bool = False):
    sig = sig or prepare(df, cfg)
    idx = df.index
    o, h, l, c = (df[k].values for k in ("open", "high", "low", "close"))
    div = df["dividends"].values if "dividends" in df else np.zeros(len(df))
    i0 = 0 if start is None else idx.searchsorted(pd.Timestamp(start))
    i1 = len(df) - 1 if end is None else idx.searchsorted(pd.Timestamp(end), side="right") - 1

    cash = capital
    pos = 0  # +1 comprado, -1 vendido
    qty = 0
    entry_px = stop_px = 0.0
    entry_i = 0
    pend = 0  # ordem pendente: +1 abrir compra, -1 abrir venda, 2 fechar
    trades = []
    eq = np.empty(i1 - i0 + 1)
    tcost = tdiv = tbtc = 0.0
    trade_extra = 0.0  # proventos/aluguel acumulados na operação corrente
    cdi_r = cdi_daily(idx) if cdi else np.zeros(len(df))
    tc = lambda v: abs(v) * (costs.fee + costs.slippage) + costs.brokerage

    def close_pos(i, px, why):
        nonlocal cash, pos, qty, tcost, trade_extra
        val = qty * px
        k = tc(val)
        tcost += k
        if pos == 1:
            cash += val - k
            gross = (px - entry_px) * qty
        else:
            cash -= val + k
            gross = (entry_px - px) * qty
        ek = tc(entry_px * qty)
        trades.append(dict(entry=idx[entry_i], exit=idx[i], side="C" if pos == 1 else "V",
                           entry_px=entry_px, exit_px=px, qty=qty, days=i - entry_i,
                           pnl=gross - k - ek + trade_extra,
                           ret=(gross - k - ek + trade_extra) / (entry_px * qty), why=why))
        pos = 0; qty = 0; trade_extra = 0.0

    for i in range(i0, i1 + 1):
        # 0) proventos: direito de quem estava posicionado no fechamento anterior (data-com)
        if pos != 0 and div[i] > 0:
            v = div[i] * qty
            if pos == 1:
                v *= costs.div_net_long
                cash += v; trade_extra += v; tdiv += v
            else:
                cash -= v; trade_extra -= v; tdiv -= v
        # 1) ordens pendentes na abertura
        if pend == 2 and pos != 0:
            close_pos(i, o[i], "sinal")
        elif pend in (1, -1) and pos == 0:
            px = o[i]
            q = int((cash / (px * (1 + costs.fee + costs.slippage))))
            if q > 0:
                k = tc(q * px); tcost += k
                if pend == 1:
                    cash -= q * px + k
                else:
                    cash += q * px - k
                pos, qty, entry_px, entry_i = pend, q, px, i
                if cfg.stop is not None:
                    stop_px = px * (1 - cfg.stop) if pos == 1 else px * (1 + cfg.stop)
        pend = 0
        # 2) stop intradiário
        if pos != 0 and cfg.stop is not None:
            if pos == 1 and l[i] <= stop_px:
                close_pos(i, min(o[i], stop_px) if i > entry_i else stop_px, "stop")
            elif pos == -1 and h[i] >= stop_px:
                close_pos(i, max(o[i], stop_px) if i > entry_i else stop_px, "stop")
        # 3) aluguel do vendido
        if pos == -1:
            b = qty * c[i] * costs.btc_year / 252
            cash -= b; trade_extra -= b; tbtc += b
        # caixa parado rende CDI (líquido aprox. de IR 15%)
        if pos == 0 and cash > 0:
            cash *= 1 + cdi_r[i] * 0.85
        # 4) marcação a mercado
        eq[i - i0] = cash + (qty * c[i] if pos == 1 else -qty * c[i] if pos == -1 else 0)
        # 5) sinais no fechamento -> executam amanhã
        if i < i1:
            if pos == 1 and sig["LX"][i]:
                pend = 2
            elif pos == -1 and sig["SX"][i]:
                pend = 2
            elif pos == 0:
                if sig["L"][i]:
                    pend = 1
                elif sig["S"][i]:
                    pend = -1
    if pos != 0:
        close_pos(i1, c[i1], "fim")
        eq[-1] = cash

    equity = pd.Series(eq, index=idx[i0:i1 + 1])
    tr = pd.DataFrame(trades)
    return equity, tr, dict(costs=tcost, dividends=tdiv, btc=tbtc)


def after_tax(tr: pd.DataFrame, capital: float, rate=0.15) -> float:
    """Resultado final após IR mensal 15% com compensação de prejuízo."""
    if tr.empty:
        return capital
    m = tr.groupby(tr.exit.dt.to_period("M")).pnl.sum()
    carry = 0.0; tax = 0.0
    for v in m:
        v += carry
        if v > 0:
            tax += v * rate; carry = 0.0
        else:
            carry = v
    return capital + tr.pnl.sum() - tax


def metrics(equity: pd.Series, tr: pd.DataFrame, extra: dict, capital=10_000.0) -> dict:
    yrs = (equity.index[-1] - equity.index[0]).days / 365.25
    final = equity.iloc[-1]
    ret = equity.pct_change().dropna()
    dd = equity / equity.cummax() - 1
    n = len(tr)
    wins = tr[tr.pnl > 0] if n else tr
    loss = tr[tr.pnl <= 0] if n else tr
    gp, gl = (wins.pnl.sum(), -loss.pnl.sum()) if n else (0, 0)
    net_tax = after_tax(tr, capital)
    in_mkt = tr.days.sum() / max(len(equity), 1) if n else 0
    return dict(
        retorno=final / capital - 1,
        cagr=(final / capital) ** (1 / yrs) - 1 if yrs > 0 and final > 0 else np.nan,
        ret_pos_ir=net_tax / capital - 1,
        max_dd=dd.min(),
        sharpe=ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0,
        trades=n,
        acerto=len(wins) / n if n else np.nan,
        ganho_medio=wins.ret.mean() if len(wins) else 0,
        perda_media=loss.ret.mean() if len(loss) else 0,
        payoff=(wins.ret.mean() / -loss.ret.mean()) if len(wins) and len(loss) and loss.ret.mean() < 0 else np.nan,
        profit_factor=gp / gl if gl > 0 else np.nan,
        dias_medios=tr.days.mean() if n else 0,
        exposicao=in_mkt,
        stops=(tr.why == "stop").mean() if n else 0,
        custos=extra["costs"], proventos=extra["dividends"], aluguel=extra["btc"],
        final=final,
    )


def buy_hold(df: pd.DataFrame, start, end, capital=10_000.0, costs: Costs = Costs()):
    """Compra e segura com proventos reinvestidos (aprox.) — referência."""
    d = df.loc[start:end]
    px0 = d.open.iloc[0] * (1 + costs.fee + costs.slippage)
    units = capital / px0
    vals = []
    for dt, row in d.iterrows():
        if row.dividends > 0:
            units += units * row.dividends * costs.div_net_long / row.close
        vals.append(units * row.close)
    return pd.Series(vals, index=d.index)
