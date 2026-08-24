# HYPE 4H MA7 原生趋势搜索合同（2026-08-06）

## 身份与证据角色

- Family：`HYPE-4H-MA7-Asymmetric-Body-Trend`（`HYPE-4H-MA7-ABT`）。
- Branch：`native-4h-ma7-trend-search`。
- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 周期：UTC 原生边界 `4h`；由标准数据湖连续、闭合 `1h` K 线聚合。
- 状态：`explore / not promoted / not live-ready`；本合同不登记版本、不产生 runner handoff。
- 机制变化：不再迁移日线 V1 参数。固定 `SMA7/ATR7`，重新搜索适合 `4h` 的斜率趋势状态、reclaim / pullback / breakout 入场、迟滞退出和保护参数。
- 证据限制：全部价格历史均已被研究者查看。锁定评估段只保证不参与本次参数选择，不是 clean prospective OOS。

## 数据、指标与时序

- 数据范围以本次运行时通过质量门禁的完整数据为准；报告必须写明 UTC 起止、`1h/4h` 行数、来源、缺口、重复、关键空值、OHLC、`is_closed` 与 raw/normalized 对齐结果。
- 每根 `4h` 必须恰由四根连续闭合 `1h` 组成；边缘不完整 bucket 丢弃。
- `SMA7[t] = mean(close[t-6:t])`；`ATR7` 为 7 根 `4h` true range 的简单均值。
- 趋势斜率为 `side × (SMA7[t] - SMA7[t-lookback]) / ATR7[t]`。
- 所有收盘信号只读取已闭合 `4h`；最早在下一根 `4h` open 成交。
- hard/trailing stop 使用组成 `4h` 的真实 `1h` 顺序；开盘跳过保护价时按该小时 open 成交。
- trailing stop 只在 `4h` 收盘后更新，从下一根 `4h` 起生效。
- 单账户只允许 `-1 / 0 / +1`；非加仓，成交后约 `1x`，成交间数量固定；多空同时出现时多头优先。

## 成本

- 手续费 `0.001/fill`。
- 基准不利滑点 `4 bps/fill`；压力为 `8 bps/fill`。
- funding 使用 Binance 实际事件时间和费率，以事件小时 open 近似名义，只在实际持仓区间结算。

## 时间切分

- Development：首根完整 `4h` 至 `2026-01-01 00:00 UTC`（exclusive）。
- Validation：`2026-01-01 00:00` 至 `2026-04-01 00:00 UTC`（exclusive）。
- Selection prefit：Development + Validation，只允许该区间参与排序和唯一候选冻结。
- Locked evaluation：`2026-04-01 00:00 UTC` 至数据终点；唯一候选冻结后只打开一次，不根据结果修改参数、改单边或改评分。
- 若任一边界不存在，或 locked evaluation 短于 90 天，运行 fail closed。

## 搜索空间

多空独立、固定随机种子 `20260806`，每边抽取 `8,000` 个去重且规范化的配置。与入场模式无关的字段固定为默认值，避免用行为等价配置占用预算。

| 参数 | 离散集合 |
| --- | --- |
| `entry_mode` | `regime, reclaim, pullback_reclaim, breakout` |
| `slope_lookback` | `1, 2, 3, 5, 7, 10, 14 bars` |
| `slope_min_atr` | `0, 0.01, 0.02, 0.05, 0.10, 0.20` |
| `confirm_bars` | `1, 2, 3, 5` |
| `entry_buffer_atr` | `0, 0.10, 0.25, 0.50, 0.75` |
| `pullback_lookback` | `2, 3, 5, 7, 10, 14 bars`（仅 pullback） |
| `pullback_touch_atr` | `-0.50, -0.25, 0, 0.10, 0.25, 0.50`（reclaim / pullback） |
| `breakout_lookback` | `2, 3, 5, 7, 10, 14 bars`（仅 breakout） |
| `exit_confirm_bars` | `1, 2, 3, 5` |
| `exit_buffer_atr` | `0, 0.10, 0.25, 0.50, 0.75, 1.0, 1.5` |
| `slope_exit_lookback` | `0, 1, 2, 3, 5, 7 bars` |
| `hard_stop_atr` | `1.5, 2.0, 3.0, 4.0, 5.0` |
| `trail_atr` | `0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0` |
| `max_hold_bars` | `0, 12, 24, 42, 60, 90, 180` |
| `cooldown_bars` | `0, 1, 2, 3, 6, 12` |

