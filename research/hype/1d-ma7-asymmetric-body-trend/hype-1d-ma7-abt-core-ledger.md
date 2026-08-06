# HYPE-1D-MA7-Asymmetric-Body-Trend Core Ledger

## Family Identity

- Full family name：`HYPE-1D-MA7-Asymmetric-Body-Trend`
- Alias：`HYPE-1D-MA7-ABT`
- Market / exchange / symbol / timeframe：Binance USD-M Futures，`HYPEUSDT` perpetual，UTC `1d`
- Mechanism：固定 `SMA7` 的非对称多空状态机；覆盖原始前收/开盘/实体规则，以及多空独立 reclaim、斜率确认、迟滞退出与 ATR 保护的 materially new diagnostic branch。
- Boundary：非加仓、固定 `1x`；独立于 `HYPE-1D-PT`、`HYPE-1D-MHEF` 与无订单的 `BIN-1D-MA7DC`。

## Current State

- Current version：`HYPE-1D-MA7-Asymmetric-Body-Trend-V1`。
- Current status：`registered / not promoted / not live-ready`。
- Initial result：`2025-05-31` 至 `2026-07-30 UTC` 的 `425d` 成本后回测中，字面版净收益 `-89.41%`、MDD `-91.53%`、219 笔；方向性实体反转版净收益 `-82.59%`、MDD `-86.63%`、75 笔；对称收盘反转版净收益 `-74.79%`、MDD `-79.92%`、99 笔。
- Separated-trend observation：post-reveal 多空候选全期 `+293.20%`、MDD `-26.44%`、13 笔；`8 bps` 为 `+289.25%`，额外延迟一天为 `+140.58%`，long-only / short-only 分别 `+151.91% / +52.31%`。
- EMA7 substitution：保持 V1 其余参数不变时为 `+35.93%`、MDD `-46.15%`、26 笔，但 long-only / short-only 均亏损，`12h` 相位转为 `-19.34%`；不改变 V1 的 SMA7 身份。
- 4H transfer：独立 4H 家族的 bar-transfer / clock-equivalent combined 分别为 `-67.72% / -2.61%`，后者 `2h` 相位为 `-25.09%`；不改变日线 V1 身份。
- 3x leverage observation：每次入场目标 `3x`、数量固定时为 `+2,907.12%`、MDD `-56.40%`，但 `12h` 相位仅 `+6.98%`、MDD `-91.11%`，实际杠杆最高漂至约 `4.28x`；不改变 V1 的 `1x` 身份。
- BTC/ETH shared-parameter control：共享 MA7 参数零调参应用于 HYPE 为 `-65.15%`、MDD `-73.47%`，多空单腿和两个日界均失败；不替换 V1。
- Baseline：同期计事件级 funding 与双边成本的 `1x` buy-and-hold 为 `+50.82%`；多空候选历史超额 `+242.38` 个百分点。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。
- Blockers：盈利候选是在最后 `90d` 揭示后二次选择，只有 13 笔；`12h/0h` 收益比 `10.1%`，3x 后相位 MDD 达 `-91.11%` 且未建模精确强平；原参数直迁 BTC/ETH 后共同 `425d` 均亏损，BTC 周 K combined `-21.72%` 且多空单腿均亏损，SOX 全历史为 `-36.29%` 且无超额，MU Binance combined 为 `-12.30%`，其 weekday 观察也在 `0h/12h` 间由 `+18.31%` 翻为 `-25.76%`，MU Nasdaq 虽 `+51.51%` 但无超额且数据未接受，HYPE 4H 两种时间合同均失败；多头首个持仓日无 hard stop；无 clean prospective OOS / CPCV、完整极端执行审计、runner parity 或线上对账。
- Next gate：停止在已揭示历史上继续挑参数；V1 只接受新增日 K prospective observation，并须补足相位/起跑点与长仓首日保护审计。当前不推进 runner。

## Version Rules

