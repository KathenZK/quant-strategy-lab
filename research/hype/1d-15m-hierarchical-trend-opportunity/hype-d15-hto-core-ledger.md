# HYPE-1D-15M-Hierarchical-Trend-Opportunity Core Ledger

## Family Identity

- Full family name：`HYPE-1D-15M-Hierarchical-Trend-Opportunity`
- Alias：`HYPE-D15-HTO`
- Market / exchange / symbol / timeframe：Binance USD-M Futures / `HYPEUSDT` / `1d` regime + `15m` execution
- Mechanism summary：前一完整 UTC 日确定方向与风险许可，`15m` 闭合 K 线寻找同向突破、回踩恢复、动量扩张或均线延续机会。
- Boundary：独立家族；不继承其他 HYPE 家族的身份、参数、版本和结论。

## Current State

- Current version(s)：`HYPE-D15-HTO-V1`、`V2`、`V3`
- Current status：`registered / not promoted / not live-ready`
- Runner / dry-run / live status：无。
- Live-readiness blockers：V3 prefit 年化 `1.838x < 10x` 且 MDD `20.98% >= 20%`；locked OOS 净收益 `-29.76%`、胜率 `29.41%`、MDD `36.75%`；参数邻域命中率为 0，真实 `1m` 相位失败；无 runner parity、重启恢复、拒单和 missing-bar fail-closed 证据。
- Next decision gate：本机制停止 promotion；若重开，必须使用 materially new mechanism 与 `2026-07-29 03:00 UTC` 之后的全新 prospective OOS，不得复用已揭示 OOS 调参。

## Version Rules

- Registration / freeze：只固定版本身份并更新本表，默认状态 `registered`，不表示 promotion。
- `V1`：首个完成 prefit 搜索并冻结的原始日线方向 + `15m` 择时版本。
- `V2`：只允许删除经逐项消融证明 dormant/path-equal 的参数或部件。
- `V3`：在 V2 有效参数面上完成调优后冻结；不得读取 locked OOS 选优。
- New version trigger：成交路径、日线状态、入场族、退出族或风险合同发生变化。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `HYPE-D15-HTO-V1` | `registered / not promoted / not live-ready` | 5 因子日线投票 + `15m` Donchian 入场的原始广搜冻结边界 | prefit `1.488x` 年化 / `62.07%` 胜率 / `18.85%` MDD / 58 笔 | [V1 搜索产物](artifacts/hype_d15_hto_v1_search_2026-07-29.json)，[全消融](ablations/hype-d15-hto-v1-full-ablation-2026-07-29.md) | 年化失败；不晋升 |
| `HYPE-D15-HTO-V2` | `registered / not promoted / not live-ready` | 删除 Supertrend、日线 ADX 门槛、RSI/回踩/扩张等 dormant 槽位的 clean-equivalent | 与 V1 trade signature 完全一致 | [V3 调优产物中的等价证明](artifacts/hype_d15_hto_v3_tune_2026-07-29.json) | 只精简接口，不增加绩效证据 |
| `HYPE-D15-HTO-V3` | `registered / not promoted / not live-ready` | clean 参数面 120,000 组调优后的最终冻结版本 | prefit `1.838x / 60.00% / 20.98% / 50`；OOS `0.242x / 29.41% / 36.75% / 17` | [冻结规格](specs/hype-d15-hto-v3-spec.md)，[prefit 审计](diagnostics/hype-d15-hto-v3-prefit-robustness-2026-07-29.md)，[OOS 报告](diagnostics/hype-d15-hto-v3-locked-oos-final-2026-07-29.md) | promotion review FAIL；不创建 live spec 或 runner |

## Shared Assumptions

- Data：标准数据湖 Binance `HYPEUSDT` 永续 `15m` raw/normalized；日线只由 96 根完整 `15m` 聚合。
- Cost：每次成交手续费 `0.001`，单次成交不利滑点 `4 bps`，按实际持仓区间计资金费。
- Execution timing：只用闭合 K；日线状态至少滞后一完整 UTC 日；`15m` 信号下一根开盘成交。
- Position sizing：单一净仓，最高 `3x` 杠杆，无隐含加仓。
- Funding / carry：按持仓方向和事件时间逐笔计入。

## Evidence Map

- Specs：[V3 冻结规格](specs/hype-d15-hto-v3-spec.md)
- Diagnostics / ablations：[最终决策报告](diagnostics/hype-d15-hto-final-decision-2026-07-29.md) / [V1 全消融](ablations/hype-d15-hto-v1-full-ablation-2026-07-29.md)
- Scripts / artifacts：[脚本说明](scripts/README.md) / [产物说明](artifacts/README.md)
