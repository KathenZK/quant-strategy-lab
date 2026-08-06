# HYPE 15m MHEF V2 冻结候选中心全参数消融（2026-07-28）

- Family：`HYPE-15M-Multi-Horizon-EMA-Forecast`
- 对象：已冻结且已判验证失败的 V2 candidate
- 状态：`explore / diagnostic only / not promoted / not live-ready`；不允许 validation 后重新选候选
- 数据边界：只读取 Train 与 Tune，截止 `2026-01-28 08:00 UTC`；没有读取 prefit validation 或 `2026-04-28` 后复用 OOS。

## 结论

围绕最终候选逐槽运行 `71` 个变体，`51` 个仍满足 Train/Tune 毛净收益为正；但只有两个变体在两段净收益上不差于 reference：

1. `zero_cost_diagnostic`：仓位路径完全相同，只是删除现实成本，不是可执行优化。
2. `calibration_min_bars=2048`：Tune 收益、换手和回撤与 reference 完全相同，只改变早期 warmup，并把 Train 起算路径截短；不是持续信号改进。

因此没有可据此登记 V2.1 的参数级优化。消融给出的有效方向是重新设计仓位控制器，而不是继续搜索 EMA 数字。

## Reference

| 项目 | Train | Tune |
| --- | ---: | ---: |
| 净收益 | `+10.42%` | `+5.88%` |
| 最大回撤 | `-13.97%` | `-7.38%` |
| Sharpe | `1.05` | `1.05` |
| 年化换手 | `65.2x` | `57.0x` |
| 调仓次数 | `159` | `90` |

## 各参数得到的证据

### 1. EMA 速度：不是越慢越好

| EMA 集合 | Train 净收益 | Tune 净收益 | Tune 年化换手 | 判断 |
| --- | ---: | ---: | ---: | --- |
| `8/32,16/64,32/128,64/256` | `+10.42%` | `+5.88%` | `57.0x` | reference，唯一稳定集合 |
| medium | `+23.03%` | `-5.74%` | `36.2x` | 明显跨段失效 |
| slow | `+1.09%` | `-3.88%` | `17.1x` | 太慢 |
| ultra | `-18.40%` | `-9.18%` | `11.5x` | 方向本身失败 |

有效尺度集中在约 `2h` 至 `64h`，继续把均线放慢只会降低换手，不会提高预测力。

### 2. Sleeve 分工：`32/128` 是主干，但组合仍有价值

- `32/128` 单 sleeve：Train `+18.71%`、Tune `+5.21%`，接近 reference，但 Tune 少 `0.67pct` 且换手升至 `79.1x`。
- `8/32` 单独运行两段均亏损，但从 ensemble 删除它后 Tune 从 `+5.88%` 降至 `+3.64%`：它不适合独立交易，却可作为低权重早期减仓/转向信息。
- 删除 `16/64` 或 `64/256` 后 Tune 变负；二者承担确认和稳定作用。
- 慢权重 `0.10/0.20/0.30/0.40` 最稳。改成 fast/equal/base 均降低较弱区间表现。

方向：保留“快周期只试探、中周期主导、慢周期确认”的角色设计，不做单均线交叉。

### 3. Coherence 与 dead zone 有用

- coherence `0.5` 最稳；删除 coherence 虽把 Train 提高到 `+13.37%`，却把 Tune 降到 `+4.64%`。
- dead zone `0.10` 最稳；删除后 Train 提高到 `+14.17%`，Tune 降至 `+2.40%`、回撤和换手都恶化。

这两个参数不是 dormant；它们牺牲趋势特别顺的区间，换取较弱区间稳定性。

### 4. 波动率缩放是硬组件

- 目标年化波动 `60%` 是唯一跨段稳定点。
- 删除波动率缩放：Train `-12.53%`、Tune `+2.06%`，跨段断裂。
- 目标波动改变后结果非线性，原因是固定 `buffer/minimum change` 使用绝对仓位单位：缩放仓位会同时改变是否触发交易。

这说明下一版不能继续把风险缩放与成本门分开调参；无交易阈值应随风险预算、预测持久度和实际成本共同变化。

### 5. 成本控制有效，但当前形式有结构缺陷

| 控制方式 | Train 净收益 | Tune 净收益 | Tune 年化换手 |
| --- | ---: | ---: | ---: |
| reference | `+10.42%` | `+5.88%` | `57.0x` |
| 无最小调仓量 | `+10.71%` | `+2.48%` | `89.5x` |
| 无目标带 | `+9.88%` | `+1.31%` | `194.4x` |
| 精确追目标 | `-15.55%` | `-8.94%` | `418.5x` |

`buffer=0.20`、`minimum change=0.15` 都是真正有效组件。

但 `max_position_step=0.25 / 0.50 / 2.0` 的仓位路径逐 K 完全相同，说明“单 K 限速”在 reference 中从未触发，是 dormant 参数。当前渐进加减仓主要来自连续目标变化，而不是 step cap。

更重要的是，固定目标带会允许小残余仓位长期存在：reference 的 time-in-market 接近 `100%`。这与“趋势结束后 flat”并不完全一致。

### 6. Calibration 长度不是优化方向

`256/512` 只因最大 slow EMA 为 `256` 和固定 warmup 关系而近似等价；`1024/2048` 只改变样本初期何时开始出 forecast，Tune 指标完全相同。把 warmup 截短后得到更高 Train 收益不能视为 alpha。

该参数后续应由最大 lookback 自动决定，不再作为可搜索参数。

## 真正可做的 HYPE 优化方向

下一步若继续 HYPE，应建立 materially new V3 position controller，而不是在 V2 上改 EMA：

1. **部分向 aim 移动**：越出成本门后使用 `position += λ × (aim-position)`，让“试探—确认—加仓”真正由 partial adjustment 实现；删除未触发的固定 `max_position_step`。
2. **入场/退出使用不同迟滞**：入场需要较高 coherence；趋势分数进入退出区并持续若干 K 时，使用更小退出 buffer 主动回到 flat，避免成本带留下永久残仓。
3. **风险与成本统一**：无交易阈值不再是固定仓位 `0.20/0.15`，而是比较 forecast 的预计持有期收益与一次往返成本，并随波动率目标同步缩放。
4. **多折 walk-forward 门禁**：在现有 development 内按月/季度滚动，要求大多数折毛净收益均为正；不再只优化一个 Train/Tune 切点。
5. **冻结后只走未来盲测**：历史 prefit validation 已揭示且失败，不能作为 V3 选择集。任何 V3 只能在开发期冻结，再从 `2026-07-28 08:00 UTC` 后积累 fresh prospective OOS。

完整逐槽结果：[candidate-centered ablation CSV](../artifacts/hype_15m_mhef_v2_candidate_centered_ablation.csv)；摘要：[candidate-centered ablation summary](../artifacts/hype_15m_mhef_v2_candidate_centered_ablation_summary.json)。

