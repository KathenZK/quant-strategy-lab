# Binance-1H-Cross-Sectional-LightGBM-Selector Core Ledger

## Family Identity

- Full family name：`Binance-1H-Cross-Sectional-LightGBM-Selector`
- Alias：`BIN-1H-CSLGBM`
- Market / exchange / symbol / timeframe：Binance USD-M、USDT perpetual、point-in-time 动态全市场币池、`1h`
- Mechanism summary：横截面因子预测未来 `4h/12h/24h` 扣成本相对收益，并比较 long-only、long-short 与全局单仓 selector。
- Boundary / collision warnings：不是固定六币 `BIN-15M-AS6S`、`BIN-1H-ML6AS` 或 `BIN-1H-AR-MAE`；也不是单币 `HYPE-15M-FML`。

## Current State

- Current version(s)：`BIN-1H-CSLGBM-V1`。
- Current status：`archived / formula-invalidated / HARD-GATE-FAILED`。
- Runner / dry-run / live status：无 runner 实现；未 dry-run；未 live。
- Archive boundary：原始 prefit/OOS 组合收益使用了错误的倒数空头收益公式，
  全部旧绩效作废；按正确线性 USD-M 公式重算后研究门禁失败。本地数据与
  非 Markdown 产物已删除，不再重建、复现或 promotion。
- Next decision gate：无；重开视同新研究线。

## Version Rules

- `V1`：首个冻结的模型、特征、动态币池、组合状态机和完整证据包；登记不等于 promotion。
- `Vx.y`：同一模型/组合机制下的小型特征、阈值、风险或执行修订。
- Observation / diagnostic rows：数据审计、基线和失败模型不占版本号。
- New version trigger：模型目标、主周期、币池构造、组合路由或执行状态机发生实质变化。

## Version Table

| Version | Status | Role / Core Idea | Key Frozen Metrics | Evidence | Decision / Live Readiness |
| --- | --- | --- | --- | --- | --- |
| V1 | `archived` | 165 个高覆盖因子、730d rolling、四种子 LightGBM regression 均值；UTC 00:00、24h、Top7/Bottom7、0.45x gross；研究记录因公式错误失效 | 原始 prefit/OOS 绩效全部作废；固定原模型分数和选币、按正确空头公式重算 OOS：总收益 `-37.04%`、DD `37.04%`、组合胜率 `56.67%`、Sharpe `-3.26`、PF `0.60`、`90` 周期/`1,260` 腿 | [公式纠错审计](diagnostics/binance-1h-cslgbm-v1-oos-2026-07-17.md)；原冻结 SHA `9f5743...02a1`；纠错脚本 `scripts/audit_v1_short_return_correction.py` | `HARD-GATE-FAILED`；仅保留事故复盘与纠错记录 |

## Shared Assumptions

- Data：Binance 官方 API + Binance Vision 归档；研究窗从 `2020-01-01 UTC` 起，历史上市/下架合约均纳入 point-in-time 清单。
- Cost：标准每次成交手续费 `0.001` + `4 bps` 不利滑点；另计真实 funding；压力成本为基准的 `1.5x`。
- Execution timing：K0 `1h` 收盘后计算因子和排名，最早 K1 open 成交；不得使用 K1 或未来横截面信息。
- Position sizing：研究 long-only Top N、long-short Top/Bottom N 和全局单仓；具体上限在候选冻结前确定。
- Funding / carry：按实际持仓区间和方向计入，不把缺失 funding 静默填成真实 0。

## Evidence Map

- Specs：[冻结研究契约](specs/binance-1h-cslgbm-research-contract-2026-07-17.md)、[已撤销的 V1 外部复现规格](specs/binance-1h-cslgbm-v1-reproduction-spec.md)
- Diagnostics / ablations：[历史数据清单与补齐诊断](diagnostics/binance-usdm-history-inventory-2026-07-17.md)、[V1 OOS 公式纠错审计](diagnostics/binance-1h-cslgbm-v1-oos-2026-07-17.md)。
- Live specs：无。
- Runner tracking：无。
- Scripts / artifacts：[历史归档清单脚本](scripts/inventory_binance_usdm_history.py)、[因子面板脚本](scripts/build_cross_sectional_factor_panel.py)、[walk-forward 训练](scripts/train_prefit_walk_forward.py)、[候选冻结脚本](scripts/freeze_prefit_candidate_v1.py)、[V1 artifact 撤销清单](artifacts/v1_oos_2026q2/README.md)。原始错误 artifact 只保留作事故证据，不作为有效绩效或 promotion 证据。
