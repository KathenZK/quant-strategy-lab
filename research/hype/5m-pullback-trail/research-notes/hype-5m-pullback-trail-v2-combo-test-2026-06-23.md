# HYPE-5M-PBTR V2 Combo Test 2026-06-23

日期：2026-06-23

Ledger id：`HYPE-5M-PBTR`

> 注意：`HYPE-5M-PBTR` 是新的 HYPE 5m 回踩-追踪止损研究线。本文中的 V1/V2 只在 `HYPE-5M-PBTR` 主账内有效，不等于原 `hype-ema-tb-core-ledger.md` 里的 15m V1/V2/V35 系列。

## 测试目的

上一份 `../ablations/hype-5m-r05732-strategy-ablation-2026-06-23.md` 显示，若只做单参数消融，几个方向可能同时改善策略：

- 放宽 `pullback_buffer`。
- 收紧 `stop_atr`。
- 提高或删除固定止盈 `tp_atr`。
- 调整 `roc_window`。
- 放松或保留 `max_chop`、`min_efficiency`、`min_dir_rsi`。
- 调整最终高周期过滤 `dir_htf` 阈值。

本轮测试不再做全市场海搜，只围绕这些已经有消融依据的参数做同步微调，验证是否能得到一个比 V1 更强、且仍满足可实盘观察门槛的 V2。

## 测试网格

固定不变：

- `entry_style=pullback_resume`
- `side_mode=both`
- `trail_atr=0.75`
- `min_hold_bars=6`
- `max_hold_bars=576`
- `cooldown_bars=0`
- `exit_ema=0`
- 手续费单边 `0.04%`
- 滑点单边 `0.01%`
- 杠杆 `1x`

同步测试参数：

| 参数 | 测试值 |
| --- | --- |
| `ema_pair` | `21/96`, `12/96` |
| `pullback_buffer` | `0.0025`, `0.005`, `0.01`, `0.015`, `99.0` |
| `tp_atr` | `1.875`, `2.5`, `3.0`, `99.0` |
| `stop_atr` | `0.5`, `0.75` |
| `max_chop` | `62`, `100` |
| `min_efficiency` | `0`, `0.025` |
| `min_dir_rsi` | `50`, `55` |
| `roc_window` | `24`, `48`, `96`, `192` |
| `dir_htf_threshold` | `0.5`, `0.688442`, `0.946715`, disabled |

总组合数：`10240`。

## 通过门槛

V2 gate：

- 全样本交易数 `>=500`。
- forward 交易数 `>=20`。
- 每切片胜率 `>=56%`。
- 每切片 payoff `>=1.8`。
- 最差切片最大回撤不劣于 `-12%`。

结果：

- 总组合：`10240`
- 通过 V2 gate：`1568`
- `dir_htf=0.5` 通过：`98`
- `dir_htf=0.688442` 通过：`986`
- `dir_htf=0.946715` 通过：`484`
- 删除 `dir_htf` 过滤通过：`0`

删除 `dir_htf` 后虽然收益可能极高，但最差切片胜率无法过 `56%`，因此不记录为 V2。

## V2 选择

本轮选择最高综合得分且通过 gate 的组合为 `HYPE-5M-PBTR-V2`：

```text
ema21_96_pb0.01_tp99_sl0.5_chop62_eff0_rsi55_roc96_htf0.5
```

完整参数：

| 参数 | V1 | V2 |
| --- | ---: | ---: |
| `side_mode` | `both` | `both` |
| `ema_fast` | `21` | `21` |
| `ema_slow` | `96` | `96` |
| `entry_style` | `pullback_resume` | `pullback_resume` |
| `pullback_buffer` | `0.0025` | `0.01` |
| `roc_window` | `48` | `96` |
| `min_regime_age` | `3` | `3` |
| `max_regime_age` | `2000` | `2000` |
| `max_dist_ema` | `0.06` | `0.06` |
| `min_dir_roc` | `-0.01` | `-0.01` |
| `min_dir_rsi` | `55` | `55` |
| `max_dir_rsi` | `72` | `72` |
| `max_chop` | `62` | `62` |
| `min_efficiency` | `0.025` | `0` |
| `stop_atr` | `0.75` | `0.5` |
| `tp_atr` | `1.875` | `99.0` |
| `trail_atr` | `0.75` | `0.75` |
| `min_hold_bars` | `6` | `6` |
| `max_hold_bars` | `576` | `576` |
| `final dir_htf` | `>=0.688442` | `>=0.5` |

