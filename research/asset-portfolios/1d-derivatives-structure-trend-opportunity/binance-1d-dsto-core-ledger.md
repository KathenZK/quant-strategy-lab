# Binance-1D-Derivatives-Structure-Trend-Opportunity Core Ledger

## Family Identity

- Full family name：`Binance-1D-Derivatives-Structure-Trend-Opportunity`
- Alias：`BIN-1D-DSTO`
- Market / timeframe：Binance USD-M perpetual；UTC daily anchor + `5m/1h` causal context
- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`
- Mechanism：每日锚点预测 long/flat/short，OOF threshold 后每资产只执行非重叠 5 日 `0.25x` probe；full 模型必须证明 derivatives structure 超越 price-only control。
- Collision warning：不是 DSML 的降门重开，也不继承 MA7、VIPR、PIC 或 HYPE ABT 的 root、模型与 promotion 证据。

## Current State

- Current version：无；原 full-field P0 因官方源质量失败，P0R 精确 OI + funding 容量通过；历史 P1 因 market aggregate 未在 fold 内排除 held asset 而失效。
- Status：`explore / diagnostic-only / not promoted / not live-ready`；P1 evidence invalidated。
- Data range：source metrics `[2021-12-01, 2025-05-31) UTC`；P0R anchors `[2021-12-08, 2025-05-25) UTC`。
- HYPE boundary：下载、特征、训练和评估均未读取 HYPE；无 transfer。
- Runner：无 live spec、无 implementation、无 dry-run/live instance。
- Next gate：冻结五资产 nested 合同因 inner 仅剩2 peers、低于`>=3`而不可执行；若再检验 OI/funding，必须另立更大 universe + fold-local aggregate + 未见时间窗合同。不得在已揭示 P1 上修后重称 OOS。

## Version Rules

- P0 数据、P1 模型、单资产或方向 observation 均不构成正式版本。
- 登记版本必须冻结 anchor、特征、label、模型、threshold、非重叠排程、成本与证据。
- 改变 horizon、加入 basis/liquidation/order book、允许 asset id、按资产/方向设参数或解锁 HYPE 均是 materially new contract。

## Version Table

| Observation | Status | Role / Core Idea | Evidence | Decision |
| --- | --- | --- | --- | --- |
| Full-field P0 | `HARD-GATE-FAILED` | OI/positioning/taker 全字段、完整 5m/30d context | [源质量诊断](diagnostics/binance-1d-dsto-p0-source-quality-2026-08-10.md) | 6,385 日包身份通过，但内容缺口/null 使原 P0 失败 |
| P0R exact OI + funding | `diagnostic-only / P0 PASS` | 精确端点 fail-closed、至少 3 peers | [修订合同](specs/binance-1d-dsto-p0r-oi-funding-contract-2026-08-10.md) | 6,118 anchors，P0R 通过后进入 P1 |
| P1 OI + funding | `invalidated evidence / diagnostic-only` | 30-feature full 对 8-feature price control 的历史输出 | [复核更正](diagnostics/binance-1d-dsto-p1-oi-funding-development-2026-08-10.md) | aggregate isolation 违反合同；不得解释增量，不解锁 HYPE |

## Shared Assumptions

- Data：Binance Vision USD-M daily metrics ZIP、direct `1h` OHLCV 与官方 funding/mark；坏源不插值，P0R 仅接受精确 OI 端点。
- Timing：metrics 与闭合小时 K 均严格早于 anchor；anchor open 成交，120h 后 open 退出。
- Cost：fee `0.001/fill`；主 `4bps/fill`，另报 `8/12bps`、funding-off 与 lag `+1h`。
- Sizing：固定 `0.25x`，每资产单仓、无加仓/stop/动态 sizing。

## Evidence Map

- [P0/P1 数据与模型合同](specs/binance-1d-dsto-p0-p1-contract-2026-08-10.md)
- [P0R OI + Funding 修订合同](specs/binance-1d-dsto-p0r-oi-funding-contract-2026-08-10.md)
- [P0 官方源质量诊断](diagnostics/binance-1d-dsto-p0-source-quality-2026-08-10.md)
- [P1 OI + Funding 复核更正](diagnostics/binance-1d-dsto-p1-oi-funding-development-2026-08-10.md)
- [DSML 官方历史容量失败诊断](../1d-ma7-derivatives-structure-meta-label/diagnostics/binance-1d-ma7-dsml-p0-capacity-2026-08-10.md)
- [决策记录](decision-log.md)
- [产物索引](artifacts/README.md)
