# HYPE 4H MA7 原生趋势参数搜索（2026-08-06）

## 结论

本轮找到一个有历史研究价值的固定 MA7 多空观察值，但仍不能称为“合适策略”。

唯一候选只按 Development / Validation / selection-prefit 冻结；未参与选择的 `120d` locked evaluation 成本后为 `+10.23%`，`8 bps/fill` 为 `+7.55%`，说明它不像日线参数直迁那样直接失败。但同期计成本和 funding 的 `1x` buy-and-hold 为 `+45.60%`，候选少赚 `35.37` 个百分点；额外延迟一根 `4h` 后也转为 `-4.28%`。

四个可用整点相位虽然全部盈利，但原生 `0h` 为 `+324.74%`，非原生相位只有 `+65.70% / +20.66% / +94.66%`；非原生收益中位仅为原生的 `20.2%`，低于默认 `40%`，收益 CV `1.07` 也高于 `0.75`。因此候选保持 `explore / not promoted / not live-ready`，不登记版本。

## 冻结合同与实现纠错

- Family：`HYPE-4H-MA7-Asymmetric-Body-Trend`。
- Branch：`native-4h-ma7-trend-search`；不继承日线 V1 参数或 4H direct-transfer 指标。
- Development：`2025-05-30 12:00` 至 `2026-01-01 00:00 UTC`。
- Validation：`2026-01-01 00:00` 至 `2026-04-01 00:00 UTC`。
- Locked evaluation：`2026-04-01 00:00` 至 `2026-07-30 04:00 UTC`；不参与参数选择。
- 每边随机抽取 `8,000` 个去重配置，前 `160` 个做稳定性审计，稳定性前 `24 × 24 = 576` 个多空组合配对；随机种子 `20260806`。
- 首次实现误把最终 route 的合同词典序写成加权总分。独立审计后只恢复 `hard-pass → 最差 log-equity → 中位 log-equity → prefit log-equity`；pair pool、参数空间、切分和门槛均不变，未读取 locked 数值参与纠错后的选择。
- 全部历史已被研究者查看，因此 locked 只表示本轮 selection-isolated，不是 clean prospective OOS。
- 完整规则见[搜索合同](../specs/hype-4h-ma7-native-trend-search-contract-2026-08-06.md)。

## 数据与执行

- Binance USD-M `HYPEUSDT` perpetual。
- 标准数据湖 `1h`：`2025-05-30 10:00` 至 `2026-07-30 04:00 UTC`，`10,219` 根；缺口、重复、关键空值、非法 OHLC、非闭合 K 与 raw/normalized 对齐 blocker 均为 `0`。
- UTC 原生相位形成 `2,554` 根完整 `4h`；每根严格由四根连续闭合 `1h` 聚合。
- 收盘信号最早下一根 `4h` open 成交；hard/trailing stop 使用真实 `1h` 顺序，开盘跳过 stop 时按小时 open 成交。
- 手续费 `0.001/fill`、基准不利滑点 `4 bps/fill`、压力 `8 bps/fill`、真实事件时间 funding。
- 单仓约 `1x`、非加仓、成交间数量固定；多空均有入场即生效的 hard stop。

## 冻结参数

| 参数 | Long | Short |
| --- | --- | --- |
| 入场 | `pullback_reclaim` | `pullback_reclaim` |
| MA7 斜率 | `5 bars >= 0.02 ATR7` | `10 bars >= 0 ATR7` |
| 确认 / 入场带 | `2 / 0.25 ATR7` | `3 / 0.25 ATR7` |
| pullback lookback / touch | `2 / +0.50 ATR7` | `5 / -0.50 ATR7` |
| 退出确认 / 迟滞 | `3 / 0.25 ATR7` | `3 / 0.25 ATR7` |
| 斜率退出 | `5 bars` | `3 bars` |
| hard / trailing stop | `1.5 / 关闭` | `3 / 4 ATR7` |
| max hold / cooldown | `12 / 1 bars` | `12 / 2 bars` |

搜索阶段共有 long-only `94` 个、short-only `14` 个、combined `436` 个 hard-pass；上表是按冻结词典序得到的唯一 combined route。

## Selection 与 locked

