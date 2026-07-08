# HYPE-1H-Adaptive-Regime-V4 剪枝微调基线规格

## 身份与状态

- Full version：`HYPE-1H-Adaptive-Regime-V4`。
- 来源：V3 参数剪枝审计 + prefit 三场景微调中的冻结揭示组合 `di_cross_00205__stoch_reversal_05554`。
- 状态：`diagnostic pruned tuned baseline / NO-GO / not live-ready / not promoted`。
- 登记原因：按用户要求，将 V3 剪枝后微调中 base K+1 current full 与 reused holdout 均明显优于 V3 的组合登记为 V4，作为后续研究基线。

V4 不是 live、paper-live、dry-run、candidate 或 handoff。它虽然在 base K+1 下收益、更低/相同回撤、胜率均优于 V3，但 K+2 与 8 bps 压力下最大回撤仍超过 `20%` 硬门槛。

## 数据与回测口径

- 市场：Binance USD-M Futures `HYPEUSDT` perpetual，`1h`。
- 全量闭合 K：`2025-05-30 10:00 UTC` 至 `2026-07-02 02:00 UTC`，共 `9,545` 根。
- 数据质量：missing `0`、duplicate `0`、critical null `0`、OHLCV violation `0`、raw/normalized mismatch `0`、normalized unclosed `0`。
- 历史资金费：`2,385` 条，按逐笔持仓区间计入。
- 指标 warmup 后计分起点：`2025-07-14 10:00 UTC`。
- Prefit 截止：`2026-04-13 03:39 UTC`；之后区间为已解锁的 `reused holdout`，不能称为 untouched OOS。
- 手续费：`0.001/fill`；滑点：base 为 `0.0004/fill`，压力口径为 `0.0008/fill`。
- 执行：闭合 K 信号，下一根 `1h` open 市价入场；单仓不重叠；同刻冲突 DI-cross 优先；stop-first；gap-open stop 按 open 成交。

## 剪枝说明

V4 接口来自 V3 的 clean interface 剪枝：V3 原有 `34` 个字段槽，移除 `9` 个 dormant 字段槽后剩 `25` 个可调/登记字段槽。剪枝后的默认配置与 V3 的 DI、Stoch、merged 三层逐笔交易签名 exact equal。

已移除字段：

- DI-cross：`ema_htf`、`max_adx`、`roc_window`、`min_dir_roc_bps`、`max_dist_ema_bps`、`max_aligned_funding_bps`。
- Stoch-reversal：`ema_htf`、`max_dist_ema_bps`、`sl_atr`。

这些字段不再作为 V4 参数暴露；其中 Stoch 的 `sl_atr` 固化为 `4.0` 作为安全兜底，但 3-6 ATR 变体在 V3 消融中全为 path-equal，说明实际退出由 trailing 或最长持仓先触发。

## V4 参数总表

### DI-cross 腿

| 参数 | V4 值 | 作用 | 解释 |
| --- | ---: | --- | --- |
| `min_adx` | `10.0` | 趋势强度下限 | 要求 `ADX14 >= 10` 才允许 DI-cross 入场；比 V3 的 `12` 更宽，允许较早的趋势恢复信号进入。 |
| `min_rvol` | `2.0` | 放量过滤 | 要求当前成交量相对 `48h` 均量至少 `2x`；避免在低流动性或无量交叉中开仓。 |
| `max_atr_bps` | `250.0` | 波动上限 | 要求 `ATR14 / close <= 250 bps`；过滤过度波动的 DI 趋势入场，降低止损被噪声扫掉的概率。 |
| `htf_mode` | `h12` | 高周期方向过滤 | 要求 DI 信号方向与闭合 `12h` EMA regime 一致；避免逆高周期趋势交易。 |
| `require_body_dir` | `false` | K 线实体方向过滤 | V4 关闭该过滤，不再要求信号 K 的实体方向与交易方向一致；这是本轮微调带来 holdout 改善的关键之一。 |
| `tp_atr` | `1.5` | 止盈距离 | DI 入场后挂 `1.5 * ATR14` 的固定止盈；控制趋势腿单笔利润兑现位置。 |
| `sl_atr` | `4.5` | 止损距离 | DI 入场后挂 `4.5 * ATR14` 的固定止损；比 V3 的 `4.0` 略宽，减少趋势腿被短时波动打掉。 |
| `max_hold_bars` | `18` | 最长持仓 | DI 持仓最多 `18` 根 `1h` K；若止盈/止损都未触发，到期按状态机退出。 |
| `fixed_leverage` | `3.0` | 固定名义杠杆 | DI 腿每笔使用固定 `3x` 名义权益暴露；不是动态风险仓位。 |

### Stoch-reversal 腿

