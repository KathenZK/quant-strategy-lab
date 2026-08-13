# HYPE-4H-MA7-RSI6-Asymmetric-Reversal Core Ledger

## Family Identity

- Full name：`HYPE-4H-MA7-RSI6-Asymmetric-Reversal`
- Alias：`HYPE-4H-MA7-RSI6-AR`
- Market / timeframe：Binance USD-M `HYPEUSDT` perpetual，UTC `4h`
- Mechanism：SMA7 触发做多，MA7 下穿与三根 RSI6 overbought memory 共同触发反手做空，RSI6 超卖后平空等待。
- Collision：不是 `HYPE-4H-MA7-Close-Reversal` 或 `HYPE-4H-MA7-ABT` 的版本。

## Current State

- Current version：无。
- Status：`explore / not promoted / not live-ready`。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Baseline：原生相位全期 base `+113.10%`、MDD `-57.76%`、PF `1.36`；最后 `120d +30.96%`，同期持有 `+44.99%`。
- Robustness：`8 bps=+99.75%`、额外延迟一根 `4h=+110.08%`；但 `1h/2h` 相位为 `-51.65% / -78.77%`，12 个 rolling 90 日窗口仅 6 个为正。
- V2 Cross-Reentry：空头重新站上 SMA7 时直接反多；全期降至 `+12.16%`、MDD `-66.94%`、PF `1.03`，short PF `0.83`，不采纳。
- Blockers：严重相位不稳定；无 hard stop 或交易所驻留保护；原生/`2h` 最大有效杠杆约 `2.15x / 6.96x`；无 prospective OOS。
- Next gate：停止把原生相位正收益视为稳健候选；后续必须先解决 bar alignment 与保护合同。当前不登记。

## Version Rules

- `Vx` 只在用户明确要求登记时创建。
- 改 MA 类型/长度、RSI 公式/阈值、三根语义、平空后的动作或保护规则均改变版本身份。
- 成本、相位、近期和 rolling 结果是审计，不构成版本。

## Version Table

| Observation | Status | Role | Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| SMA7-RSI6 asymmetric baseline | `explore / not promoted / not live-ready` | 用户指定零搜索状态机 | 原生 `+113.10%`；`1h/2h=-51.65%/-78.77%` | [基准诊断](diagnostics/hype-4h-ma7-rsi6-asymmetric-reversal-baseline-2026-08-06.md) | 有趣但相位失败，不登记 |
| V2 Cross-Reentry observation | `explore / not promoted / not live-ready` | `short -> long` 增加 MA7 上穿直接反手 | `+12.16%`；MDD `-66.94%`；PF `1.03` | [V2 诊断](diagnostics/hype-4h-ma7-rsi6-cross-reentry-v2-observation-2026-08-07.md) | 无超额且 short 腿转亏，不采纳 |

## Shared Assumptions

- TradingView/Wilder `RSI6`；最近三根中任一严格 `>70`。
- 闭合 `4h` 产生信号，下一根 open 成交；约 `1x`、非加仓。
- Binance fee `0.001/fill`、slippage `4 bps/fill`、实际 funding。

## Evidence Map

- [家族入口](README.md)
- [冻结合同](specs/hype-4h-ma7-rsi6-asymmetric-reversal-contract-2026-08-06.md)
- [基准诊断](diagnostics/hype-4h-ma7-rsi6-asymmetric-reversal-baseline-2026-08-06.md)
- [完整交易路径 HTML](artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_trade_path_2026-08-06.html)
- [V2 观察合同](specs/hype-4h-ma7-rsi6-cross-reentry-v2-observation-contract-2026-08-07.md) · [V2 诊断](diagnostics/hype-4h-ma7-rsi6-cross-reentry-v2-observation-2026-08-07.md) · [V2 交易路径 HTML](artifacts/hype_4h_ma7_rsi6_v2_cross_reentry_trade_path_2026-08-07.html)
- [机器摘要](artifacts/hype_4h_ma7_rsi6_asymmetric_reversal_summary_2026-08-06.json)
- [复现脚本](scripts/research_hype_4h_ma7_rsi6_asymmetric_reversal.py) · [HTML 渲染脚本](scripts/render_hype_4h_ma7_rsi6_trade_path.py)
- [决策记录](decision-log.md)
- [机器证据](artifacts/README.md)
