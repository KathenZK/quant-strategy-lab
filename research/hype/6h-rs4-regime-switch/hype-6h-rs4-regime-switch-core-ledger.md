# HYPE-6H-RS4-Regime-Switch Core Ledger

本主账记录 `HYPE-6H-RS4-Regime-Switch` 家族的版本、证据与当前状态。该 family 来源于同事提供的 RS4 HTML 说明，但本仓库只把可复现、已审计的数据口径写入主账。

## Family Status

- 当前主版本：`HYPE-6H-RS4-Regime-Switch-V1`
- 当前状态：`diagnostic only / not promoted`
- 当前数据口径：Binance HYPEUSDT perpetual `5m` normalized OHLCV，聚合为 `6h`
- 当前关键限制：未复核 Bybit 2024-12 全史；funding 仅覆盖到 `2026-06-01`；未完成跨交易所横测与 live runner 状态机审计

## HYPE-6H-RS4-Regime-Switch-V1

### 身份

- Full name：`HYPE-6H-RS4-Regime-Switch-V1`
- 简称：`RS4-V1`
- 定义日期：2026-06-28
- 版本来源：2026-06-28 简化版回测，接受全参数消融后的参数精简建议
- 版本状态：diagnostic only / not promoted

### 策略规格

共同执行口径：

- 标的：Binance HYPEUSDT USDT 永续合约
- 研究周期：`6h` K 线，由标准数据湖 `5m` 闭合 K 聚合
- 信号/成交：第 `i` 根 `6h` 收盘后计算信号，第 `i+1` 根 `6h` 开盘成交
- 成本：单边手续费 `4.5bps` + 滑点 `5.0bps`
- funding：按持仓所在 `6h` 区间内 funding_rate 求和；当前本地 funding 只覆盖到 `2026-06-01`

v10 压缩动量腿：

- `range_window = 12`，即过去 `12` 根 `6h` 的 high/low 总振幅
- `range_threshold = 0.12`
- 只有 `range <= 12%` 时允许 v10 工作
- MACD histogram：`MACD(8, 21, 5)`
- 空头：histogram < 0 即目标做空
- 多头：histogram 连续 `2` 根 > 0 才目标做多
- MFEu：浮盈曾达到 `2.0 * entry_atr` 后，若之后出现空仓信号，只要回吐 < `1.5 * entry_atr` 且仍有浮盈，则延迟空仓退出
- 反向信号永不延迟
- V1 简化：移除 `first_flat_exemption` 与 `breakeven_guard`

melt-leg 扩张突破腿：

- 只有 `range > 12%` 且 `ER20 >= 0.35` 时允许工作
- 仅多头
- 入场：收盘价突破前 `20` 根最高价
- 出场：收盘价跌破前 `10` 根最低价，或任一 gate 失效
- Donchian `20/10` 是固定机制常量，不再作为搜索参数

组合：

- `RS4-V1 = v10 + 1.0 * melt-leg`
- `w = 1.0` 是当前诊断口径；后续如用 `w=0.5`，应记录为风险档位，不作为新 alpha 参数

### 精简记录

V1 相对原始复现口径的参数精简：

- 移除 `first_flat_exemption`
- 移除 `breakeven_guard`
- `donchian_entry`、`donchian_exit`、`atr_window` 固定为机制常量，不进入后续搜索空间

精简理由：

- `first_flat_exemption` 关闭后，全样本收益与回撤几乎不变
- `breakeven_guard` 关闭后，与关闭 `first_flat_exemption` 的结果完全一致
- Donchian entry 多个长度在当前样本逐笔等价；保留 Donchian 机制，但不继续调 entry length
- ATR window 邻域不敏感；固定 `28`

### 复现证据

- 独立复现报告：`diagnostics/hype-6h-rs4-regime-switch-backtest-2026-06-26.md`
- 全参数消融报告：`diagnostics/hype-6h-rs4-parameter-ablation-stability-2026-06-28.md`
- 简化版回测报告：`diagnostics/hype-6h-rs4-simplified-backtest-2026-06-28.md`
- 简化版脚本：`scripts/research_hype_6h_rs4_simplified_backtest.py`
- 参数消融脚本：`scripts/research_hype_6h_rs4_parameter_ablation.py`

### V1 结果摘要

简化版 V1 全样本：

- 收益：`+624.48%`
- 最大回撤：`-29.77%`
- Sharpe：`3.14`
- 交易数：`128`
- 正月份：`11/14`
- 最差月：`-12.61%`
- 正 21 天窗口：`15/19`
- 最差 21 天窗口：`-7.86%`

固定时间片：

| 时间片 | 收益 | 最大回撤 | 备注 |
| --- | ---: | ---: | --- |
| `2025-05-30` → `2025-09-01` | `+24.47%` | `-28.60%` | 早期段回撤接近全样本主要风险 |
| `2025-09-01` → `2025-12-01` | `+91.63%` | `-8.58%` | 最平滑阶段 |
| `2025-12-01` → `2026-03-01` | `+33.42%` | `-18.80%` | 简化版较原基线略弱 |
| `2026-03-01` → `2026-06-01` | `+63.03%` | `-17.96%` | 包含 2026-05 melt-up |
| `2026-06-01` → latest | `+39.64%` | `-8.03%` | funding 缺口段，需补齐后复核 |
| `2026-05` | `+18.49%` | `-13.24%` | melt-leg 补 v10 踏空的核心证据段 |

### 当前判定

`HYPE-6H-RS4-Regime-Switch-V1` 可以作为后续诊断与审计的简化基线，但不能提升为 paper-live、live、dry-run 或候选策略。

主要原因：

- 当前只复核了 Binance 近期段，未复核 HTML 声称的 Bybit 全史
- melt-leg 仍高度依赖少数 regime 事件
- 参数消融显示该策略不是宽参数平台，ER gate、range gate、方向限制、long persist 等是承重墙
- funding 数据不完整，`2026-06-01` 后当前按 0 funding 处理
- 尚未完成 live runner 状态机持久化、重启恢复、净仓规则与跨交易所执行审计
