# BTC-1D-Qingze-Critical-Point-Trend Core Ledger

## Family Identity

- Full family name：`BTC-1D-Qingze-Critical-Point-Trend`
- Alias：`BTC-1D-QZ-CPT`
- Market / exchange / symbol / timeframe：Binance USD-M perpetual / `BTCUSDT` / UTC `1d`
- Mechanism summary：均线只负责定向，放量突破临界点后次日开盘试仓，盈利后正金字塔加码，宽 ATR 止损让利润延伸。
- Boundary / collision warnings：不是 `BTC-15M-EMA-Trend-Breakout`、Turtle 20/10 或 MA7 家族的版本；本家族专门审计用户提供的青泽式日线规则。

## Current State

- Current version(s)：无注册版本；已有 baseline 与一次参数搜索锁定验证 observation。
- Current status：`explore / diagnostic-only / not promoted / not live-ready`。
- Runner / dry-run / live status：无 runner handoff，无 dry-run/live 授权。
- Live-readiness blockers：20 日持仓量高位过滤器缺少历史数据；B 类机制仍无交易；参数搜索 rank 1 锁定 validation 为负；当前 validation 已暴露；未完成 CPCV、Monte Carlo、压力测试和 runner parity。
- Next decision gate：补足可信历史持仓量并使用新的 clean OOS 重建机制；不得继续在 `2026-01-02～2026-07-29` 上重选参数。

## Version Rules

- Registration / freeze：只有用户明确要求登记/冻结 `Vx`，并完成主账版本行和证据链接后，才产生注册版本。
- Promotion：必须另行明确目标状态并通过仓库硬门禁；登记不表示 promotion。
- `V1`：未来首个冻结版本必须明确 OI 过滤器、A/B 定义、止损和加码时序。
- `Vx.y`：不改变信号与状态机，只修正实现或证据口径。
- Observation / diagnostic rows：固定解释的单次回测可作为 observation，不自动生成版本号。
- New version trigger：均线口径、临界点定义、OI 门槛、成交时序、加码层级或退出状态机发生实质变化。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| `2026-08-07 baseline diagnostic` | `explore / diagnostic-only / not promoted / not live-ready` | SMA60 + A/B 临界点 + `20%/12%/8%` 正金字塔；无 OI | 2024-07-31–2026-07-29；净收益 `+0.88%`，MDD `-13.38%`，11 笔；B 信号 0 | [诊断](diagnostics/btc-1d-qz-cpt-baseline-2026-08-07.md) · [合同](specs/btc-1d-qz-cpt-baseline-contract-2026-08-07.md) | 证据不足且不完整还原；不登记、不 promotion |
| `2026-08-07 parameter-search observation` | `explore / diagnostic-only / not promoted / not live-ready` | 20,000 组 development 搜索，rank 1 锁定验证 | Development `+21.94%` / 6 笔；validation `-0.55%` / 4 笔 / MDD `-8.04%` | [搜索诊断](diagnostics/btc-1d-qz-cpt-parameter-search-validation-2026-08-07.md) · [搜索合同](specs/btc-1d-qz-cpt-parameter-search-contract-2026-08-07.md) | `locked holdout failed`；不登记、不事后重选 |

## Shared Assumptions

- Data：可信 Binance perpetual `1h` 聚合为完整 UTC 日 K；窗口受 funding 覆盖限制。
- Cost：每次成交手续费 `0.001`，不利滑点 `4 bps`。
- Execution timing：闭合日 K 生成信号，下一 UTC 日开盘成交；日内 stop 使用 gap-aware OHLC 模型。
- Position sizing：初始 `20%`，浮盈后增加 `12%`、`8%`；合计下单分配上限 `40%`，持仓市值随价格漂移。
- Funding / carry：使用实际 funding 日内总和；日内 stop 对 funding 事件时序仍是近似。

## Evidence Map

- Specs：[基线合同](specs/btc-1d-qz-cpt-baseline-contract-2026-08-07.md) · [参数搜索合同](specs/btc-1d-qz-cpt-parameter-search-contract-2026-08-07.md)
- Diagnostics / ablations：[基线诊断](diagnostics/btc-1d-qz-cpt-baseline-2026-08-07.md) · [参数搜索锁定验证](diagnostics/btc-1d-qz-cpt-parameter-search-validation-2026-08-07.md)
- Live specs：无。
- Runner tracking：无。
- Scripts / artifacts：[基线脚本](scripts/research_btc_1d_qingze_critical_point.py) · [搜索脚本](scripts/search_btc_1d_qingze_parameters.py) · [产物索引](artifacts/README.md) · [锁定验证交易路径图](artifacts/btc_1d_qingze_parameter_search_selected_validation_trade_path_2026-08-07.html)
