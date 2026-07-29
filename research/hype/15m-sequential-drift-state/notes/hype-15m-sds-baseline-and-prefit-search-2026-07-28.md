# HYPE-15M-SDS 首轮基线与 prefit 搜索 — 2026-07-28

## 结论

有“每根 K 重新评估趋势开始、持续、转弱与反转”的策略形态，但逐 K 更新的是**状态证据**，不是每根 K 都下单。首轮实现证明：如果趋势证据过于灵敏、退出迟滞不足，15m 噪音会造成严重换手和负期望。

本轮三个搜索表面均失败：

1. 冻结的顺序漂移/CUSUM 基线在 prefit、family-local reused OOS 与 full 均显著亏损；不进入消融。
2. 只使用 prefit 的滚动回归趋势状态搜索，满足最低样本量的配置中没有 train/validation 同时正收益；不形成候选。
3. 只使用 prefit 的 breakout-retest campaign 虽把“发现”和“入场”分离，仍没有满足样本量且 train/validation 同时正收益的配置。

家族保持 `explore / not promoted / not live-ready`，不登记 V1，不修改任何 live runner。

## 研究机制

### 未编号基线：顺序漂移状态

每根闭合 K：

1. 用前一时点可得的 EWMA 波动率把 log return 标准化；
2. 更新 fast/slow drift；
3. 更新正负 Page CUSUM；
4. 用 32 根 efficiency ratio 排除明显震荡；
5. 在 `flat / long / short` 三状态间切换；
6. 下一根 open 执行状态变化。

基线不是固定 TP 小利策略。持仓随状态持续，趋势证据衰减或反向 CUSUM 触发时退出；另有 `4ATR` 紧急止损、`384` 根最长持仓和止损后的 episode lock。

冻结参数与完整公式见 [机器清单](../artifacts/hype_15m_sds_dataset_freeze.json) 和 [实现](../scripts/sds_engine.py)。

### 第二表面：回归趋势显著性状态

为判断首轮是否只是单根收益 CUSUM 太敏感，第二轮改为：

- `48/96/144` 根滚动 log-price 线性回归 slope t-stat；
- 同窗口 efficiency ratio；
- 收盘价在前一滚动高低区间中的位置；
- 趋势启动连续 `2/3` 根确认；
- 趋势结束连续 `3/5` 根确认；
- `6ATR` 紧急止损，最高 `1x`。

共 `432` 个配置。搜索脚本强制 `include_locked_oos=False`，只使用 prefit，并再切出最后三个月作内部 validation。

## 数据与成本

- 数据：Binance `HYPEUSDT` perpetual `15m`，`2025-05-30 10:30 UTC` 至 `2026-07-28 07:45 UTC`。
- 数据质量：40,694 根闭合 K；缺失、重复、关键空值、OHLCV 违规和 raw/normalized mismatch 均为 0。
- 成本：每次 fill `0.001` fee + `4 bps` adverse slippage，另计实际 funding。
- 执行：K0 close 更新状态，K1 open 执行；单净仓；gap stop 用 open；禁止同 K 回看。
- OOS：`2026-04-28 08:00 UTC` 至 terminal。该窗口与其他 HYPE 研究重叠，只称 reused OOS。

## 冻结顺序漂移基线结果

| 窗口 | Return | MaxDD | Trades | Win rate | Median hold |
| --- | ---: | ---: | ---: | ---: | ---: |
| prefit | `-97.59%` | `-97.67%` | `695` | `25.18%` | `8` bars |
| locked reused OOS | `-33.72%` | `-47.47%` | `204` | `31.37%` | - |
| full | `-98.40%` | `-98.45%` | `899` | `26.70%` | `9` bars |

Full buy-and-hold 为 `+64.99%`，策略相对基准明显为负。基线在约 14 个月内发生 `441` 次 long start 和 `458` 次 short start，说明主要失败是状态切换过多、持仓太短。

零成本 prefit 仍为 `-83.09% / -84.41% MaxDD / 695 trades / 31.80% WR`。因此成本放大了失败，但根因是趋势开始/结束定义本身没有正期望，不是单纯手续费问题。

## Prefit-only 回归状态搜索

- 搜索总数：`432`
- 满足 train `>=30` 笔且 validation `>=10` 笔：`144`
- 满足样本量且 train、validation 同时正收益：`0`

最佳有效样本失败对照：

| 参数 | 值 |
| --- | --- |
| regression window | `96` |
| entry slope t-stat | `1.5` |
| efficiency min | `0.20` |
| range location | `0.65 / 0.35` |
| start / end confirmation | `3 / 3` bars |
| exit slope t-stat | `0.5` |

