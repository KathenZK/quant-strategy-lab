# Binance-1H-Price-Impulse-Campaign

- Full family：`Binance-1H-Price-Impulse-Campaign`（alias：`BIN-1H-PIC`）。
- 市场：Binance USD-M perpetual；候选执行资产 ETH，BTC/HYPE/SOL 为同规则对照。
- 周期：完整 `1h` bar；每日固定 UTC 观察窗；最长 `14d` campaign。
- 机制：只用价格位移与过去波动；`4h` impulse admission 后以 25% probe 试错，MFE 确认后分层 add，半回吐只去新增层，funding 后持续维护 stop-out 风险。
- 当前状态：`explore / not promoted / not live-ready`；尚无 registered version、live spec 或 runner。
- 当前结论：V2 ETH base `+47.93% / Sharpe 0.82 / MDD -11.05%`，硬风险违规 0；最近 6m `-0.23%` 未过冻结门禁，禁止上线。

## 边界

- 本家族是从趋势 habitat 进入订单状态机的独立策略线，不继承 `BIN-1H-FATHA` 的诊断身份，也不继承任何 HYPE 策略版本。
- `BIN-1H-FATHA` 已揭示 ETH `4h` onset 结果，所以本轮历史回测只能做执行与失败筛查，不能制造新的未见 OOS。
- V0 固定 quantity；V1/V2 已在研究账本执行真实 lot/quantity resize，但 quant-runner 尚未实现同方向 partial resize、LIFO lot/stop parity 与 funding 后 risk trim。

## 入口

- [主账](binance-1h-pic-core-ledger.md)
- [决策记录](decision-log.md)
- [冻结合同](specs/binance-1h-pic-v0-contract-2026-08-03.md)
- [V1 分层候选合同](specs/binance-1h-pic-v1-layered-contract-2026-08-03.md)
- [V2 风险不变量合同](specs/binance-1h-pic-v2-risk-invariant-contract-2026-08-03.md)
- [V0–V2 初始研究结论](diagnostics/binance-1h-pic-v0-v2-initial-research-2026-08-03.md)
- [脚本](scripts/README.md)
- [产物](artifacts/README.md)
