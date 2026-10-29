# autotrade

Backtest e (futuramente) automação de swing trade na B3.

## Estrutura

- `scripts/fetch_data.py` — baixa histórico diário (Yahoo Finance + brapi) para `data/`.
- `.github/workflows/fetch-data.yml` — roda a coleta no GitHub Actions (em todo push do script e em dias úteis às 19h17 BRT). Para usar a brapi além dos ativos grátis, crie o secret `BRAPI_TOKEN` no repositório.
- `backtest/engine.py` — motor: sinal no fechamento, execução na abertura seguinte, stop intradiário, custos B3, slippage, proventos (data-com), aluguel de short, IR mensal, CDI opcional no caixa.
- `backtest/grid.py` — grade de 1.152 configurações em treino (2012–19), validação (2020–22) e teste (2023–26).
- `backtest/validate.py`, `backtest/validate2.py` — candidatas em 11 ativos, com e sem CDI.
- `backtest/report_data.py` — dados do relatório de PETR4.
- `results/` — CSVs com todos os resultados. `report/relatorio.html` — relatório visual.

## Grade ampla (v2)

- `backtest/engine2.py` — motor compilado (numba): entrada acima/abaixo de MM5, MM10, das duas ou de qualquer uma; candle a favor/contra; IFR opcional; saída por média ou IFR; stop % ou ATR; alvo; até 3 entradas; day trade (zera no fim do pregão, IR 20%); CDI no caixa.
- `backtest/grid2.py` — 86.400 configurações × 54 pares ativo/timeframe (semanal, diário, 1h swing e day trade, 15 e 5 min). Grava em `results/grid2/` (fora do git; regenere com `python backtest/grid2.py`).
- `backtest/noise.py` — controle de sorte com séries sintéticas por bootstrap em blocos.
- `backtest/analyze2.py` → `results/summary2.json`. `backtest/export_showcase.py` → `report/data/` para o simulador.
- `scripts/fetch_intraday.py` — candles de 60/15/5 min, acumulados a cada execução do workflow.
- `report/laboratorio.html` — relatório com simulador candle a candle.

## Rodar

```bash
pip install pandas numpy yfinance
python scripts/fetch_data.py PETR4 VALE3
python backtest/grid.py PETR4
python backtest/validate2.py
```

## Resultado (29/10/2026)

- Estratégia original (reversão IFR 30/70 + MM5/10, compra e venda, stop 3%): PETR4 2012–26 terminou em −0,4%; mediana dos 11 ativos negativa nos três períodos.
- Melhor variação: **pullback em tendência** — compra candle vermelho acima das MM5 e MM10, sai no fechamento abaixo da MM10, sem stop, só comprado, caixa no CDI. Mediana dos ativos: 4,5% / 7,5% / 14,3% a.a. (treino/validação/teste) contra CDI líquido de 8,1% / 5,5% / 11,2%, com quedas de 20–40%. Vantagem pequena, ainda não suficiente para operar dinheiro real.

### Grade ampla (29/10/2026)

- Sem CDI no caixa, só ~3% das combinações diárias bateram o CDI no teste (2023–26). As robustas (positivas em treino e validação) ficaram, na mediana, 1,5 p.p. abaixo do CDI.
- Séries sintéticas sem padrão geraram "vencedoras" tão boas quanto as reais: não há evidência de vantagem além do acaso.
- Destaques para operar no papel: reversão IFR 30→70 com stop de 1 ATR (bateu o CDI em 7 de 11 ativos no teste), pullback em tendência e tendência com IFR > 60, todas só compradas e com caixa no CDI.
- Day trade 1h: só 5% das combinações bateram o CDI no teste. 15 e 5 min: só 60 dias de dados, inconclusivo.
