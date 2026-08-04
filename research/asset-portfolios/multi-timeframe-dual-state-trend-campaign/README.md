# Binance-MTF-Dual-State-Trend-Campaign

- Full family：`Binance-MTF-Dual-State-Trend-Campaign`（alias：`BIN-MTF-DSTC`）。
- 市场/资产：Binance USD-M perpetual；HYPEUSDT primary，BTCUSDT、ETHUSDT 独立 control。
- 周期：完整 UTC `1d` 定义 Campaign，`4h` 结构、`1h` 回调、`15m` restart/next-open 执行。
- 机制：把长期 Campaign 失效与当前 position/lot stop 分成两个状态；小 Probe 试错，只有真实浮盈和新回调重启共同出现才分层加仓，并独立比较慢速结构退出与半 MFE 保护。
- 当前状态：`explore / not promoted / not live-ready`；Goal active，尚无 registered version 或 runner。

## 边界

- 是 `BIN-MTF-PTC` HARD-GATE-FAILED 后的 materially new successor，不继承旧 continuation meter、24h failure exit、参数、绩效或状态。
- 独立于 `HYPE-15M-MTPP`；不读取其 `[2026-08-02, 2026-11-02)` prospective OOS，也不继承 RSI/KDJ 入场证据。
- 数据边界按资产分离：BTC/ETH 截至 `2026-08-03 11:45 UTC`，HYPE 必须在查询层截断至 `2026-08-01 15:15 UTC`。
- 当前 MA7 研究只提供设计约束：MA7 是 Campaign 环境量尺，不是单独交易信号；单独 `0.5ATR` 容忍带失败，半 MFE 只有不足样本的局部线索。

## 入口

- [主账](binance-mtf-dstc-core-ledger.md)
- [决策记录](decision-log.md)
- [Goal 合同](specs/binance-mtf-dstc-goal-contract-2026-08-04.md)
- [数据与评估合同](specs/binance-mtf-dstc-data-evaluation-contract-2026-08-04.md)
- [实验注册表](specs/binance-mtf-dstc-experiment-registry-2026-08-04.md)
- [脚本说明](scripts/README.md)
- [产物说明](artifacts/README.md)
