# Binance BTC/ETH 1D Relative-Cycle Rotation

- 标准家族名：`Binance-1D-BTCETH-Relative-Cycle-Rotation`
- 短 id：`BIN-1D-BE-RCR`
- 主状态：`explore / research line closed / HARD-GATE-FAILED / not promoted / not live-ready`
- 当前版本：无；研究结果不得自动登记版本
- 机制：BTC/ETH 共同周期方向决定多空，相对风险调整动量决定唯一持仓资产
- 资产：Binance USDⓈ-M `BTCUSDT`、`ETHUSDT`
- 周期：闭合 `1d` 信号、下一 UTC 日开盘执行；持仓期间按真实 `1h` 路径与 funding 记账
- 风险：组合总毛杠杆上限 `1.0x`，不做波动率目标或事后风险缩放
- 目标：development 净值倍数 `>=20x` 且 ordered `1h` MDD `<=20%`，再进入唯一候选审计

阅读顺序：[冻结合同](specs/binance-1d-be-rcr-p0-contract-2026-08-12.md) → [主账](binance-1d-be-rcr-core-ledger.md) → [决策日志](decision-log.md)。

本家族不是 MA7 V2，也不继承 HYPE V7.1 参数；它只继承“冻结、消融、因果归因、唯一候选、封存 OOS”的研究方法。P0–P6 全部完成后未达到 `20x/20%`，当前研究线已关闭且从未揭示 audit/prospective。