| 窗口/场景 | 收益 | MDD | PF | 交易数 |
| --- | ---: | ---: | ---: | ---: |
| Development | `+152.12%` | `-37.49%` | `2.07` | `51` |
| Validation | `+52.39%` | `-26.75%` | `1.89` | `25` |
| Selection prefit | `+284.22%` | `-37.49%` | `1.98` | `76` |
| Prefit `8 bps` | `+261.73%` | `-37.59%` | `1.91` | `76` |
| Prefit +1 bar delay | `+192.11%` | `-37.90%` | `1.68` | `76` |
| Locked base | `+10.23%` | `-22.69%` | `1.17` | `31` |
| Locked `8 bps` | `+7.55%` | `-23.25%` | `1.12` | `31` |
| Locked +1 bar delay | `-4.28%` | `-30.15%` | `0.94` | `31` |
| Locked buy-and-hold | `+45.60%` | — | — | — |

Locked 绝对收益和成本压力为正，是比 direct-transfer 更好的信号；但超额和延迟失败，不能把它解释为稳健通过。

## 全期与多空单腿

| Route | 全期收益 | MDD | PF | Locked 收益 |
| --- | ---: | ---: | ---: | ---: |
| Combined | `+323.53%` | `-37.49%` | `1.62` | `+10.23%` |
| Long-only | `+96.49%` | `-25.27%` | `1.38` | `-6.73%` |
| Short-only | `+112.87%` | `-37.06%` | `3.10` | `+15.72%` |
| Buy-and-hold | `+50.58%` | — | — | `+45.60%` |

Locked 的正收益主要来自仅 `7` 笔的 short leg；long leg 为负。不能据此事后删除多头或改成 short-only，因为 locked 已打开且样本太少。

## 相位、邻域与时间稳定性

| 4H 起始相位 | 收益 | MDD | 交易数 |
| --- | ---: | ---: | ---: |
| `0h` | `+324.74%` | `-37.49%` | `107` |
| `1h` | `+65.70%` | `-37.23%` | `112` |
| `2h` | `+20.66%` | `-46.08%` | `109` |
| `3h` | `+94.66%` | `-38.45%` | `102` |

- 四个整点相位都盈利，但相位收益比例和 CV 未过默认门槛；数据只有 `1h`，默认 `30m` 半周期相位仍未完成。
- 52 个一次一项邻域中 `42` 个 Locked 为正，存在一定局部高原；但 long 入场模式、entry buffer 等关键变化仍有负值。
- 12 个滚动 `90d` 窗口有 `11` 个为正；唯一负窗口为 `2026-02-24` 至 `2026-05-25` 的 `-5.30%`。
- 最近 `1d/7d/1m/3m/6m/1y` 为 `+0.34% / +2.51% / -10.68% / +19.43% / +15.49% / +226.87%`；近期切片只作 audit。
- 全期 107 笔交易 bootstrap 盈利概率 `98.96%`，5% equity multiple 为 `1.45`；其 MDD 只在逐笔边界计算，不能替代 intrabar 路径回撤，也不能推翻相位和超额失败。

## 决策

1. 保留该 combined route 为“有前景的历史观察值”，但搜索合同的合适候选判定仍为失败。
2. 不根据 locked 的 short-only、邻域或相位结果继续二次选参，不登记版本、不推进 runner。
3. 同一机制下一步只接受新增 prospective 4H 数据；若改用趋势寿命、效率或多周期机制，应另立合同，不能继承本轮 selection 指标。

## 证据

- [机器摘要](../artifacts/hype_4h_ma7_native_trend_summary_2026-08-06.json)
- [候选前沿](../artifacts/hype_4h_ma7_native_trend_frontier_2026-08-06.csv)
- [组合排名](../artifacts/hype_4h_ma7_native_trend_pairs_2026-08-06.csv)
- [窗口、成本与延迟指标](../artifacts/hype_4h_ma7_native_trend_metrics_2026-08-06.csv)
- [多空单腿](../artifacts/hype_4h_ma7_native_trend_components_2026-08-06.csv)
- [相位审计](../artifacts/hype_4h_ma7_native_trend_phase_2026-08-06.csv)
- [滚动 90 日](../artifacts/hype_4h_ma7_native_trend_rolling_90d_2026-08-06.csv)
- [近期切片](../artifacts/hype_4h_ma7_native_trend_recent_2026-08-06.csv)
- [参数邻域](../artifacts/hype_4h_ma7_native_trend_neighborhood_2026-08-06.csv)
- [逐笔交易](../artifacts/hype_4h_ma7_native_trend_trades_2026-08-06.csv)
- [权益路径](../artifacts/hype_4h_ma7_native_trend_path_2026-08-06.csv)
- [复现脚本](../scripts/search_hype_4h_ma7_native_trend.py)
