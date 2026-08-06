# Binance-1D-MA7-Deviation-Continuation Core Ledger

## Family Identity

- Full family：`Binance-1D-MA7-Deviation-Continuation`
- Alias：`BIN-1D-MA7DC`
- Market：Binance USD-M perpetual；HYPEUSDT、BTCUSDT、ETHUSDT；完整 UTC `1d`
- Mechanism：固定 SMA7 的方向、斜率强度、价格偏离与偏离速度，验证未来趋势延续和回调重启
- Boundary：独立于 HYPE 日线 MA7/MA30 交易搜索及其 BTC/ETH 直迁；本家族第一阶段无订单

## Current State

- Current version：无；当前仅为未登记 diagnostic。
- Current status：`explore / not promoted / not live-ready`。
- Initial diagnostic：BTC long 为 `partial`，通过方向延续与斜率增量两项；ETH long 只通过 restart 增量；HYPE long/short、BTC/ETH short 均为 `not supported`。这些是证据标签，不是主状态。
- Campaign diagnostic：HYPE `2 ATR / 3–14d / cross1 / long` 只有 6 个 completed swings，低于 12 段门槛；通过对齐、及时进入和退出/净正三组门禁，但完整波段捕获中位数仅 `18.7%`、MFE 保留仅 `31.7%`，标签为 `insufficient`。截图中的约 `20.5→77` 主体上涨是约 134 日的 `3 ATR` swing；追到结束附近需 9–11 次往返，成本后只捕获约 `33%–37%` 的对数波段。
- Tolerance-exit diagnostic：单独 `0.5ATR + 两日确认` 明显恶化；叠加 `MFE>=2R / 50% giveback` 后，HYPE primary 捕获/MFE 保留中位数提高至 `24.1%/41.3%`，但只有 6 段、只过 2/5 门禁，标签 `insufficient`，最近 3m/6m 中位净结果仍为负。`1ATR` 单腿 hard stop 会在截图 5 月加速段先触发，进一步确认 position risk 与 campaign invalidation 必须分层。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Blockers：没有账户级仓位、加减仓与独立 campaign invalidation；HYPE 的视觉对齐和半 MFE 保护仍未达到 >=50% 的波段捕获/浮盈保留且主样本不足；单腿 1ATR stop 与长期 campaign 尺度冲突；BTC/ETH 结果不一致；全部历史为 researcher-exposed diagnostic。
- Locked/prospective：未建立；已查看历史不得充当新的 prospective OOS。
- Next gate：若继续 HYPE，必须把长期 `campaign state` 与实际 `risk/position state` 分层，冻结重入次数和累计 campaign 风险，再做真实 next-bar 账户回测；不能继续把一次 MA7 跌破同时当作仓位止损与长期趋势失效。BTC long 若继续，仍须独立建线，ETH 作控制。任何方向都需新 prospective OOS 才能提供 promotion 证据。

## Version Rules

- 用户明确要求登记版本前，不创建 `V1`。
- SMA 长度、状态定义、未来标签或执行时序发生实质变化，均须新合同；不能在揭示结果后静默救参。
- BTC、ETH、HYPE 可得出不同结论，不能从最终结果事后只保留赢家资产并宣称跨资产成立。

## Version Table

当前无 registered version。

## Shared Assumptions

- 数据来自仓库标准 Binance USD-M 数据湖，并要求 raw/normalized parity。
- 只聚合完整 UTC 日；日线状态在该日结束后的下一个 UTC 午夜可见。
- `SMA7` 使用当时已经闭合的最近 7 根日 K；所有未来路径只用于标签。
- 本阶段没有成交与收益回测；`0.1% fee + 4 bps` 单边不利滑点仅形成未来终值的往返成本门槛。

## Evidence Map

- [冻结验证合同](specs/binance-1d-ma7dc-initial-validation-contract-2026-08-04.md)
- [初始验证报告](diagnostics/binance-1d-ma7dc-initial-validation-2026-08-04.md)
- [Campaign 持仓轨道合同](specs/binance-1d-ma7dc-campaign-track-contract-2026-08-04.md)
- [Campaign 持仓轨道验证](diagnostics/binance-1d-ma7dc-campaign-tracking-2026-08-04.md)
- [容忍带与半 MFE 合同](specs/binance-1d-ma7dc-tolerance-exit-contract-2026-08-04.md)
- [容忍带与半 MFE 验证](diagnostics/binance-1d-ma7dc-tolerance-exit-2026-08-04.md)
- [研究脚本](scripts/research_binance_1d_ma7dc.py)
- [Campaign 审计脚本](scripts/audit_binance_1d_ma7dc_campaign_tracking.py)
- [容忍带退出审计脚本](scripts/audit_binance_1d_ma7dc_tolerance_exit.py)
- [产物说明](artifacts/README.md)
- [决策记录](decision-log.md)