V2 的解释：

- `pullback_buffer=0.01`：允许回踩/反抽距离 EMA21 更远，不再只抓极贴近 EMA21 的形态。
- `tp_atr=99`：等价于删除固定止盈，主要依赖移动止损退出。
- `stop_atr=0.5`：初始硬止损更紧，但历史上主要退出仍来自移动止损。
- `min_efficiency=0`：删除弱贡献效率过滤。
- `roc_window=96`：方向动量窗口拉长。
- `dir_htf >= 0.5`：高周期过滤仍保留，但比 V1 放宽。

## V1/V2 对比

| 版本 | 交易数 | 日均 | 周均 | 月均 | 年化 | 胜率 | payoff | profit factor | 最大回撤 | 最差切片年化 | 最差切片胜率 | 最差切片 payoff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V1 | `1340` | `3.45` | `24.13` | `104.92` | `29.07x` | `59.18%` | `2.58` | `3.74` | `-7.70%` | `9.75x` | `58.29%` | `2.19` |
| V2 | `2515` | `6.47` | `45.29` | `196.92` | `548.67x` | `57.46%` | `2.79` | `3.77` | `-6.85%` | `137.91x` | `56.23%` | `2.43` |

V2 频率约为 V1 的 `1.88x`，胜率下降约 `1.72` 个百分点，但 payoff、profit factor、最差切片年化和回撤都改善。

## V2 切片表现

| 切片 | 天数 | 交易数 | 日均 | 年化 | 胜率 | payoff | profit factor | 最大回撤 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | `388.74` | `2515` | `6.47` | `548.67x` | `57.46%` | `2.79` | `3.77` | `-6.85%` |
| 2025-05-30~2025-09-01 | `93.56` | `622` | `6.65` | `210.32x` | `56.91%` | `2.43` | `3.21` | `-5.64%` |
| 2025-09-01~2025-12-01 | `91.00` | `658` | `7.23` | `3290.48x` | `56.23%` | `3.08` | `3.95` | `-5.14%` |
| 2025-12-01~2026-03-01 | `90.00` | `391` | `4.34` | `237.61x` | `60.87%` | `2.95` | `4.59` | `-6.85%` |
| 2026-03-01~2026-06-01 | `92.00` | `607` | `6.60` | `137.91x` | `57.00%` | `2.61` | `3.47` | `-5.42%` |
| 2026-06-01~2026-06-23 | `22.18` | `237` | `10.69` | `184639.47x` | `57.81%` | `2.96` | `4.06` | `-4.39%` |

forward 年化极高来自短窗口复利放大，不能作为可外推收益预期。更应关注的是：forward 有 `237` 笔、胜率 `57.81%`、payoff `2.96`、最大回撤 `-4.39%`。

## V2 交易结构

- 多头：`1364` 笔，胜率 `56.96%`，payoff `2.69`，profit factor `3.57`。
- 空头：`1151` 笔，胜率 `58.04%`，payoff `2.90`，profit factor `4.01`。
- 退出原因：全部为 `stop`，因为 `tp_atr=99` 等价于删除固定止盈。
- 这里的 `stop` 几乎全部是移动止损，不等于亏损硬止损。
- 平均持仓 `7.22` 根 5m K，约 `36.1` 分钟。
- P50 持仓 `7` 根，P95 `9` 根，最大 `13` 根。

## V2 保守参考

如果希望保留 V1 原来的 `dir_htf >= 0.688442` 强过滤，也有一个较稳参考：

```text
ema21_96_pb0.01_tp99_sl0.5_chop100_eff0_rsi50_roc96_htf0.688442
```

表现：

- 全样本 `2370` 笔。
- 年化 `432.92x`。
- 胜率 `57.47%`。
- payoff `2.75`。
- 最大回撤 `-7.70%`。
- 最差切片胜率 `56.36%`。
- forward `260` 笔，胜率 `60.00%`。