| 参数 | V4 值 | 作用 | 解释 |
| --- | ---: | --- | --- |
| `indicator_window` | `21` | Stoch 计算窗口 | 使用 `21` 根 `1h` K 计算随机指标 K/D；窗口越长信号越平滑。 |
| `threshold_low` | `25.0` | 超卖阈值 | Stoch 在低于 `25` 的区域出现反向交叉时，才允许做多反转候选。 |
| `threshold_high` | `55.0` | 超买阈值 | Stoch 在高于 `55` 的区域出现反向交叉时，才允许做空反转候选；保留 V3 的阈值以减少额外改动。 |
| `min_adx` | `0.0` | 趋势强度下限 | V4 关闭 Stoch 腿 ADX 下限过滤；反转腿不再要求趋势强度达到某个水平。 |
| `min_rvol` | `1.0` | 成交量下限 | 要求当前成交量相对 `48h` 均量至少 `1x`；避免过冷清的反转信号。 |
| `min_atr_bps` | `200.0` | 波动下限 | 要求 `ATR14 / close >= 200 bps`；反转腿需要足够波动，否则 trailing 空间不足。 |
| `max_atr_bps` | `500.0` | 波动上限 | 要求 `ATR14 / close <= 500 bps`；比 V3 的 `400` 更宽，允许更多高波动反转机会。 |
| `macd_fast` | `8` | MACD 快线周期 | 用于 MACD 转向确认的快 EMA 周期。 |
| `macd_slow` | `55` | MACD 慢线周期 | 用于 MACD 转向确认的慢 EMA 周期；比 V3 的 `21` 更慢，要求更长周期动量结构参与确认。 |
| `macd_signal` | `5` | MACD signal 周期 | MACD 信号线平滑周期；与 `macd_fast/macd_slow` 共同形成 histogram 转向判断。 |
| `require_macd_turn` | `true` | MACD 转向确认 | 要求 MACD histogram 出现与交易方向一致的转向；减少纯 Stoch 交叉噪声。 |
| `trail_activation_atr` | `1.0` | trailing 激活距离 | 浮盈达到 `1.0 * ATR14` 后启动 trailing stop。 |
| `trail_atr` | `1.0` | trailing 距离 | trailing stop 与有利方向极值保持 `1.0 * ATR14` 距离，用于反转腿保护利润。 |
| `max_hold_bars` | `8` | 最长持仓 | Stoch 持仓最多 `8` 根 `1h` K；若 trailing/兜底止损未触发，到期退出。 |
| `cooldown_bars` | `36` | 冷却期 | Stoch 腿出场后等待 `36` 根 `1h` K 才允许下一次 Stoch 入场；比 V3 的 `24` 更克制，减少连续反转噪声。 |
| `fixed_leverage` | `2.0` | 固定名义杠杆 | Stoch 腿每笔使用固定 `2x` 名义权益暴露；不是动态风险仓位。 |

## 固定执行参数

以下参数不作为 V4 可调字段暴露，但属于策略语义的一部分：

| 参数 | 固定值 | 说明 |
| --- | ---: | --- |
| `entry_delay_bars` | `1` | 闭合 K 产生信号，下一根 `1h` open 入场。 |
| `side_mode` | `both` | DI 与 Stoch 都允许做多和做空。 |
| `sizing_kind` | `fixed` | 固定名义权益杠杆，不使用风险百分比动态 sizing。 |
| `merge_priority` | `DI first` | 同一时刻 DI 和 Stoch 都有信号时，DI-cross 优先。 |
| `stop_order_model` | `stop-first / gap-open` | 同一根 K 内止损和止盈同时触发时按 stop-first；gap 穿 stop 时按 open 成交。 |
| Stoch `sl_atr` | `4.0` | 不作为调参字段；只保留为硬止损安全兜底。 |

## 冻结结果

| Window / Scenario | Annual multiple | Max DD | Win rate | Trades | 备注 |
| --- | ---: | ---: | ---: | ---: | --- |
| Base K+1 Prefit | `16.3191x` | - | - | - | 三场景 prefit 稳健排名的最小年化值为 `16.3191x`。 |
| Base K+1 Reused holdout | `13.0662x` | `-19.11%` | - | - | 冻结后揭示；后段年化首次明显高于 `10x`。 |
| Base K+1 Current full | `22.8128x` | `-19.11%` | `81.08%` | `74` | 收益、回撤、胜率三项均不差于 V3。 |
| K+2 Current full | `8.7014x` | `-23.56%` | - | - | 回撤仍穿越 `20%`，压力失败。 |
| 8 bps Current full | `15.3677x` | `-22.46%` | - | - | 回撤仍穿越 `20%`，压力失败。 |

## 与 V3 对比

| Metric | V3 | V4 |
| --- | ---: | ---: |
| 参数字段槽 | `34` | `25` |
| Current full annual | `15.0530x` | `22.8128x` |
| Current full max DD | `-19.11%` | `-19.11%` |
| Current full win rate | `79.73%` | `81.08%` |
| Current full trades | `74` | `74` |
| Reused holdout annual | `9.0300x` | `13.0662x` |
| K+2 current full / DD | `3.0574x / -31.93%` | `8.7014x / -23.56%` |
| 8 bps current full / DD | `9.4070x / -28.40%` | `15.3677x / -22.46%` |

## 决策

V4 作为更干净、更强的 diagnostic baseline 登记，但不提升状态。原因：

- K+2 延迟下最大回撤 `-23.56%`，仍超过 `20%` 硬门槛。
- 8 bps/fill 滑点下最大回撤 `-22.46%`，仍超过 `20%` 硬门槛。
- 还没有生产 runner、重启恢复、交易所订单/仓位对账、missing-bar fail-closed、kill switch、真实 stop-market 滑点和新增 forward trades 证据。

## 复现

```bash
uv run python research/hype/1h-adaptive-regime/scripts/research_hype_1h_ar_v3_prune_and_tune.py
```

关键证据：

- `notes/hype-1h-ar-v3-prune-and-tune-2026-07-07.md`
- `artifacts/hype_1h_ar_v3_prune_and_tune_2026-07-07.json`
- `artifacts/hype_1h_ar_v3_prune_and_tune_combos_2026-07-07.csv`