| 窗口 | Return | MaxDD | Trades |
| --- | ---: | ---: | ---: |
| train | `+17.44%` | `-32.25%` | `54` |
| validation | `-27.69%` | `-31.31%` | `24` |
| prefit combined | `-15.08%` | `-32.25%` | `78` |

较低频的18笔配置可以让 train/validation 表面同时为正，但违反最低样本合同，validation 只有2笔，不具备可判断性，不能当作候选。

## Prefit-only breakout-retest campaign

第三轮不再直接追随趋势证据，而使用五态过程：

```text
flat
  -> direction_detected / breakout
  -> armed
  -> retest + reclaim
  -> trend_active
  -> weakening / flat
```

搜索范围包含：

- regression window `48/96`
- breakout window `32/64/96`
- exit structure `16/32`
- slope t-stat `1.5/2.5`
- efficiency `0.20/0.30`
- retest distance `0.25/0.50 ATR`
- armed timeout `8/16` bars
- exit confirmation `2/4` bars

结果：

- 搜索总数：`384`
- 满足 train `>=30` 笔且 validation `>=10` 笔：`288`
- 满足样本量且 train、validation 同时正收益：`0`

最佳有效样本失败对照为 regression `96`、breakout `32`、exit `16`、retest `0.5ATR`、armed `16` 根、exit confirm `4` 根：

| 窗口 | Return | MaxDD | Trades |
| --- | ---: | ---: | ---: |
| train | `-0.22%` | `-31.21%` | `53` |
| validation | `-18.39%` | `-21.16%` | `20` |
| prefit combined | `-18.57%` | `-31.21%` | `73` |

回踩状态机把基线的 695 笔 prefit 交易降到 73 笔，说明它确实解决了过度换手；但净期望和跨段稳定性仍不成立。

## 对“怎样较准确识别趋势开始与结束”的回答

有效的逐 K 趋势策略至少要把四件事分开：

1. **状态估计**：每根 K 更新方向、速度、持续性和震荡程度。
2. **启动事件**：证据连续跨过较高阈值才从 flat 进入 long/short，不能把每次速度上升都当作新趋势。
3. **持续与结束迟滞**：进入后用更低的退出阈值和多根确认，避免在同一趋势中来回开平。
4. **成交状态机**：信号与执行分离；止损后锁住原 episode，必须看到趋势状态真正重置才允许再入。

首轮结果说明，仅用 drift、CUSUM、回归斜率、效率比和区间位置不够。第三轮进一步加入**启动后回踩/重测再确认**：

```text
flat
  -> direction_detected
  -> armed (等待回踩/重测，限定窗口)
  -> trend_active (恢复同向后入场)
  -> weakening
  -> flat 或 reverse
```

这仍然每根 K 评价，也确实把“看见可能开始”与“值得下单”分离并大幅降低换手；但本次 prefit 结果仍为负。因此问题已经不是状态机形式，而是仅靠 15m OHLCV 很难稳定判断某次启动会延续还是迅速失败。

## 决定

- 不登记 V1，不进入全参数消融，不向 runner 交接。
- 不使用已揭示 reused OOS 调整当前两套规则，也不重测回归搜索。
- 当前纯 OHLCV 15m 表面停止扩搜。若继续，必须加入 materially new 信息，例如真实 1m/5m 重聚合后的成交路径、taker imbalance/CVD、盘口或跨市场确认，并把 `2026-07-28 08:00 UTC` 之后数据留作 prospective OOS。

## 证据

- 数据冻结：[JSON](../artifacts/hype_15m_sds_dataset_freeze.json)
- 顺序漂移基线：[summary](../artifacts/hype_15m_sds_baseline_summary.json) · [trades](../artifacts/hype_15m_sds_baseline_trades.csv) · [equity](../artifacts/hype_15m_sds_baseline_equity.csv) · [states](../artifacts/hype_15m_sds_baseline_states.parquet)
- 成本诊断：[JSON](../artifacts/hype_15m_sds_baseline_cost_diagnostic.json)
- 回归搜索：[summary](../artifacts/hype_15m_sds_regression_prefit_search.json) · [ranking](../artifacts/hype_15m_sds_regression_prefit_ranking.csv)
- 回踩重测：[summary](../artifacts/hype_15m_sds_breakout_retest_prefit_search.json) · [ranking](../artifacts/hype_15m_sds_breakout_retest_prefit_ranking.csv)
- 实现：[sds_engine.py](../scripts/sds_engine.py) · [regression search](../scripts/research_hype_15m_sds_regression_search.py) · [breakout-retest search](../scripts/research_hype_15m_sds_breakout_retest_search.py)
