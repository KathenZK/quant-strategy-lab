# HYPE-EMA-TB-V35.1 冻结参数说明

日期：2026-07-20  
状态：`registered / not promoted / not live-ready`  
角色：V35 精简等价版；计划中的 quant-runner 迁移目标

V35.1 从 V35 出发，只移除样本内冗余的空头 1h EMA 确认。它不包含 V41 的 cooldown1，也不改变多空风险预算、仓位上限或退出状态机。

## 版本身份

```text
V35.1 = V35
      - short h1 EMA confirmation
```

V35.1 的版本身份只固定研究规则。将其标为迁移目标不等于 promotion，不授权启动 quant-runner live，也不修改当前外部 V35 live runner。

## 数据与成本

| 项目 | 冻结值 |
| --- | --- |
| 市场 | Binance USD-M perpetual |
| 标的 | `HYPE/USDT:USDT` |
| 周期 | `15m` |
| 回测数据窗口 | `2025-05-30 10:30 UTC` 至 `2026-07-17 08:45 UTC` |
| 数据质量 | `39,642` 根已闭合 K；缺口、重复、关键空值、OHLC 违规均为 0 |
| Funding | Binance funding，对齐持仓区间 |
| 成本 | 每次 fill `0.00085`，开仓和平仓分别计入 |

## 冻结参数

```yaml
features:
  ema_fast: 96
  ema_slow: 384
  adx_window: 28
  volume_window: 192
  atr_window: 672
  h1_adx_window: 21
  h1_alignment: resample 15m to 1h, shift(1), forward-fill

entry:
  long:
    ema_spread_gt: 0.0
    adx_min: 28
    volume_surge_min: 0.25
    h1_adx_gt: 18
    h1_plus_di_gt_h1_minus_di: true
  short:
    ema_spread_lt: 0.0
    adx_min: 36
    volume_surge_min: 0.50
    h1_ema_confirm: removed
  conflict: skip when long and short are both true

sizing:
  long_target_atr_pct: 0.020
  short_target_atr_pct: 0.018
  max_allocation: 3.0
  allocation: min(3.0, target_atr_pct / entry_atr_pct)

exits:
  take_profit_atr: 5.0
  hard_stop_atr: 7.0
  intrabar_conflict: stop_first
  adx_exit: 22
  delayed_bars: 3
  disable_indicator_exit_after_mfe_atr: 1.5
  max_hold_bars: 384
  trailing_stop: none
  profit_floor: none
  partial_take_profit: none

execution:
  signal_bar: K0 close
  entry_bar: K2 open
  entry_atr_source: completed K1 ATR672
  same_bar_reentry: false
  cooldown_bars: 0
```

信号在 K0 收盘确认，完整跳过 K1，K2 open 入场。TP/SL 使用入场时冻结的 K1 `ATR672`；指标退出在收盘确认，下一根 open 成交。平仓 bar 不同 bar 内重入，但下一根 K 可以按仍成立的信号重新开仓。

## 冻结回测

| 窗口 | 收益 | MaxDD | 平仓数 |
| --- | ---: | ---: | ---: |
| `1d` | `+8.94%` | `-4.64%` | `1` |
| `7d` | `-7.71%` | `-22.94%` | `3` |
| `1m` | `-1.53%` | `-23.96%` | `7` |
| `3m` | `+138.64%` | `-27.26%` | `35` |
| `6m` | `+1575.77%` | `-27.26%` | `68` |
| `1y` | `+7167.82%` | `-27.26%` | `104` |
| `full` | `+7708.65%` | `-27.26%` | `111` |

Full Sharpe `4.56`，胜率 `77.48%`（`86/111`）；多单 `85` 笔、空单 `26` 笔；退出为 TP `84`、SL `16`、indicator exit `11`。

## 等价性审计

- V35 与 V35.1 的逐笔签名完全一致；签名包含 entry/exit 时间、方向、价格、allocation、退出原因和 trade return。
- 两者逐根权益曲线最大绝对差为 `0`。
- 所有标准分片、方向统计和退出结构完全一致。
- 迁移实现不需要计算 1h EMA24/96；legacy Python 回测配置仍保留窗口字段仅为引擎兼容，但 V35.1 信号不读取它们。
- 结论仅限冻结窗口：空头 1h EMA 确认是**样本内冗余条件**，不应表述为跨市场、跨时期永久无效。

## 迁移边界

- quant-runner 已实现独立 `hype_ema_tb` kind，catalog 能力硬限制为 `DryRunOnly`；配置实例保持 `enabled=false`。
- Runner-side SPEC、Lab handoff draft、TOML 与 Python/Rust 逐笔 parity 已完成；`111/111` 笔在 entry/exit 时间、方向、价格、allocation、退出原因上零偏差。
- 当前空仓使平台切换不需要 adopt open position；旧 Python SQLite 应只读归档，不批量灌入 quant-runner 原生 ledger。
- V35 既有消融明确显示多数核心参数位于尖峰，触发现行 Gate 3 blocker；V35.1 仍缺 OOS/CPCV、执行压力、真实 1m 相位与 live-executable review，不能进入 `live spec` 或 dry-run。

## 证据

- 回测脚本：[research_hype_ema_tb_v35_1.py](../scripts/research_hype_ema_tb_v35_1.py)
- 汇总产物：[hype_ema_tb_v35_1_2026-07-20.json](../artifacts/hype_ema_tb_v35_1_2026-07-20.json)
- 逐笔产物：[hype_ema_tb_v35_1_2026-07-20_trades.csv](../artifacts/hype_ema_tb_v35_1_2026-07-20_trades.csv)
- 权益产物：[hype_ema_tb_v35_1_2026-07-20_equity.csv](../artifacts/hype_ema_tb_v35_1_2026-07-20_equity.csv)
- Runner handoff draft：[hype-ema-tb-v35-1-runner-draft.md](../live-specs/hype-ema-tb-v35-1-runner-draft.md)
- Python/Rust parity：[HYPE-EMA-TB-V35.1_parity_2026-07-20.json](../artifacts/HYPE-EMA-TB-V35.1_parity_2026-07-20.json)
- 父版本：[hype-trend-strategy-v35-spec.md](hype-trend-strategy-v35-spec.md)
