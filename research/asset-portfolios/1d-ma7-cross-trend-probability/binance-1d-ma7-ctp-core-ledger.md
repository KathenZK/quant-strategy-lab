# Binance-1D-MA7-CTP Core Ledger

## Family Identity

- Full family name：`Binance-1D-MA7-Cross-Trend-Probability`
- Alias：`BIN-1D-MA7-CTP`
- 市场/周期：Binance USD-M USDT 永续，完整 UTC 日 K。
- 机制：只在严格 SMA7 方向穿越事件上，判断下一 UTC open 起 20 日是否先到顺向 `+2 ATR` 而非逆向 `-1 ATR`。
- 碰撞警告：不是 `BIN-1D-CATL` 一般 asset-day 模型，不是 `BIN-1D-TPSA` / `BIN-1D-MA7-RC`，不修改 HYPE P0-P8/V7.1；`HYPER/USDT:USDT` 必须保留。

## Current State

- 当前实验：`P3 Independent Context Feature Block Audit`。
- 主状态：`explore / diagnostic-only / not promoted / not live-ready`
- P0 SCOUT：裸穿越后约 30% 走出趋势段，斜率/放量/30 日路径几乎不抬升。
- P1 裁决：`UNSTABLE_MA7_EVENT_SIGNAL`。开发期有弱排序，但全面过拟合；2025+ AUC 0.5202，95% CI 穿过 0.50，合并系统 2026 年 AUC 0.4753 并触发年度方向翻转门。
- P2 裁决：`SIGNAL_EXPLAINED_BY_MA7_CORE`。只用 2025 年前 MA7 穿越，单一 pooled 极简模型在 D1-D3 稳定门过线，但 F1 相对 F0 paired AUC 差 95% CI 下界为 -0.0050，不能证明穿越前路径提供独立增量。2026-09-01 已修复 Platt 方法名覆盖与同样本校准评价问题；D2-D3 前向 Brier 由 0.2200 改善到 0.2183，原始排序指标不变。
- P3 裁决：`DATA_BLOCK_NOT_READY`。合同锁定后、训练前严格样本为 52,563 行、338 资产，但 `feature_known_at < entry_ts` 为 0 行且全部等于 `entry_ts`，未满足 P3 明确时点门禁，因此停止训练，不生成 OOF 或增量裁决。
- 运行/交接：无 runner、无 dry-run、无 live spec、无 handoff。
- 隔离：P1/P2/P3 输入、事件、OOF、模型卡/报告中 `HYPE/USDT:USDT` 均为 0 行；P2/P3 2025+ 建模读取与预测均为 0。
- 下一决策门：等待 2026-06-30 后真正未揭示的新 donor 数据，或用户明确授权独立封存揭示实验；不默认继续调参。

## Version Rules

- `P0/P1/...` 是研究实验，不是可交易策略版本。
- 只有用户明确要求“登记/冻结 Vx”时才创建 registered strategy version。
- 改标签、屏障、ATR、事件定义或把非穿越日纳入训练，必须新开实验，不得覆盖 P1 裁决。

## Version Table

