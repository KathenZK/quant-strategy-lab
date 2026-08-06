# SOX-1D-MA7-Asset-Specific-Search Core Ledger

## Family Identity

- Full family name：`SOX-1D-MA7-Asset-Specific-Search`
- Alias：`SOX-1D-MA7-AS-SEARCH`
- Market / source / timeframe：Yahoo Finance `^SOX` PHLX Semiconductor price index，America/New_York session `1d`
- Mechanism：固定 `SMA7/ATR7`，先审计 BTC/ETH 共享参数，再用 development-only 搜索 SOX 专属多空状态机。
- Boundary：指数不可直接交易；不是 SOXX ETF、期货或期权，不能继承 live-readiness。

## Current State

- Current version：无；本次仅产生 development-selected observations。
- Current status：`explore / not promoted / not live-ready`。
- Shared control：全历史 combined `-2.96%`、MDD `-77.49%`；`10 bps/fill=-58.48%`，触发 SOX 专属搜索。
- SOX combined：development `+584.29%`、researcher-exposed holdout `+111.06%`、full `+200.29%`。
- MA20 substitution：只替换信号均线后，combined backward `+3.78%`、holdout `+77.33%`、full `+162.47%`，MDD 从 MA7 的 `-93.47%` 改善为 `-60.62%`；仍远逊 buy-and-hold。
- Failure evidence：combined backward pre-2010 `-79.36%`、full MDD `-93.47%`、full buy-and-hold `+9,725.06%`；long-only full `+482.33%` 但 MDD `-88.82%`，short-only full `-43.25%`。
- Stability：combined 逐年 22/33 为正，滚动三年 20/30 为正；最差滚动三年 `-82.34%`。
- Runner：无 live spec、无可交易 instrument、无 runner implementation。
- Blockers：无长期超额；跨年代与回撤失败；指数不可交易；成本/借券未指定；只有日线、无完整 phase/intraday path；无 clean prospective OOS。
- Next gate：不登记、不 promotion；如继续研究，先指定可交易代理并在新家族冻结独立数据、成本和未揭示 OOS 合同。

## Version Rules

- 本家族的搜索结果不产生 `SOX-...-V1`；登记必须由用户另行请求且先解决 blocker。
- 参数、搜索窗口或目标函数变化产生新 observation，不覆盖本次冻结结果。
- SOXX、期货、期权或其他代理属于新的 instrument family。

## Version Table

| Observation | Status | Role / Core Idea | Key Metrics | Evidence | Decision |
| --- | --- | --- | --- | --- | --- |
| BTC/ETH shared control | `explore / not promoted / not live-ready` | 共享 SMA7 多空参数零调参迁移 | full `-2.96%`，MDD `-77.49%` | [诊断](diagnostics/sox-1d-ma7-asset-specific-search-2026-08-05.md) | 失败，触发搜索 |
| SOX development combined | `explore / not promoted / not live-ready` | 2010–2020 development-only 多空配对 | holdout `+111.06%`；full `+200.29%`，MDD `-93.47%` | [合同](specs/sox-1d-ma7-asset-specific-search-contract-2026-08-05.md) · [诊断](diagnostics/sox-1d-ma7-asset-specific-search-2026-08-05.md) | 找到正收益，但不登记 |
| SOX development long-only | `explore / not promoted / not live-ready` | development-only 多头候选 | holdout `+62.12%`；full `+482.33%`，MDD `-88.82%` | [机器摘要](artifacts/sox_1d_ma7_asset_specific_search_summary_2026-08-05.json) | 正收益但稳定性失败 |
| SMA20 substitution | `explore / not promoted / not live-ready` | 保持 ATR7 与 MA7-selected 状态机，只替换为 SMA20 | holdout `+77.33%`；full `+162.47%`，MDD `-60.62%` | [MA20 诊断](diagnostics/sox-1d-ma20-substitution-2026-08-05.md) | 风险改善但无超额，不登记 |

## Shared Assumptions

- Data：Yahoo `^SOX` raw OHLC，`8,117` sessions，数据质量 blocker 为 `0`。
- Cost：主结果零成本；`10 bps/fill` 仅为示意摩擦。
- Execution：收盘信号次 session open；open gap 与日 high/low 触发 stop。
- Position：固定约 `1x`、单仓、非加仓；short 只是指数路径模拟。
- Selection：仅用 `2010-01-04` 至 `2021-01-04` exclusive；2021+ 不参与本次选择。

## Evidence Map

- [搜索合同](specs/sox-1d-ma7-asset-specific-search-contract-2026-08-05.md)
- [诊断报告](diagnostics/sox-1d-ma7-asset-specific-search-2026-08-05.md)
- [MA20 零调参替换合同](specs/sox-1d-ma20-substitution-contract-2026-08-05.md)
- [MA20 零调参替换诊断](diagnostics/sox-1d-ma20-substitution-2026-08-05.md)
- [机器摘要](artifacts/sox_1d_ma7_asset_specific_search_summary_2026-08-05.json)
- [复现脚本](scripts/search_sox_1d_ma7_asset_specific.py)
- [决策记录](decision-log.md)
