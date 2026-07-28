# Scripts — BIN-1D-TSMOM-VT

一次性研究脚本。`1d` 数据复用 [`emax_1d_derived` 缓存](../../1d-ema-cross-lightgbm-event-selector/scripts/README.md)（已审计 `1h` 归档 UTC 日边界重采样）；连接器与资金费加载复用 15m 家族冻结引擎 [`emax_common.py`](../../15m-ema-cross-lightgbm-event-selector/scripts/emax_common.py) 的纯函数。产物落 [../artifacts/](../artifacts/README.md)。

- [`run_tsmom_vt_demo.py`](run_tsmom_vt_demo.py)：P0 演示基线（TSMOM 符号集成 + 两层 vol targeting + 成本/资金费归因），执行 [演示契约](../specs/bin-1d-tsmom-vt-demo-contract-2026-07-27.md)。
