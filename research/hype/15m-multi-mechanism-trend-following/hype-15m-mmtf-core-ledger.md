# HYPE-15M-MMTF Core Ledger

## Family Identity

- Full family name：`HYPE-15M-Multi-Mechanism-Trend-Following`
- Alias：`HYPE-15M-MMTF`
- Market / symbol / timeframe：Binance USD-M Futures，`HYPEUSDT` perpetual，`15m`
- Mechanism boundary：多机制纯趋势发现、V1 冻结、全接线消融与 clean tune；不继承任何既有 HYPE 家族的版本或结论。

## Current State

- 当前主状态：V1-V3 `registered / not promoted / not live-ready`
- 当前版本：V3 tuned clean freeze；one-time locked OOS 与稳健性 `HARD-GATE-FAILED`，不得 promotion。
- 硬目标：净胜率 `>=80%`、年化净值倍数 `>=20x`、最大回撤严格 `<20%`、实际杠杆 `<=3x`。
- 下一决策门：本冻结线停止调参；只有 materially new 机制与新 prospective OOS 才能重开。

## Version Rules

- V1：prefit 训练/验证上冻结的原始多机制趋势基线；登记不代表 promotion。
- V2：V1 全接线消融后形成的 clean baseline；必须说明删除项与成交路径变化。
- V3：只对消融保留参数做邻域/组合微调后的最终冻结候选。
- 锁定最近三个月 OOS 只能在 V3 参数、机制和代码哈希冻结后揭示一次；揭示结果不得回流调参。

## Version Table

| Version | Status | Role | Frozen metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| V1 | `registered / not promoted / not live-ready` | 双向 Keltner 趋势突破原始基线 | prefit `1.8427x annual / 92.00% WR / 14.11% MDD / 100 trades`；validation `2.5186x / 100% / 8.35% / 26` | [规格](specs/hype-15m-mmtf-v1-original-baseline-spec.md) · [广搜](diagnostics/hype-15m-mmtf-v1-broad-search-2026-07-22.md) | 年化硬门槛失败；进入消融，不 promotion |
| V2 | `registered / not promoted / not live-ready` | V1 clean-equivalent | 与 V1 trade signature 完全一致 | [规格](specs/hype-15m-mmtf-v2-clean-equivalent-spec.md) · [消融](ablations/hype-15m-mmtf-v1-full-ablation-2026-07-22.md) | 删除 dormant 表面；不提供新增收益证据 |
| V3 | `registered / HARD-GATE-FAILED / not promoted / not live-ready` | clean active-surface tune | full `1.8215x annual / 89.26% WR / 21.88% MDD / 121`；locked OOS `0.5262x / 76.19% / 21.88% / 21` | [规格](specs/hype-15m-mmtf-v3-tuned-spec.md) · [最终审计](diagnostics/hype-15m-mmtf-v3-final-audit-2026-07-22.md) | annual、MDD、OOS、phase、delay/stress 失败；停止本冻结线 |

## Shared Assumptions

- 闭合 `15m` K 生成信号，至少下一根 open 执行；禁止 K 线内未来信息。
- Binance 成本：每次 fill fee `0.001`、基础不利滑点 `4 bps`，另计真实持仓期间 funding；压力滑点 `8 bps`。
- 单净仓、不重叠；杠杆只允许 `(0, 3]`。
- 最后三个月为锁定 OOS；candidate generation、ranking、ablation 与 tune 均不得读取该段绩效。

## Evidence Map

- 数据冻结与质量证据：[报告](diagnostics/hype-15m-mmtf-data-freeze-2026-07-22.md) · [机器清单](artifacts/hype_15m_mmtf_dataset_freeze_2026-07-22.json)。
- V1：[广搜报告](diagnostics/hype-15m-mmtf-v1-broad-search-2026-07-22.md) · [规格](specs/hype-15m-mmtf-v1-original-baseline-spec.md) · [机器冻结](artifacts/hype_15m_mmtf_v1_search_2026-07-22.json)。
- V1 消融：[报告](ablations/hype-15m-mmtf-v1-full-ablation-2026-07-22.md) · [CSV](artifacts/hype_15m_mmtf_v1_ablation_2026-07-22.csv)。
- V2/V3：[clean tune](diagnostics/hype-15m-mmtf-v2-clean-tune-2026-07-22.md) · [V3 spec](specs/hype-15m-mmtf-v3-tuned-spec.md) · [最终审计](diagnostics/hype-15m-mmtf-v3-final-audit-2026-07-22.md) · [验收矩阵](diagnostics/hype-15m-mmtf-goal-completion-matrix-2026-07-22.md)。