- `V1` 只指第 `041` 组多空分离机制，冻结多空入场、退出/翻仓优先级、成本、仓位和风险合同；不包含初始实体规则。
- `V1.x` 只允许不改变逐笔行为的文档或 clean-equivalent 修正；参数、保护或时序变化升主版本。
- SMA 长度、空头退出方向、仓位目标或保护规则变化属于身份级变化，不得把已揭示历史上的事后赢家静默写回同一版本。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` | `registered / not promoted / not live-ready` | 第 `041` 组固定 SMA7、多空独立 reclaim 与迟滞/ATR 保护 | `425d` `+293.20%`，MDD `-26.44%`，13 笔；`12h/0h=10.1%` | [V1 规格](specs/hype-1d-ma7-abt-v1-spec.md) · [搜索报告](diagnostics/hype-1d-ma7-abt-separated-trend-search-2026-08-04.md) | post-reveal registration only；相位、样本、首日保护与 prospective gate 未通过 |
| EMA7 substitution observation | `explore / not promoted / not live-ready` | 只把 V1 的 SMA7 替换为 `EMA(span=7)` | `+35.93%`，MDD `-46.15%`，26 笔；`12h=-19.34%` | [EMA7 诊断](diagnostics/hype-1d-v1-ema7-substitution-2026-08-05.md) | 单腿均亏损且相位翻负；不登记、不替换 V1 |
| 3x leverage observation | `explore / not promoted / not live-ready` | 每次入场目标 `3x`，数量固定至退出 | `+2,907.12%`，MDD `-56.40%`；`12h` MDD `-91.11%` | [3x 诊断](diagnostics/hype-1d-v1-3x-leverage-2026-08-05.md) | 相位和强平合同未通过；不登记、不替换 1x V1 |

## Shared Assumptions

- Data：标准 Binance `HYPEUSDT` perpetual `1h` 数据湖聚合完整 UTC 日 K；raw/normalized、缺口、重复、关键空值和 OHLC 校验均通过。
- Indicator：`SMA7_t = mean(close[t-6:t])`；开盘决策只读取前一完整日的 `SMA7`。
- Cost：手续费 `0.001/fill`、不利滑点 `4 bps/fill`、实际 Binance funding timestamp/rate；多空分离分支只在实际持仓区间结算并用事件小时 open 近似名义，另审计 `8 bps/fill`。
- Execution：收盘条件最早在下一 UTC 开盘成交；空头开盘条件先观察日 open，再在下一根 `1h` open 成交；固定 `1x` 目标，成交间数量不变。
- Evidence role：现有历史已被研究者查看，只是 diagnostic evidence，不是 clean prospective OOS。

## Evidence Map

- [初始研究合同](specs/hype-1d-ma7-abt-initial-contract-2026-08-04.md)
- [初始回测与稳健性报告](diagnostics/hype-1d-ma7-abt-initial-validation-2026-08-04.md)
- [V1 规格](specs/hype-1d-ma7-abt-v1-spec.md)
- [多空分离候选观察规格](specs/hype-1d-ma7-abt-separated-trend-observation-2026-08-04.md)
- [多空分离搜索报告](diagnostics/hype-1d-ma7-abt-separated-trend-search-2026-08-04.md)
- [EMA7 零调参替换诊断](diagnostics/hype-1d-v1-ema7-substitution-2026-08-05.md)
- [3x 杠杆诊断](diagnostics/hype-1d-v1-3x-leverage-2026-08-05.md)
- [HYPE 4H 零调参迁移诊断](../4h-ma7-asymmetric-body-trend/diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md)
- [BTC/ETH 零调参迁移诊断](../../asset-portfolios/1d-ma7-separated-trend-transfer/diagnostics/binance-1d-ma7-separated-trend-transfer-2026-08-05.md)
- [BTC/ETH 共享参数应用于 HYPE 诊断](../../asset-portfolios/1d-ma7-asset-specific-search/diagnostics/binance-ma7-shared-params-on-hype-2026-08-05.md)
- [BTC 周 K 零调参迁移诊断](../../btc/1w-ma7-asymmetric-body-trend/diagnostics/btc-1w-ma7-v1-transfer-2026-08-05.md)
- [SOX 全历史零调参迁移诊断](../../sox/1d-ma7-separated-trend-transfer/diagnostics/sox-1d-ma7-v1-transfer-2026-08-05.md)
- [MU 双市场零调参迁移诊断](../../mu/1d-ma7-separated-trend-transfer/diagnostics/mu-1d-ma7-dual-market-transfer-2026-08-05.md)
- [MU Binance 剔除周末诊断](../../mu/1d-ma7-separated-trend-transfer/diagnostics/mu-1d-ma7-binance-weekday-filter-2026-08-05.md)
- [初始规则脚本](scripts/research_hype_1d_ma7_asymmetric_body_trend.py) · [多空分离搜索脚本](scripts/search_hype_1d_ma7_separated_trend.py)
- [产物说明](artifacts/README.md)
- [决策记录](decision-log.md)
