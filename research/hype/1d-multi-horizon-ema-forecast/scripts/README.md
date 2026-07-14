# Scripts

- [research_hype_1d_multi_horizon_ema_forecast.py](research_hype_1d_multi_horizon_ema_forecast.py)：从通过质量门的标准 `1h` 数据湖聚合完整 UTC 日 K，构建经典 EWMAC forecast，运行四条 sleeve、加权组合、`0.10` 调仓缓冲和 1x 永续买入持有对照。

复现：

```bash
uv run python research/hype/1d-multi-horizon-ema-forecast/scripts/research_hype_1d_multi_horizon_ema_forecast.py --run-date 2026-07-14
```

脚本固定引用 [multi-horizon-ema-forecast v1](../../../_shared-kernels/multi-horizon-ema-forecast/README.md) 的执行、成本、funding 和切片模块，SHA256 `63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4`；日线 EWMAC 特征构建保留在本家族脚本中。
