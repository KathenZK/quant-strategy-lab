# HYPE-5M-Micro-Scalp 主账

## 家族身份

- Full family name：`HYPE-5M-Micro-Scalp`
- Historical alias：`HYPE-5M-MS`
- 市场：Binance USD-M Futures `HYPEUSDT` perpetual
- 周期：`5m`
- 机制：高频高胜率小单笔利润 scalp 搜索；closed-bar signal、next-open entry、入场即固定 TP/SL bracket、同 K 冲突 stop-first。

本主账于 2026-07-07 补建（此前版本登记散落在 README 与 decision-log 中，违反 core-ledger 覆盖规则）。历史批次明细见 `decision-log.md`。

## 当前状态

`V1/V1.1/V1.2/V1.3 registered audit observations / NO-GO for original 3-5 trades/day shape / not promoted / not live-ready`。

原始目标形态（`3-5` 笔/天高胜率 micro-profit）在可用样本、executable order model 和观测 Binance 成本下不可行；放宽频率至约 `0.3-0.5` 笔/天后才出现正期望候选。所有版本最多推进到逐笔 audit，不得标记 candidate、dry-run、handoff 或 live。

## 版本表

成本口径：fee `0.001`/fill、adverse slippage `4 bps`/fill（V1 早期批次使用观测 Binance live cost，见对应报告）。

| Version | Identity | Status | 关键指标（1x） | Evidence | Live-readiness |
| --- | --- | --- | --- | --- | --- |
| `HYPE-5M-Micro-Scalp-V1` | `R1_relax_frequency_R01242__tp_sl_0011`：`vwap_revert`、both sides、EMA `21/96/384`、VWAP 偏离 `75 bps`、`require_trend=true`、TP/SL `67.5/275 bps`、max hold `96`、cooldown `36` | registered audit baseline | `188` 笔、`0.48` 笔/天、年化 `1.32x`、win `85.11%`、PF `1.468`、maxDD `-8.16%` | `canonical-specs/hype-5m-micro-scalp-v1-baseline-spec.md`；`ablations/hype-5m-micro-scalp-v1-full-parameter-ablation-2026-06-29.md` | not live-ready |
| `HYPE-5M-Micro-Scalp-V1.1` | `V1S_rand_016782__N00596`：V1 有效字段精简组合搜索优先观察行 | registered audit observation | `182` 笔、`0.46` 笔/天、年化 `2.13x`、win `87.91%`、PF `2.660`、maxDD `-8.06%` | `canonical-specs/hype-5m-micro-scalp-v1-1-baseline-spec.md`；`ablations/hype-5m-micro-scalp-v1-1-full-parameter-ablation-2026-06-30.md`；`research-notes/hype-5m-micro-scalp-v1-simplified-candidate-robustness-2026-06-30.md` | not live-ready |
| `HYPE-5M-Micro-Scalp-V1.2` | `V1.1_tune_grid_004895`：V1.1 有效字段微调优先观察行；调整 EMA HTF、ADX/Chop/RVOL/ATR 过滤与 TP/SL | registered audit observation | 指定成本下 `1x/2x/3x` 年化 `1.76x/2.98x/4.89x`、maxDD `-9.96%/-19.90%/-29.67%`；默认 `1x`，`2x/3x` 仅压力测试 | `canonical-specs/hype-5m-micro-scalp-v1-2-baseline-spec.md`；`research-notes/hype-5m-micro-scalp-v1-2-registration-and-leverage-retest-2026-07-01.md` | not live-ready |
| `HYPE-5M-Micro-Scalp-V1.3` | V1.2 精简 schema 版：剔除 dormant 与等效关闭字段，仅保留 `18` 个有效参数；与 V1.2 逐笔等价 | registered clean-equivalent observation | 与 V1.2 逐笔等价（`1x` 年化 `1.76x`、maxDD `-9.96%`）；不提供新增收益证据 | `canonical-specs/hype-5m-micro-scalp-v1-3-baseline-spec.md`；`ablations/hype-5m-micro-scalp-v1-3-full-parameter-ablation-2026-07-01.md`；`research-notes/hype-5m-micro-scalp-v1-3-baseline-backtest-2026-07-01.md` | not live-ready |

## 版本规则

- 本家族版本号 local 于 `HYPE-5M-Micro-Scalp`，与 `HYPE-5M-Pullback-Trail`、`HYPE-15M-MII` 等家族的版本号无关。
- 登记新版本必须更新本表、`decision-log.md`，并同步 `research/hype/README.md` 与 `research/README.md` 的状态标签。
- V1.3 之后的动态 TP（`research-notes/hype-5m-micro-scalp-v1-3-atr-dynamic-tp-2026-07-01.md`）与动态杠杆（`research-notes/hype-5m-micro-scalp-v1-3-atr-dynamic-leverage-2026-07-01.md`）测试均未超越固定基线，未形成新版本。
- 任何版本进入 promotion 状态前必须补齐：逐笔路径图、同 K TP/SL 与 gap ordering 审计、订单维护、restart-state 审计、live-executable 审计与 `forward-tracking/` 证据（见 `research/strategy-status-glossary.md`）。
