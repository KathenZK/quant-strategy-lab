# HYPE-15M-MII Core Ledger

## Family Identity

- 完整家族名：`HYPE-15M-Multi-Indicator-Intraday`
- 别名：`HYPE-15M-MII`
- 市场：Binance USD-M `HYPEUSDT` 永续，`15m`
- 机制：RSI crossing + MACD 方向 + ATR/RVOL 过滤 + 固定或 ATR bracket。
- 边界：独立于 EMA-X、EMA-TB 与 Candle-Count；裸 `V1.x` 不具备家族身份。

## Current State

- 当前版本：`HYPE-15M-MII-V1.4A`；V1.3 为 superseded dry-run history，V1.4 为 parent registered observation。
- 状态：`dry-run / not live-ready`；2026-08-04 parity JSON 缺失标为 `MISSING_EVIDENCE`，不改变既有 runner 授权。
- 共享 15m 行情组 2026-07-21→07-30 停摆区间观察作废；恢复证据见 [group halt](../15m-ema-crossover/runner-tracking/hype-ema-x-runner-2026-07-30-group-halt.md)。
- live blockers：funding、stop-market/真实滑点、重启恢复、交易所对账、missing-bar fail-closed、kill switch 与在线开平仓 reconciliation。
- 下一门：补齐规范 parity 和达标 runner-tracking；实际实例状态只以 quant-runner 为准。

## Version Rules

- `V1` 是修复时序后的首个冻结基线；`V1base` 是高收益诊断表达。
- `V1.1` 是 V1base 干净等价版；`V1.2` 改 ATR bracket；`V1.3` 只改 2.5x 暴露。
- `V1.4` 只改 `min_rvol96=0.85`；`V1.4A` 只改防守 bracket。
- 登记固定身份，不代表 promotion；信号机制改变才升主版本。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| `V1` | diagnostic baseline / not live-ready | RSI7/MACD/ATR，固定 bracket，1.5x | 年化 `18.66%`、DD `-31.84%`、Last90 年化 `-41.44%`；gate `0/62` | [spec](specs/hype-15m-mii-v1-baseline-spec.md) · [audit](diagnostics/hype-15m-mii-v1-live-feasibility-2026-06-29.md) | 不 promotion |
| `V1base` | diagnostic observation / not live-ready | 放宽 RSI，`TP1.2%/SL3.6%/2x` | K+2 DD `-36.28%` | [selection](notes/hype-15m-mii-relaxed-dd-high-return-selection-2026-06-30.md) | 主观察基线 |
| `V1.1` | clean diagnostic / not live-ready | 删除未生效参数，与 V1base 等价 | 全样本 `+309.54%`；最近 1 月 `+34.40%` | [windows](notes/hype-15m-mii-v1-1-window-backtest-2026-06-30.md) | 不 promotion |
| `V1.2` | ATR-bracket diagnostic / not live-ready | `TP1.25ATR/SL5ATR/hold24` | K+1 年化 `311.35%`/DD `-17.74%`；K+2 `154.96%`/`-34.81%` | [spec](specs/hype-15m-mii-v1-2-reproduction-spec-not-live-ready-2026-06-30.md) | 延迟脆弱 |
| `V1.3` | superseded dry-run history | V1.2 + fixed 2.5x | K+1 `+549.30%`/DD `-22.01%`；K+2 `+239.38%`/`-41.89%` | [live spec](live-specs/hype-15m-mii-v1-3-live-parameter-spec-not-live-ready-2026-07-01.md) | 2026-07-10 被替代 |
| `V1.4` | registered / not promoted / not live-ready | V1.3 + `min_rvol96=0.85` | K+1 `+978.36%`/DD `-24.70%`；K+2 `+535.54%`/`-38.30%` | [spec](specs/hype-15m-mii-v1-4-parameter-spec-not-live-ready-2026-07-08.md) | 未部署 |
| `V1.4A` | dry-run / not live-ready | V1.4 + `TP1.4ATR/SL3ATR` | recent 90d/30d `+78.82%/+27.09%`；full `+584.90%`/DD `-32.85%` | [spec](specs/hype-15m-mii-v1-4a-parameter-spec-not-live-ready-2026-07-09.md) · [tracking](runner-tracking/hype-15m-mii-runner-2026-07-10.md) | 保持 dry-run |

## Shared Assumptions

- 数据：标准 raw/normalized 数据湖，`2025-05-30T10:30Z` 至 `2026-06-26T04:00Z`；质量 gate 全通过。
- 成本：fee `0.001/fill`、slippage `4 bps/fill`，round-trip `0.28%`；funding 未计。
- 执行：闭合 K、next-open 入场，K+2 压力；单仓、stop-first、timeout-open。
- 仓位：版本冻结 fixed exposure；不得由 Lab 文档推断 runner 启停。

## Evidence Map

- 历史归档：[hype-15m-mii-historical-research-archive-2026-08-06.md](notes/hype-15m-mii-historical-research-archive-2026-08-06.md)
- 规格：[specs/](specs/) · [live-specs/README.md](live-specs/README.md)
- 消融与诊断：[ablations/](ablations/) · [diagnostics/](diagnostics/)
- runner：[runner-tracking/](runner-tracking/) · 决策：[decision-log.md](decision-log.md)
- 脚本与产物：[scripts/README.md](scripts/README.md) · [artifacts/README.md](artifacts/README.md)
