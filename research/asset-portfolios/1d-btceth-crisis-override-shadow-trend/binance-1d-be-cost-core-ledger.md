# Binance-1D-BTCETH-Crisis-Override-Shadow-Trend Core Ledger

## Family Identity

- Full family name：`Binance-1D-BTCETH-Crisis-Override-Shadow-Trend`
- Alias：`BIN-1D-BE-COST`
- Market / symbols / timeframe：Binance USD-M `BTCUSDT`、`ETHUSDT` perpetual；UTC `1d` 信号、真实 `1h` 路径执行
- Mechanism：冻结 CBCT P1 growth shadow；双资产慢周期 crisis state 触发账户级、互斥的 BTC/ETH 等权 short basket override。
- Boundary：这是独立于 MA7 family 的组合策略；不是 HYPE MA7 或 BTC/ETH MA7 的新版本。

## Current State

- Current version：`Binance-1D-BTCETH-Crisis-Override-Shadow-Trend-V1`（`BIN-1D-BE-COST-V1`）。
- Current status：`V1 registered / not promoted / not live-ready`。
- Research line：`closed / HARD-GATE-FAILED`；登记 V1 不撤销 P0 裁决，也不重开搜索。
- Frozen path：CBCT P1 growth `entry20/exit10/EMA50/trail5ATR/confirm2/cooldown7/maxhold120 + 1ATR/35%/2d`；crisis `EMA200/slope60/confirm3`。
- Development base：`23.132090x`，ordered MDD `-35.2226%`，27 笔账户交易；3 个 crisis episodes / 6 asset legs。
- Stress / delay：`22.655605x/-35.2226%`；`7.274619x/-36.9956%`，delay retention `63.17%`。
- Gate result：收益过 `20x`，但 MDD、delay 和集中度失败；`0` hard-pass。
- Evidence role：只使用已揭示 development；audit/prospective 均未读取。
- Runner：无 live spec、无 quant-runner implementation、无 dry-run/live instance。

## Version Rules

- `V1` 只代表 [V1规格](specs/binance-1d-be-cost-v1-spec.md) 的完整 BTC/ETH 账户路径，不能拆成单资产版本。
- 改动 shadow、crisis state、资产权重、gross、执行顺序或成本模型后，必须另开版本或新 family。
- 追加同参新窗口 observation 不自动改版本号；读取 audit/prospective 或 promotion 必须另获明确授权并满足治理门禁。
- 版本登记只固定研究身份；不等于通过 hard gate、promotion 或 live-ready。

## Version Table

| 版本 | 状态 | 核心参数 | Development 指标 | 证据 | 决策 |
| --- | --- | --- | --- | --- | --- |
| `BIN-1D-BE-COST-V1` | `registered / not promoted / not live-ready` | Shadow `entry20/exit10/EMA50/trail5ATR/confirm2/cooldown7/maxhold120 + 1ATR/35%/2d`；crisis `EMA200/slope60/confirm3` | base `23.132090x/-35.2226%`；stress `22.655605x/-35.2226%`；delay `7.274619x/-36.9956%` | [V1规格](specs/binance-1d-be-cost-v1-spec.md) · [P0裁决](diagnostics/binance-1d-be-cost-p0-2026-08-12.md) · [完整路径](artifacts/binance_1d_be_cost_v1_trade_path_2026-08-14.html) | 登记身份；research line 仍关闭，不 promotion |

## Shared Assumptions

- Development `[2019-12-24,2025-08-07)`；audit `[2025-08-07,2026-08-10)` sealed。
- 既有 prospective 首个 eligible closed day `>=2026-08-13`、首次执行 `>=2026-08-14 00:00 UTC`；本次没有读取或回填。
- Cost：fee `0.001/fill`，base/stress slippage `4/8bps/fill`，actual event-time funding。
- Execution：闭合日状态次日 open 执行；账户 gross target `<=1x`；shadow single position 与 dual-short basket 互斥。

## 关闭边界

- 禁止在 COST 内扩 EMA/slope/confirm、return/vol 阈值、pair stop/TP 或杠杆。
- 最大风险已转移到盈利 BTC long 的持仓内回吐；下一机制只能另立 partial-profit runner family。

## Evidence Map

- [P0冻结合同](specs/binance-1d-be-cost-p0-contract-2026-08-12.md)
- [V1规格](specs/binance-1d-be-cost-v1-spec.md)
- [P0裁决](diagnostics/binance-1d-be-cost-p0-2026-08-12.md)
- [机器摘要](artifacts/binance_1d_be_cost_p0_2026-08-12.json)
- [V1完整交易路径](artifacts/binance_1d_be_cost_v1_trade_path_2026-08-14.html) · [SHA256](artifacts/binance_1d_be_cost_v1_trade_path_2026-08-14.sha256)
- [V1路径渲染脚本](scripts/render_binance_1d_be_cost_v1_trade_path.py)
- [决策记录](decision-log.md)
