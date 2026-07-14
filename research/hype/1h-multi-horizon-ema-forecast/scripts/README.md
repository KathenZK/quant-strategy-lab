# Scripts

- [research_hype_1h_multi_horizon_ema_forecast.py](research_hype_1h_multi_horizon_ema_forecast.py)：校验共享内核 SHA，读取并审计标准数据湖，运行四条 EMA sleeve、加权组合、`0.10` 调仓缓冲和 1x 永续买入持有对照，生成报告与 artifacts。

复现：

```bash
uv run python research/hype/1h-multi-horizon-ema-forecast/scripts/research_hype_1h_multi_horizon_ema_forecast.py --run-date 2026-07-14
```

脚本固定引用 [multi-horizon-ema-forecast v1](../../../_shared-kernels/multi-horizon-ema-forecast/README.md)，SHA256 `63d754088ac55b958b5a5536d4ae8f5049d6b6c9c48a0fca7dc89c770d6e31c4`。
