# HYPE-EMA-TB Core Ledger

## Family Identity

- 完整家族名：`HYPE-EMA-Trend-Breakout`
- 别名：`HYPE-EMA-TB`
- 市场：Binance USD-M `HYPEUSDT` 永续，`15m`
- 机制：EMA96/384 趋势背景、ADX/volume/高周期确认、K2 open、固定 ATR bracket 与 delayed indicator exit。
- 边界：不是 EMA-X 或 5M-PBTR；V1 回踩与 V2+ 突破是本家族内部两代机制。

## Current State

- V35 是 grandfathered `live` 历史状态；V35.1–V35.3、V36–V41 为 `registered / not promoted / not live-ready`。
- legacy 外部 `hype-trend` 曾运行 V35/V35.1，并于 `2026-07-22T04:09Z` 观测为 V35.3 live mode；当前是否运行须从实际环境核对，Lab 不授权。
- V35.1 叙事记录 `111/111` parity，但规范 JSON 缺失，证据健康度 `MISSING_EVIDENCE`；V35.3 外部实现不等于研究 promotion。
- V35 线上对账：11 笔 entry 全匹配，9 笔非人工退出原因一致；两次人工平仓、账本漏记和最终 K 仍是 blockers。
- 下一门：确认外部 V35.3 切换授权，修复 fill/income 与 final-bar 校验，再完成 Gate 3、OOS/CPCV、压力、相位和 live-executable review。

## Version Rules

- V1/V2 只在核心机制变化时升级；字母/小数后缀表示同机制参数、风控或 overlay。
- V35 起以 live-realistic K2/open 状态机为基准；等价重编号不提供新增验证。
- 登记、外部实现与 promotion 三者独立；未经用户决策不得据文档改变 runner。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `V35` | live / grandfathered external runner | EMA96/384，TP5/SL7、ADX22 delayed3、tx384 | `+6474.19%`、DD `-23.49%`、101 笔 | [reconciliation](runner-tracking/hype-ema-tb-v35-post-freeze-live-parity-2026-07-22.md) | 自动路径一致；人工/账本 blockers |
| `V35.1` | registered / not promoted / not live-ready | V35 去冗余 short 1h EMA confirm | `+7708.65%`、DD `-27.26%`、111 笔 | [spec](specs/hype-trend-strategy-v35-1-spec.md) · [review](diagnostics/hype-ema-tb-v35-1-dry-run-promotion-review-2026-07-20.md) | Gate 3 尖峰阻塞 |
| `V35.2` | registered / not promoted / not live-ready | V35.1 short MFE4.4 时减 75% | `+9409.39%`、DD `-23.46%`、112 笔 | [spec](specs/hype-trend-strategy-v35-2-spec.md) | 峰值敏感，等 OOS |
| `V35.3` | registered / not promoted / not live-ready | V35.2 + long SL6.75 / short SL5.7 | `+10017.59%`、DD `-22.88%`、113 笔 | [spec](specs/hype-trend-strategy-v35-3-spec.md) | 外部实现不等于 promotion |
| `V39` | registered / not promoted / not live-ready | long volume0.35、short target0.022、去冗余确认 | `+9969.45%`、DD `-23.46%`、107 笔 | [spec](specs/hype-trend-strategy-v39-spec.md) | 未实现 runner |
| `V39.2` | registered / not promoted / not live-ready | long volume 回 0.25 + cooldown1 | `+8922.26%`、DD `-24.61%`、108 笔 | [spec](specs/hype-trend-strategy-v39-2-spec.md) | 冻结观察 |
| `V39.3` | registered / not promoted / not live-ready | V39.2 + TP4.8/SL6.75 | `+7680.24%`、DD `-22.88%`、114 笔 | [spec](specs/hype-trend-strategy-v39-3-spec.md) | 防守观察 |
| `V39.4` | registered / not promoted / not live-ready | V39.2 short MFE4.4 减 75% | `+11682.28%`、DD `-23.46%`、109 笔 | [spec](specs/hype-trend-strategy-v39-4-spec.md) | 空头样本小 |
| `V40` | registered / not promoted / not live-ready | V35 三项精简，参数等价 V39.2 | `+9729.16%`、DD `-24.61%`、109 笔 | [spec](specs/hype-trend-strategy-v40-spec.md) | 无新增验证 |
| `V41` | registered / not promoted / not live-ready | V40 short target `0.022→0.018` | `+8321.65%`、DD `-24.61%`、109 笔 | [spec](specs/hype-trend-strategy-v41-spec.md) | 撤销额外空头风险 |

## Shared Assumptions

- 数据：Binance HYPEUSDT perpetual `15m`；版本窗口不同，比较须使用各自证据。
- 成本：历史主线计 `8.5 bps` 换手与 funding。
- 执行：闭合 K，K0/K1/K2 与 bracket/indicator/timeout 顺序按版本 spec。
- 仓位：target ATR + cap；外部实例的实际 sizing/授权只以运行环境为准。
- 内核：[ema-trend-breakout v2](../../_shared-kernels/ema-trend-breakout/README.md) 已做 V39.2/V40 parity；HYPE 历史脚本尚未 SHA-pin，仍是迁移 blocker。

## Evidence Map

- 历史归档：[历史演化 V1–V34](notes/hype-ema-tb-historical-evolution-archive-2026-08-06.md)
- 规格：[specs/](specs/) · handoff：[hype-ema-tb-v35-1-runner-draft.md](live-specs/hype-ema-tb-v35-1-runner-draft.md)
- 诊断：[diagnostics/](diagnostics/) · runner：[runner-tracking/README.md](runner-tracking/README.md)
- 决策：[decision-log.md](decision-log.md) · 脚本/产物：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
