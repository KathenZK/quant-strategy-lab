# CSI300-1D-HYPE-MA7-V7.1-Transfer Core Ledger

## Family Identity

- Full family name：`CSI300-1D-HYPE-MA7-V7.1-Transfer`
- Alias：`CSI300-1D-HM7-XFER`
- Market / exchange / symbol / timeframe：沪深 300 价格指数，`SSE/SZSE` 成分市场身份，研究代码 `000300`，Asia/Shanghai regular session `1d`
- Mechanism：把 `HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1` 的固定 `SMA7/ATR7/RSI6`、reclaim、OAPP、forced short 与 PEHC 参数零调参迁移到沪深 300。
- Boundary：价格指数不可直接交易；不是 `510300` ETF、`IF` 股指期货或 total-return series；日 OHLC 适配不等同 V7.1 的 `1h` 执行路径。

## Current State

- Current version：无；本次只形成跨市场 transfer observation。
- Current status：`explore / not promoted / not live-ready`。
- Four-year result：`2022-08-17` 至 `2026-08-17` 共 `969` 个 session；零成本 `+13.53%`、日 OHLC MDD `-16.80%`、Sharpe `0.420`、56 笔。
- Baseline：同窗价格指数买持 `+13.35%`，零成本超额仅 `+0.18pp`；`10 bps/fill` 策略降至 `+1.05%`，而同成本买持 `+13.13%`，超额 `-12.08pp`。
- Stability：long-only `+3.10%`、short-only `+0.16%`；最近 `3m/6m/1y` 为 `-5.31%/-2.32%/-7.91%`。
- Decision：`TRANSFER_FAIL`；绝对收益不能证明迁移 edge，且数据与执行均不足以支持登记或 promotion。
- Runner：无 live spec、无可交易 instrument、无 runner implementation。
- Blockers：数据为 `raw_unaccepted`；无交易所日历与 closed provenance；只有日 K；指数不可交易；费用、融券/保证金、期现基差与真实下单时序未建模。
- Next gate：若继续，应另立 `510300` ETF 或 `IF` 期货家族，先冻结真实 instrument、成本、T+1/做空或期货保证金与分钟级保护合同；不得沿用本指数指标作 OOS。

## Version Rules

- 本次迁移不产生 `V1`；用户仅要求零调参查看结果。
- 更换可交易 instrument、执行周期、成本模型、MA 参数或是否允许做空均属于新研究家族或新 observation。
- 日 K 适配的止损、forced short 与 PEHC 结果不得反写 `HYPE-1D-MA7-ABT-V7.1` 身份。

## Version Table

| Observation | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| HYPE V7.1 → CSI300 4y | `explore / not promoted / not live-ready` | 固定参数零调参迁移，日 OHLC 适配盘中保护 | 零成本 `+13.53%/-16.80%`，56 笔；买持 `+13.35%`；`10 bps/fill=+1.05%`；最近 1y `-7.91%` | [诊断](diagnostics/csi300-1d-hype-ma7-v7-1-transfer-2026-08-17.md) · [机器证据](artifacts/csi300_1d_hype_ma7_v7_1_transfer_2026-08-17.json) | `TRANSFER_FAIL`；无稳定超额、不可交易且执行证据不足 |

## Shared Assumptions

- Data：东方财富 `secid=1.000300 / klt=101 / fqt=0`；研究窗外保留 120 个日历日 warmup；Yahoo `000300.SS` 只作交叉核验。
- Cost：主结果零成本；压力为每 fill `10 bps` 不利摩擦；无 funding、分红、融券、保证金或基差。
- Execution：收盘信号下一交易 session open；跳空穿 stop 按 open，否则日 high/low 触碰按 stop；日内先后不可辨识。
- Position：固定目标 `1x`、单仓、不加仓；short 只是指数路径反事实。

## Evidence Map

- [迁移合同](specs/csi300-1d-hype-ma7-v7-1-transfer-contract-2026-08-17.md)
- [四年回测诊断](diagnostics/csi300-1d-hype-ma7-v7-1-transfer-2026-08-17.md)
- [机器结果](artifacts/csi300_1d_hype_ma7_v7_1_transfer_2026-08-17.json) · [逐笔交易](artifacts/csi300_1d_hype_ma7_v7_1_trades_2026-08-17.csv) · [日路径](artifacts/csi300_1d_hype_ma7_v7_1_path_2026-08-17.csv)
- [复现脚本](scripts/research_csi300_1d_hype_ma7_v7_1_transfer.py)
- [决策记录](decision-log.md)
