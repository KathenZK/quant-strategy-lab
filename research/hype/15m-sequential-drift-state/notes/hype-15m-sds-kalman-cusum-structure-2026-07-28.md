# HYPE-15M-SDS Kalman + CUSUM + 结构确认状态机

## 结论

按用户要求测试了 causal Kalman local-linear trend、Page CUSUM、Donchian 结构确认和非对称迟滞状态机。组合相对前三个机制明显减少换手和回撤，但仍没有形成正期望：

- 384 个冻结组合全部满足 train `>=30`、validation `>=10` 的样本要求；
- train 正收益配置：`0`；
- validation 正收益配置：`0`；
- 两段同时正收益配置：`0`。

因此结论为 `NO-GO / not registered / not promoted / not live-ready`。本轮严格只读 `2026-04-28 08:00 UTC` 之前的 prefit，没有读取已经揭示的 reused OOS。

## 机制

### Kalman 隐含趋势

对 log price 使用因果 local-linear state：

```text
level[t] = level[t-1] + slope[t-1] + process noise
slope[t] = slope[t-1] + slope process noise
price[t] = level[t] + measurement noise
```

每根闭合 K 只用当时及历史数据更新：

- `kalman_slope`：隐含每根 K 趋势速度；
- `kalman_slope_vol`：速度除以前一时点可得的 EWMA return volatility；
- `kalman_slope_z`：速度除以 Kalman 自身的 slope uncertainty；
- `innovation_z`：新价格偏离预测的标准化程度。

### CUSUM 变化触发

```text
z[t] = log_return[t] / shifted_EWMA_volatility[t]
g_pos[t] = max(0, g_pos[t-1] + z[t] - allowance)
g_neg[t] = min(0, g_neg[t-1] + z[t] + allowance)
```

CUSUM 只把 `flat` 推到 `armed`，不直接下单。

### 结构确认和迟滞

```text
flat
  -> armed：CUSUM 与 Kalman 方向同时通过
  -> active：在 timeout 内收盘突破前 N 根 Donchian 结构，且 efficiency 通过
  -> weakening：Kalman slope 转弱
  -> flat：斜率连续转弱、反向 CUSUM 或退出结构破坏
```

信号在 K0 close 确认、K1 open 执行；单净仓、1x、`4ATR96` 紧急止损、`384` 根最长持仓。

## 冻结搜索

只在 prefit 搜索：

- Kalman process ratio：`0.003 / 0.01 / 0.03`
- measurement multiplier：`1 / 4`
- CUSUM entry：`3 / 5`
- slope/vol entry：`0.05 / 0.10`
- Donchian 与 efficiency window：`32 / 64`
- efficiency min：`0.20 / 0.30`
- armed timeout：`8 / 16`
- exit confirmation：`2 / 4`

完整合同见 [prefit contract](../artifacts/hype_15m_sds_kcs_prefit_contract.json)。

## 最不差参考

没有合格候选。以下参数只用于解释失败，不是 selected strategy：

| 参数 | 值 |
| --- | ---: |
| Kalman process ratio | `0.003` |
| measurement multiplier | `4` |
| CUSUM entry | `5` |
| slope/vol entry | `0.05` |
| structure / efficiency window | `64` |
| efficiency min | `0.30` |
| armed timeout | `8` |
| exit confirmation | `2` |

| 窗口 | Return | MaxDD | Trades | Win rate |
| --- | ---: | ---: | ---: | ---: |
| Train | `-10.02%` | `-28.47%` | 47 | 34.04% |
| Validation | `-5.93%` | `-9.12%` | 10 | 20.00% |
| Prefit combined | `-15.36%` | `-28.47%` | 57 | 31.58% |

近期 prefit 分片中，6M 一度为 `+6.65% / -12.64% MaxDD / 27 trades`，但 3M validation 回到 `-5.93%`，1M 为 `-4.37%` 且 5 笔全亏，不能冻结为 prospective 候选。

## 成本诊断

| 成本 | Prefit Return | MaxDD | Trades | Win rate |
| --- | ---: | ---: | ---: | ---: |
| 零成本 | `-0.70%` | `-22.84%` | 57 | 40.35% |
| 标准成本 | `-15.36%` | `-28.47%` | 57 | 31.58% |
| 双倍成本 | `-27.87%` | `-33.69%` | 57 | 29.82% |

组合已经把基线的 695 笔降到 57 笔，但零成本仍没有正优势。标准成本不是唯一失败原因。

## 组件消融

| 变体 | Train | Validation | Prefit | Trades | 判断 |
| --- | ---: | ---: | ---: | ---: | --- |
| 完整组合 | -10.02% | -5.93% | -15.36% | 57 | 最不差但失败 |
| 去掉 CUSUM | -18.15% | -12.89% | -28.70% | 77 | CUSUM 有效减少错误启动 |
| 去掉 Kalman | -11.60% | -6.35% | -17.22% | 58 | Kalman 有小幅边际贡献 |
| 去掉结构确认 | -18.89% | -10.94% | -27.76% | 77 | 结构确认有效 |
| 去掉 efficiency | -69.39% | -45.11% | -83.20% | 333 | efficiency 是主要降噪模块 |

四个组件都不是 noop，但它们只是把严重亏损压缩为接近零毛优势，没有产生稳定 alpha。

## 方向诊断

| 方向 | Train | Validation | Prefit | Trades |
| --- | ---: | ---: | ---: | ---: |
| 双向 | -10.02% | -5.93% | -15.36% | 57 |
| 只做多 | +5.32% | -4.06% | +1.05% | 27 |
| 只做空 | -14.57% | -1.95% | -16.23% | 30 |

空头明显拖累，但关闭空头仍不能通过：只做多 validation 为负且只有 6 笔，属于样本不足和跨段不稳定，不能事后登记成长线候选。

## 状态机行为

- `long_arm=323`、`short_arm=327`
- `arm_cancel=440`
- 最终 `long_start=27`、`short_start=30`
- 主要退出为斜率转弱；另有结构退出、反向变化退出和 3 次紧急止损

说明状态机确实快速发现了大量可能变化，并通过结构和效率过滤掉约三分之二；剩下的 57 次启动仍没有足够延续性。

## 决定

- 不登记版本，不读取或回测已揭示 reused OOS，不交接 runner。
- 停止继续调 Kalman、CUSUM 或 Donchian 阈值；384 个组合的 train/validation 全负已经足够强。
- 后续若继续，必须加入 materially new 信息：1m/5m 成交路径、taker imbalance/CVD、OI、清算或跨市场 lead-lag；或者等待 `2026-07-28 08:00 UTC` 后形成新的 prospective OOS。

## 证据

- [搜索合同](../artifacts/hype_15m_sds_kcs_prefit_contract.json)
- [搜索汇总](../artifacts/hype_15m_sds_kcs_prefit_search.json)
- [完整排名](../artifacts/hype_15m_sds_kcs_prefit_ranking.csv)
- [组件消融](../artifacts/hype_15m_sds_kcs_prefit_ablation.csv)
- [逐笔交易](../artifacts/hype_15m_sds_kcs_prefit_reference_trades.csv)
- [逐 K 状态](../artifacts/hype_15m_sds_kcs_prefit_reference_states.parquet)
- [实现](../scripts/research_hype_15m_sds_kalman_cusum_structure.py)
