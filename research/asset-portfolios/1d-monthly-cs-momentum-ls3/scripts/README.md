# Scripts

- [`research_binance_1d_mcsm_ls3.py`](research_binance_1d_mcsm_ls3.py)：从 `15m` Vision 月档派生日 K 与日资金费，运行全上市动量、`ADV≥1000万` 动量与反转对照，写出诊断报告。
- [`research_binance_1d_mcsm_extensions.py`](research_binance_1d_mcsm_extensions.py)：复用同一日级缓存与冻结时序，运行 long-only/基准、广度、形成期、尾部裁剪、inverse-vol、组合波动率目标、short 约束消融与 PnL attribution。

```bash
uv run python research/asset-portfolios/1d-monthly-cs-momentum-ls3/scripts/research_binance_1d_mcsm_ls3.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-ls3/scripts/research_binance_1d_mcsm_ls3.py --run-date 2026-08-18
uv run python research/asset-portfolios/1d-monthly-cs-momentum-ls3/scripts/research_binance_1d_mcsm_extensions.py --self-test
uv run python research/asset-portfolios/1d-monthly-cs-momentum-ls3/scripts/research_binance_1d_mcsm_extensions.py --run-date 2026-08-18 --force
```