## 选择流程

1. Stage 1：多空分别只在 Development 排序；至少 `8` 笔、未破产、MDD 不差于 `-45%`。
2. 稳定性：各取前 `160` 个，审计 Development 前/后半段、完整 Development、Validation、Selection prefit 的 `8 bps` 与额外一根 `4h` 延迟。
3. 单腿准入：Development 至少 `8` 笔、Validation 至少 `3` 笔、Selection prefit 至少 `12` 笔；Development 与 Validation 均正收益；`8 bps` 和延迟后的 Selection prefit 均正收益；所有选择窗口 MDD 不差于 `-40%`。
4. 组合：各边稳定性前 `24` 个两两配对；同样只读取 Development / Validation / prefit stress / delay，并要求 prefit 至少 `15` 笔。
5. 路由比较：在 combined、long-only、short-only 中，以各选择窗口 log-equity 的最差值优先、再用中位值和 prefit 收益排序，冻结唯一候选。若没有 hard-pass，冻结最高分失败观察值，但不得称为合适策略。
6. Locked evaluation 打开后停止搜索；不因 locked、phase、近期或全期结果进行二次选择。

## 冻结后审计

- Development、Validation、Locked evaluation、Selection prefit、全期；
- combined / long-only / short-only；
- `8 bps/fill` 与额外延迟一根 `4h`；
- 最近 `1d/7d/1m/3m/6m/1y`，只作 audit；
- 从真实 `1h` 重聚合 `0h/1h/2h/3h` 四个可用相位；因缺少 `30m` 数据，仓库默认半小时相位门禁仍记为未完成；
- 90 日窗口、30 日步长的稳定性；
- 冻结参数的一次一项邻域扰动、交易 bootstrap；
- 同成本和 funding 的 `1x` buy-and-hold 基准；
- 首持仓 bar 保护、跳空 stop、延迟成交、无数据/不完整 bar 的 fail-closed 状态机检查。

## 判定

- “找到合适候选”至少要求选择阶段 hard-pass，Locked evaluation 基准与 `8 bps` 均正、额外延迟不出现灾难性失效、全期不破产且 MDD 不差于 `-40%`。
- 相位、超额收益、邻域或样本量失败时，即使绝对收益为正，也只能保留 `explore / not promoted / not live-ready` 观察值。
- 无论结果如何，本轮均不登记版本、不推进 runner；后续登记或 promotion 必须由用户另行明确要求。

## 实现审计与纠错边界

- 首次实现审计发现代码把第 5 步的最终 route 比较误写成加权总分。纠错只恢复本合同原文规定的 `hard-pass → 最差 log-equity → 中位 log-equity → prefit log-equity` 最终排序；第 4 步各边稳定性前 `24` 仍沿用 locked 打开前已实现的 composite robust score，避免借纠错更换 pair pool。参数空间、样本、时间切分和 hard-pass 门槛均不变，且纠错不读取 locked 数值参与选择。
- “额外延迟不出现灾难性失效”和参数邻域未在搜索前定义数值阈值，因此只报告原始结果，不允许它们单独授予“合适候选”结论。
- 超额收益按同窗口策略收益减 buy-and-hold；整点相位按仓库默认正中位、非原生/原生比例与 CV 门槛判断。缺少 `30m` 数据仍是未完成项。
