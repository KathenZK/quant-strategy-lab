# Binance-1H-Cross-Sectional-LightGBM-Selector

- 别名：`BIN-1H-CSLGBM`
- 市场：Binance USD-M USDT 永续合约，`1h`。
- 机制：point-in-time 动态币池上构建横截面因子，使用 LightGBM 回归、分类与排序模型预测未来净相对收益，再由 long-only、long-short 或全局单仓组合执行。
- 当前状态：`explore / not promoted / not live-ready`；尚无登记版本，`V1` 保留给首个冻结且通过研究门槛的候选。

## 边界

- 本家族不是固定六币的 `BIN-15M-AS6S`、`BIN-1H-ML6AS` 或 `BIN-1H-AR-MAE`，不得复用其币池、腿参数、版本号或绩效结论。
- 当前只做研究和数据补齐，不创建 live spec，不修改 `quant-runner`。

## 入口

- [Core ledger](binance-1h-cslgbm-core-ledger.md)
- [Decision log](decision-log.md)
- [冻结研究契约](specs/binance-1h-cslgbm-research-contract-2026-07-17.md)
- `scripts/`：历史合约清单、数据同步、因子/标签、模型和回测脚本。
- `artifacts/`：动态币池、数据质量、模型、预测和逐笔证据。