| 版本/观察 | 状态 | 角色/核心内容 | 关键冻结指标 | 证据 | 决策与 live-readiness |
| --- | --- | --- | --- | --- | --- |
| `P0 MA7 Cross Trend Probability SCOUT` | `explore / diagnostic-only / not promoted / not live-ready` | 四币与全市场裸穿越条件概率 | 全市场 111,918 可标签穿越，合计 30.4% | [合同](specs/binance-1d-ma7-cross-trend-probability-contract-2026-08-31.md)、[全市场](diagnostics/binance-1d-ma7-cross-trend-probability-all-market-2026-08-31.md) | 过滤器几乎不抬升；不是策略 |
| `P1 Cross-Conditioned Entry-Value Modeling` | `explore / diagnostic-only / not promoted / not live-ready` | 只训练 101,187 条合格 MA7 穿越；LONG/SHORT 双头 walk-forward | 2025+ 系统 AUC 0.5202，CI [0.4400, 0.6012]；LONG 0.5232 / SHORT 0.5314；系统 2026 AUC 0.4753；全部主折 `SEVERE_OVERFIT_WARNING` | [合同](specs/binance-1d-ma7-ctp-p1-cross-conditioned-entry-model-contract-2026-09-01.md)、[报告](diagnostics/binance-1d-ma7-ctp-p1-cross-conditioned-entry-model-2026-09-01.md)、[审计](diagnostics/binance-1d-ma7-ctp-p1-modeling-audit-2026-09-01.md) | `UNSTABLE_MA7_EVENT_SIGNAL`；not live-ready |
| `P2 Pooled-Minimal MA7 Cross Stability Audit` | `explore / diagnostic-only / not promoted / not live-ready` | 只用 F0/F1、单一 pooled 方向对齐模型，禁止 2025+ 预测 | 2022/2023/2024 验证 AUC 0.5945/0.5598/0.5715；OOF AUC 0.5673，CI [0.5394, 0.5936]；F1-F0 paired diff CI [-0.0050, 0.0453]；前向校准 Brier 0.2200→0.2183 | [合同](specs/binance-1d-ma7-ctp-p2-pooled-minimal-stability-contract-2026-09-01.md)、[报告](diagnostics/binance-1d-ma7-ctp-p2-pooled-minimal-stability-2026-09-01.md)、[审计](diagnostics/binance-1d-ma7-ctp-p2-modeling-audit-2026-09-01.md) | `SIGNAL_EXPLAINED_BY_MA7_CORE`；校准修复后排序不变；无新 OOS，not live-ready |
| `P3 Independent Context Feature Block Audit` | `explore / diagnostic-only / not promoted / not live-ready` | 计划在 P2 F1 基准上逐块检验流动性、MA30、市场环境与 funding 增量 | 合同锁后严格样本 52,563 行；`feature_known_at < entry_ts` 0 行、`== entry_ts` 52,563 行 | [合同](specs/binance-1d-ma7-ctp-p3-context-feature-block-audit-contract-2026-09-01.md)、[报告](diagnostics/binance-1d-ma7-ctp-p3-context-feature-block-audit-2026-09-01.md)、[审计](diagnostics/binance-1d-ma7-ctp-p3-modeling-audit-2026-09-01.md) | `DATA_BLOCK_NOT_READY`；训练前停止，无 OOF/模型卡，not live-ready |

## Shared Assumptions

- 物理输入只允许 CATL P0R donor panel 与其 feature/manifest；ATR 锚点、20 日 `+2/-1` first-hit 与成本模型继承 P0/P0R。
- 信号在完整 UTC 日收盘后形成，从下一 UTC open 起算；同小时双触不利优先。
- `label_entry_net_return` 只作分层诊断，不进 X，不年化、不合成账户权益。
- 2025+ 是 `model-unseen / hypothesis-revealed historical test`，不是严格盲测。
- P2 不读取 2025+ 建模行，不生成 2025+ 预测；P2 仅冻结等待新 OOS 的诊断证据。

## Evidence Map

- [家族 README](README.md)
- [决策记录](decision-log.md)
- [P1 脚本](scripts/run_binance_1d_ma7_ctp_p1_cross_conditioned_entry_model.py)
- [P2 脚本](scripts/run_binance_1d_ma7_ctp_p2_pooled_minimal_stability.py)
- [P3 脚本](scripts/run_binance_1d_ma7_ctp_p3_context_feature_block_audit.py)
- [产物索引](artifacts/README.md)
- [针对性测试](../../../tests/test_binance_1d_ma7_ctp_p1_cross_conditioned_entry_model.py)
- [P2 针对性测试](../../../tests/test_binance_1d_ma7_ctp_p2_pooled_minimal_stability.py)
- [P3 针对性测试](../../../tests/test_binance_1d_ma7_ctp_p3_context_feature_block_audit.py)

## What Not To Put Here

- 不粘贴完整参数表、十分位全表或 SHAP 清单；放到 specs / diagnostics / artifacts。
- 不把每次运行追加成新章节。
