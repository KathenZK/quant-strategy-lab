# Binance-1H-Cross-Sectional-LightGBM-Selector Core Ledger

## Family Identity

- Full family name：`Binance-1H-Cross-Sectional-LightGBM-Selector`
- Alias：`BIN-1H-CSLGBM`
- Market / exchange / symbol / timeframe：Binance USD-M、USDT perpetual、point-in-time 动态全市场币池、`1h`
- Mechanism summary：横截面因子预测未来 `4h/12h/24h` 扣成本相对收益，并比较 long-only、long-short 与全局单仓 selector。
- Boundary / collision warnings：不是固定六币 `BIN-15M-AS6S`、`BIN-1H-ML6AS` 或 `BIN-1H-AR-MAE`；也不是单币 `HYPE-15M-FML`。

## Current State

- Current version(s)：无；`V1` 保留给首个冻结且通过研究门槛的候选。
- Current status：`explore / not promoted / not live-ready`
- Runner / dry-run / live status：无 runner 实现；未 dry-run；未 live。
- Live-readiness blockers：全市场历史数据尚未补齐；动态币池、因子、模型、walk-forward、锁定 OOS、压力测试和 live-executable 审计均未完成。
- Next decision gate：先完成 Binance Vision / API 数据清单、补洞和 raw/normalized 质量审计；数据有 blocker 时不得训练。

## Version Rules

- `V1`：首个冻结的模型、特征、动态币池、组合状态机和完整证据包；登记不等于 promotion。
- `Vx.y`：同一模型/组合机制下的小型特征、阈值、风险或执行修订。
- Observation / diagnostic rows：数据审计、基线和失败模型不占版本号。
- New version trigger：模型目标、主周期、币池构造、组合路由或执行状态机发生实质变化。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| - | `explore / not promoted / not live-ready` | 数据与研究契约初始化；尚无候选 | 未回测 | [研究契约](specs/binance-1h-cslgbm-research-contract-2026-07-17.md) | 数据质量和锁定 OOS 前置门禁未完成 |

## Shared Assumptions

- Data：Binance 官方 API + Binance Vision 归档；研究窗从 `2020-01-01 UTC` 起，历史上市/下架合约均纳入 point-in-time 清单。
- Cost：标准每次成交手续费 `0.001` + `4 bps` 不利滑点；另计真实 funding；压力成本为基准的 `1.5x`。
- Execution timing：K0 `1h` 收盘后计算因子和排名，最早 K1 open 成交；不得使用 K1 或未来横截面信息。
- Position sizing：研究 long-only Top N、long-short Top/Bottom N 和全局单仓；具体上限在候选冻结前确定。
- Funding / carry：按实际持仓区间和方向计入，不把缺失 funding 静默填成真实 0。

## Evidence Map

- Specs：[冻结研究契约](specs/binance-1h-cslgbm-research-contract-2026-07-17.md)
- Diagnostics / ablations：[历史数据清单与补齐诊断](diagnostics/binance-usdm-history-inventory-2026-07-17.md)。
- Live specs：无。
- Runner tracking：无。
- Scripts / artifacts：[历史归档清单脚本](scripts/inventory_binance_usdm_history.py)；产物待生成。
