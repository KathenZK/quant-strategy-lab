# HYPE-EMA-X Core Ledger

## Family Identity

- 完整家族名：`HYPE-EMA-Crossover`
- 别名：`HYPE-EMA-X`
- 市场：Binance USD-M `HYPEUSDT` 永续，`15m`
- 机制：EMA96/384 regime、趋势质量过滤、late re-entry、结构/预警退出。
- 边界：不是 HYPE-EMA-TB；裸 `V15` 等版本号不得脱离家族使用。

## Current State

- 当前版本：`HYPE-EMA-X-V18`。
- 状态：`dry-run / forward-test required / not live-ready`；V15–V17.1 为 `registered / not promoted / not live-ready`。
- V18 与 V17.1 逐笔逻辑和冻结指标相同，只删除 noop 与关闭模块。
- 共享 15m 行情组 2026-07-21→07-30 停摆区间观察作废；恢复见 [group halt](runner-tracking/hype-ema-x-runner-2026-07-30-group-halt.md)。
- 下一门：parity、真实成交/保护单、重启恢复和 online open/close reconciliation；实际授权只以 quant-runner 为准。

## Version Rules

- V1–V14 是从裸交叉、regime 持有、退出状态机到 late re-entry 的历史演化。
- V15 是高质量低回撤版；V16 放宽趋势分；V17 组合 HQ/LQ；V17.1 仅调整 HQ sizing；V18 仅清理参数表。
- sizing/文档清理不构成新 signal-quality 突破；登记不代表 promotion。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `V15` | registered / not promoted / not live-ready | `atr18 + trend_score>=7` 高质量信号 | 1Y `+2303.65%`、DD `-17.79%`、win `90.32%`、31 笔 | [V15/V16 规格](notes/hype-ema-x-v15-v16-promoted-strategy-specs.md) | 稳健观察 |
| `V16` | registered / not promoted / not live-ready | 只保留 `atr18`，放宽 trend score | `+3202.92%`、DD `-28.19%`、win `86.84%`、38 笔 | [状态搜索](notes/hype-ema-x-v16-v17-trend-state-search.md) | 高收益高回撤 |
| `V17` | registered / not promoted / not live-ready | V15 HQ + 受限 V16 LQ 卫星 | `+2910.74%`、DD `-17.79%`、win `90.91%`、33 笔 | [hybrid 消融](ablations/hype-ema-x-v17-hybrid-ablation.md) | 平衡主候选 |
| `V17.1` | registered / not promoted / not live-ready | V17 HQ sizing `1.0→1.1` | `+3861.48%`、DD `-19.44%`、win `90.91%`、33 笔 | [剪枝审计](diagnostics/hype-ema-x-v17-1-parameter-prune-audit-2026-07-01.md) | sizing 增强 |
| `V18` | dry-run / forward-test required / not live-ready | V17.1 干净参数规格 | 与 V17.1 相同 | [spec](specs/hype-ema-x-v18-baseline-spec.md) · [tracking](runner-tracking/hype-ema-x-runner-2026-07-10.md) | 当前 dry-run |

## Shared Assumptions

- 数据：normalized HYPEUSDT `15m` 数据湖；V15–V18 使用冻结 365-day research slice。
- 成本：以对应 spec/diagnostic 的 Binance 成本为准；跨版本窗口不同，不得裸比。
- 执行：闭合 K 信号、下一根 open；退出与 late re-entry 按 V18 spec。
- 仓位：V17 HQ/LQ 均 1.0；V17.1/V18 仅 HQ 1.1；实盘 sizing 未获授权。
- 消融：V17 `144` 项、V17.1 `146` 项；高全样本收益不能替代 forward evidence。

## Evidence Map

- 历史归档：[V1–V14 历史研究](notes/hype-ema-x-v1-v14-historical-archive-2026-08-06.md)
- 当前规格：[hype-ema-x-v18-baseline-spec.md](specs/hype-ema-x-v18-baseline-spec.md)
- 核心诊断：[strict live audit](diagnostics/hype-ema-x-v17-1-strict-live-audit-2026-07-01.md) · [V18 rolling retest](diagnostics/hype-ema-x-v18-retest-and-rolling-windows-2026-07-01.md)
- runner：[runner-tracking/README.md](runner-tracking/README.md) · 决策：[decision-log.md](decision-log.md)
- 产物与脚本：[artifacts/README.md](artifacts/README.md) · [scripts/README.md](scripts/README.md)
