# Scripts

- [research_btc_1d_classic_cta.py](research_btc_1d_classic_cta.py)：审计 native UTC `1d` 与 `funding_rates`，按冻结文献契约构建 EWMAC + 波动率缩放仓位，并运行主口径、精确跟踪、多空归因、四条 sleeve 与 1x 买入持有对照。

复现：

```bash
uv run python research/btc/1d-classic-cta-trend/scripts/research_btc_1d_classic_cta.py --self-test
uv run python research/btc/1d-classic-cta-trend/scripts/research_btc_1d_classic_cta.py --run-date 2026-08-17
```

脚本固定引用 [multi-horizon-ema-forecast v1](../../../_shared-kernels/multi-horizon-ema-forecast/README.md) 的 EMA、成本、funding 结算和切片模块，SHA256 `63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4`。日线 EWMAC 特征与波动率缩放保留在本家族脚本中。
