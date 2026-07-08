# HYPE-5M-MA-Pullback-Scalp

- Full family name：`HYPE-5M-MA-Pullback-Scalp`（无历史别名）
- 市场/周期：Binance USD-M Futures `HYPEUSDT` perpetual `5m`
- 机制：双均线回踩 scalp——慢线定趋势、快线定回调波，HH/HL（多）或 LL/LH（空）结构确认，闭合 K 回调结束触发、下一根 open 入场、固定 TP/SL + 最长持仓超时。
- 当前状态：首轮可执行搜索与邻域稳健性完成，但尚未登记版本或进入 promotion review；`explore / not promoted / not live-ready`（观察行 `HYPE_5M_MA_PBS_R03072__base` 与其邻域 `__nb_0370`）。

## 边界

- 不是 `HYPE-5M-Micro-Scalp`、`HYPE-5M-Pullback-Trail` 的版本；与 `HYPE-1M-MA-Pullback-Scalp` 机制同源但周期/频率/成本敏感度不同，分家族管理。

## 入口

- 决策记录（兼任 interim ledger，本家族尚无登记版本）：`decision-log.md`
- 首轮可执行搜索：`diagnostics/hype-5m-ma-pullback-scalp-search-2026-06-26.md`
- 邻域稳健性：`diagnostics/hype-5m-ma-pullback-scalp-robustness-2026-06-26.md`

脚本在 `scripts/`，被报告引用的 JSON/CSV 在 `artifacts/`。候选行指标与 live 边界清单以上述报告和 decision-log 为准。