它不是本轮主 V2，因为参数变动更多：同时放松了 `max_chop` 和 `min_dir_rsi`，不如主 V2 保持原始形态干净。但它可作为实盘 shadow 参考。

## 收益来源解释

V2 的收益来源可以解释为：

1. HYPE 的 `5m` 局部趋势延续较强。EMA21/96 给出短周期方向，EMA96/384 给出更高周期背景。
2. 入场不是追突破，而是在趋势内等待回踩/反抽后重新站回 EMA21，买入的是趋势恢复，不是随机方向。
3. `min_hold_bars=6` 避免刚开仓就被 5m 噪声扫出。消融显示删除该参数会让策略几乎死亡。
4. `trail_atr=0.75` 把趋势恢复后的浮盈快速锁住。消融显示删除或放松移动止损都会导致胜率大幅下降。
5. 删除固定止盈后，交易不再被固定目标截断，主要由移动止损跟随路径。V2 因此提高了 payoff。
6. 多空都有效，说明它不是单纯吃 2026 年 6 月上涨段；但 HYPE 的高波动和趋势性仍是前提。

风险：

- 这是技术结构型收益，不是套利收益；市场微观结构、滑点和手续费会显著影响实盘。
- 年化倍数因高频复利会被放大，不应直接作为实盘收益承诺。
- V2 胜率低于 V1，体验会更波动，但频率更高、验证更快。

## 移动止盈/移动止损实盘方式

本策略里的“移动止盈”更准确地说是 ATR trailing stop，即用移动止损锁定利润。

实盘建议不用 Binance 原生 trailing stop 直接复刻，因为交易所 trailing stop 通常按百分比 callback rate 工作，不能精确表达 `previous_peak - 0.75 * ATR14(current_bar)`。应由策略程序管理 reduce-only stop-market 订单。

多头：

```text
entry 后记录 entry_price
每根已完成 5m K 更新 peak = max(入场以来最高价)
min_hold_bars 满 6 根后开始挂/改 reduce-only stop-market
trail_stop = max(initial_stop, peak_before_current_bar - 0.75 * ATR14(latest_closed_bar))
stop 只能上移，不能下移
```

空头：

```text
entry 后记录 entry_price
每根已完成 5m K 更新 trough = min(入场以来最低价)
min_hold_bars 满 6 根后开始挂/改 reduce-only stop-market
trail_stop = min(initial_stop, trough_before_current_bar + 0.75 * ATR14(latest_closed_bar))
stop 只能下移，不能上移
```

执行细节：

- 信号在 K0 收盘确认，K1 开盘成交。
- 开仓后前 6 根 K 不执行策略止损/止盈，和回测保持一致。
- 风险上可以另设灾难保护止损，但它应作为实盘风控，不计入策略复刻逻辑。
- 第 6 根 K 收盘后，根据入场以来的 peak/trough 提交第一张 reduce-only stop-market。
- 后续每根 5m K 收盘后 cancel/replace stop 单。
- 若使用固定止盈版本，止盈也必须是 reduce-only，成交后立刻撤掉 stop；V2 删除固定止盈，因此只有追踪止损更简单。
- 程序必须持久化 `entry_price`、`entry_ts`、`entry_atr`、`bars_held`、`peak/trough`、当前 stop order id，重启后从交易所仓位和本地状态恢复。

## 当前判断

V2 可以记录为 `HYPE-5M-PBTR-V2`，但状态应为“research live-dry-run candidate”，不是正式大资金版本。

建议实盘验证：

- V1 和 V2 同时 dry-run。
- V2 用小资金或 paper 跑 `300-500` 笔。
- 验收不看年化，先看净胜率、payoff、profit factor 和滑点。
- V2 若 `300` 笔后胜率低于 `54%` 且 payoff 低于 `2.0`，暂停。
- V2 若实际滑点超过回测假设 `2x`，重新压测。

## 复现产物

- `research/hype/families/5m-pullback-trail/scripts/test_hype_5m_r05732_v2_combos.py`
- `artifacts/hype_5m_r05732_v2_combo_test.json`
- `artifacts/hype_5m_r05732_v2_combo_test_ranking.csv`
- `artifacts/hype_5m_r05732_v2_combo_test_slices.csv`
