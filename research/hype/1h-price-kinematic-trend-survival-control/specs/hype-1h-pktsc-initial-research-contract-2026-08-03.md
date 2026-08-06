# HYPE-1H-PKTSC 初始研究合同（2026-08-03）

## 1. 两个必须分别回答的问题

1. **延续预测门禁**：只观察当时已闭合的价格路径，能否因果地、跨时间块预测当前方向未来 `24h/3d/7d/14d` 是否继续。
2. **动态控制门禁**：在完全相同的 campaign 入场与退出路径上，动态加减仓能否在标准成本后优于固定种子仓，并在风险不劣于固定完整仓的条件下提供独立净增益。

任一门禁失败都必须明确报告；禁止用交易收益替代预测证据，也禁止用预测 IC 替代可执行收益。

## 2. 禁止项与研究身份

- 预测特征只允许闭合 `1h close` 的对数变化；OHLC 只用于聚合质量、下一小时 open 成交和保护 stop 的路径审计。
- 禁止 EMA、MA、Donchian、ATR、ADX、RSI、成交量、资金费率、OI、订单簿、清算、人工形态和未来路径进入特征。
- Long/Short 分开报告；本轮不搜索窗口、模型、概率阈值、层级或 stop 参数。
- 相邻家族历史已经揭示，所以 `[2025-09-01, 2026-08-02)` 只能称为 historical causal walk-forward，不称 locked OOS。
- Prospective OOS 固定为 `[2026-08-02, 2026-11-02 UTC)`；输入出现该区间即 fail closed。

## 3. 数据、时序与状态

- Binance USD-M `HYPEUSDT` perpetual 标准数据湖 `15m`；每个完整小时必须有连续 `4` 根源 K。
- 小时 K 在下一整点可用；每个 UTC `00/04/08/12/16/20` 点更新状态并在同一时刻的新小时 open 执行动作。
- 方向：`sign(log close_t - log close_{t-24h})`。
- 过去窗口：`6/24/72/168/336h`。
- 每尺度冻结量：方向对齐速度、路径速度、coherence、最大单步变化占路径比、单步 RMS、相对直线路径 roughness。
- 跨尺度：`6–24/24–72/72–168/168–336h` 方向对齐加速度、尺度同向数。
- 顺序状态：24h 方向持续年龄、该 episode 的方向对齐进度、峰值进度与从峰值回吐；全部只用当时及以前价格。

## 4. 未来标签与 causal walk-forward

- horizon：`24/72/168/336h`。
- 连续标签：方向对齐最终对数收益除以过去 `336h` 单步 RMS 的扩散尺度 `Z_H`。
- 二元延续：`continuation_H = 1[direction × future log return > 0]`；MFE、MAE 和 first passage 仅作结果诊断。
- Baseline：五个方向对齐速度；Full：全部预声明价格状态。
- Ridge `alpha=10`、Logit `C=0.1`，Train-only 标准化；Long/Short 独立。
- 每个预测日只训练到 `test_day - horizon` 以前、标签已完整结束的历史；每 UTC 日重训一次，预测当天六个 4h 锚点。
- 每方向至少 `300` 个可用历史锚点才允许预测；不补值、不回填早期预测。

### 延续预测门禁

每个方向同时满足：

1. Full Ridge IC 至少 `3/4` horizon 为正，且中位 IC 不差于 Baseline。
2. Full Logit 至少 `3/4` 同时满足 AUC `>0.5`、Brier 不差于当次训练基准概率。
3. 至少 `60%` 的有资格月度块在 `24h` Full IC 为正，且至少 `6` 个有效月。
4. `24h` Full 概率顶底五分位 continuation gap 的 14 日 block-bootstrap 95% CI 下界 `>0`。
5. 最长标签覆盖至少 `20` 个独立 14 日块，每方向每 horizon 至少 `100` 个 prequential 观察。

## 5. 冻结 campaign 生命周期

- 只在 `24/72/168h` 三尺度方向一致、Full `p24 >= 0.55` 且 Full `predicted Z24 > 0` 时启动；不要求传统突破。
- 一个方向一个净仓；不在同一小时退出后反手。
- 初始价格风险距离：过去 `168h` 小时收益 RMS × `sqrt(24)`，下限 `1%`；Long/Short 对称。entry stop 只允许收紧。
- 每次 4h 更新：方向翻转或 `p24 < 0.50` 时下一小时 open 退出；否则保持 campaign。
- 无固定止盈、无 14 日 timeout；持有天数只作诊断。
- 当方向对齐价格 MFE 达 `2R` 后，下一小时起保护至少 `50%` 的峰值方向价格推进；gap 按更差 open。

生命周期完全由价格与冻结预测产生，与仓位政策无关。三种仓位政策必须使用相同 campaign id、相同入场时刻、相同退出时刻和原始退出价格。

## 6. 风险与三种同路径仓位政策

- 完整计划数量：按 entry-to-initial-stop、预计双边费用和 `R0=entry equity×1%` 反推；`3x` 是 fill/effective leverage 绝对上限，不是目标。
- 灾难审计：最差 gap/成本路径或单 campaign 实现亏损超过 entry equity `3%`，保持 not live-ready。
- `static_seed`：全程固定完整计划数量的 `35%`。
- `static_full`：从入场开始固定 `100%` 完整计划数量。
- `dynamic`：`35%` 起步；净浮盈且 `p>=0.57` 到 `70%`；MFE≥`1R` 且 `p>=0.60` 到 `85%`；MFE≥`2R` 且 `p>=0.62` 到 `100%`；`0.50<=p<0.55` 降回 `35%`，中间概率只允许维持或降至不高于 `70%`。亏损中禁止增加数量。
- 每次 add 后 projected stop-out equity 不得低于 `entry equity-R0`；每次减仓不受任何 gate 阻挡。

成本：fee `10 bps/fill` + base adverse slippage `4 bps/fill` + 实际 funding；stress adverse slippage `8 bps/fill`。

### 动态控制门禁

Long、Short 分别评估，dynamic 至少同时满足：

1. 与同路径 `static_seed` 相比，base net return 和 Sharpe 都更高；配对 campaign 净 PnL 差的 95% bootstrap CI 下界 `>0`。
2. 相对 `static_full` 的最大回撤不更差、最差单 campaign 不更差，且 dynamic base/stress 都为正。
3. 至少 `20` 个闭合 campaign、平均持有至少 `24h`、年化换手不超过 `24`。
4. 至少 `5` 次真实 add 和 `5` 次真实 reduce，避免动态模块 dormant。
5. 无 risk breach、无 `3x` fill/effective leverage breach；达到 `2R` 的 campaign 除 gap/成本外均保留至少一半价格 MFE。

本轮只判断 historical mechanism evidence，不创建版本、不 promotion、不交接 runner。
