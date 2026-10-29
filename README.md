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
