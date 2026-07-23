# HYPE-1H-Bollinger-Keltner-Squeeze-Breakout

- Full family name：`HYPE-1H-Bollinger-Keltner-Squeeze-Breakout`
- Alias：`HYPE-1H-BKSB`
- 市场/周期：Binance HYPEUSDT 永续 `1h`
- 机制：Bollinger 完整进入 Keltner 后形成 squeeze，释放并突破压缩区间时顺方向交易。
- 当前状态：`explore / not promoted / not live-ready`；冻结基础规则仅近期局部改善，全样本失败，未登记版本。

## 边界

- 这是 `1h` 独立 family，不是 1H-AR、1H-MMTF 或其他周期 BKSB 的版本。
- 只复用冻结共享内核与标准数据湖，不继承其他家族参数、证据或状态。

## 入口

- [hype-1h-bksb-core-ledger.md](hype-1h-bksb-core-ledger.md)
- [基础策略诊断](diagnostics/hype-1h-bksb-baseline-2026-07-23.md)
- [decision-log.md](decision-log.md)
- [scripts/README.md](scripts/README.md)
- [artifacts/README.md](artifacts/README.md)

