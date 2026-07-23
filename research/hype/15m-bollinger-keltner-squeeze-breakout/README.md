# HYPE-15M-Bollinger-Keltner-Squeeze-Breakout

- Full family name：`HYPE-15M-Bollinger-Keltner-Squeeze-Breakout`
- Alias：`HYPE-15M-BKSB`
- 市场/周期：Binance HYPEUSDT 永续 `15m`
- 机制：Bollinger 完整进入 Keltner 后形成 squeeze，释放并突破压缩区间时顺方向交易。
- 当前状态：`explore / not promoted / not live-ready`；冻结基础规则未通过最低可行性门槛，未登记版本。

## 边界

- 这是 `15m` 独立 family，不是纯 Keltner、MMTF 或其他周期 BKSB 的版本。
- 只复用冻结共享内核与标准数据湖，不继承其他家族参数、证据或状态。

## 入口

- [hype-15m-bksb-core-ledger.md](hype-15m-bksb-core-ledger.md)
- [基础策略诊断](diagnostics/hype-15m-bksb-baseline-2026-07-23.md)
- [decision-log.md](decision-log.md)
- [scripts/README.md](scripts/README.md)
- [artifacts/README.md](artifacts/README.md)

