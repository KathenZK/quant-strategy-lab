# HYPE-1M-MA-Pullback-Scalp

- Full family name：`HYPE-1M-MA-Pullback-Scalp`（无历史别名）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `1m`
- 机制：双均线回踩 scalp——慢线定趋势、快线定回调波，HH/HL 或 LL/LH 结构确认，闭合 K 触发、下一根 open 入场、固定 TP/SL + 最长持仓超时。
- 当前状态：`explore / not promoted / not live-ready`。首轮可执行搜索 `6,740` 组配置在该执行/成本模型下 `0` 个通过 paper gate；`>=60` 笔样本无盈利配置。

## 边界

- 不是 `HYPE-1M-EMA-Crossover`（crossover 事件研究）的版本；与 `HYPE-5M-MA-Pullback-Scalp` 机制同源但周期不同，分家族管理。

## 入口

- 决策记录（兼任 interim ledger，本家族无登记版本）：`decision-log.md`
- 首轮可执行搜索（not-promoted 证据）：`diagnostics/hype-1m-ma-pullback-scalp-search-2026-06-26.md`

脚本在 `scripts/`，被报告引用的 JSON/CSV 在 `artifacts/`。数据质量与 live 边界清单以上述报告为准。
