# HYPE-1H-PKTSC 延续预测与动态控制双门禁验证（2026-08-03）

## 结论

用户要求的两个问题都已经直接验证，结果均为 **FALSE**：

1. **只根据价格变化持续判断趋势未来是否延续：没有得到稳定、可校准的因果证据。**
2. **根据该延续概率动态加减仓、尽量吃完整趋势：没有提供独立增益，反而比同路径固定小仓更差。**

这次失败不再是“回到传统指标”的实现偏差：预测特征完全来自闭合价格的位移、速度、路径长度、coherence、burst、roughness、跨尺度加速度、趋势年龄和回吐；没有 EMA、MA、Donchian、ATR、ADX、成交量、资金费率、OI 或订单信息。

## 数据、时序和证据身份

- Binance USD-M `HYPEUSDT` perpetual：`41,108` 根闭合 `15m` K，`2025-05-30 10:30` 至 `2026-08-01 15:15 UTC`。
- 源数据缺口、重复、关键空值、无效 OHLCV 均为零，raw/normalized 全字段对账通过。
- 聚合 `10,276` 根完整 `1h` execution bar，无完整小时缺口；特征时间戳向后移一小时，确保闭合后才可用。
- 每 `4h` 更新一次；每个测试日重新拟合，预测 horizon 为 `24/72/168/336h`。
- 每次训练只允许使用 `test_day-horizon` 以前、未来标签已经完全结束的样本；每方向至少 `300` 个历史锚点才开始预测。
- 历史区间已被相邻研究观察，所以本报告只称 historical causal walk-forward，不冒充 locked OOS。
- Prospective OOS `[2026-08-02, 2026-11-02 UTC)` 未进入输入、未生成预测、未回测。

## 第一门：未来延续预测

### 整体 prequential 结果

| 方向 | horizon | Full IC | Full AUC | Full / 基准 Brier | observations |
| --- | ---: | ---: | ---: | ---: | ---: |
| Long | `24h` | `-0.118` | `0.465` | `0.284 / 0.251` | 912 |
| Long | `72h` | `-0.039` | `0.507` | `0.305 / 0.254` | 895 |
| Long | `168h` | `+0.013` | `0.477` | `0.321 / 0.254` | 881 |
| Long | `336h` | `+0.087` | `0.567` | `0.315 / 0.260` | 840 |
| Short | `24h` | `+0.019` | `0.506` | `0.275 / 0.251` | 957 |
| Short | `72h` | `+0.107` | `0.568` | `0.271 / 0.253` | 947 |
| Short | `168h` | `+0.127` | `0.548` | `0.297 / 0.255` | 926 |
| Short | `336h` | `+0.118` | `0.515` | `0.323 / 0.260` | 879 |

- Long 只有 `2/4` IC 为正；最近决策最需要的 `24h/72h` 都为负。
- Short 的连续收益排序 IC `4/4` 为正，但概率预测在 `4/4` horizon 都比“每次只报训练基准延续率”得到更差 Brier。因此它不能被解释成可执行的延续概率。
- Full 模型相对只用速度的 Baseline 没有稳定优势；增加路径形状没有修复概率校准。

### 概率分层与月份稳定性

- Long `24h` 概率最高五分位减最低五分位的实际延续率差为 **`-6.56pp`**，14 日 block-bootstrap 95% CI `[-20.24pp,+8.86pp]`。模型给得越高，实际反而略差。
- Short 对应差只有 **`+1.56pp`**，95% CI `[-13.18pp,+18.02pp]`，无法排除零或反向。
- Long `24h` 月度 IC 只有 `5/11` 为正；Short 为 `6/10`，刚到 60%，但概率 gap 和 Brier 仍失败。
- 最长 horizon 各覆盖 `20` 个独立 14 日块，样本数门槛通过；所以本轮不是简单因为锚点行数少，而是关系本身不稳定、不可校准。

### 延续预测门禁

| gate | Long | Short |
| --- | --- | --- |
| Full IC 至少 `3/4` 为正 | FAIL（2/4） | PASS（4/4） |
| Full 中位 IC 不差于 Baseline | PASS | PASS |
| Logit 至少 `3/4` 优于基准 | FAIL（0/4） | FAIL（0/4） |
| 24h 月度 IC 至少 60% 为正 | FAIL（5/11） | PASS（6/10） |
| 24h 顶底概率 gap CI 下界 > 0 | FAIL | FAIL |
| 独立块与观察数 | PASS | PASS |
| `continuation-prediction-supported` | **FALSE** | **FALSE** |

## 第二门：动态加减仓能否吃完整趋势

### 公平对照

三种政策共享完全相同的 campaign id、入场时刻、退出时刻和原始退出价格：

- `static_seed`：全程固定完整计划数量的 `35%`。
- `static_full`：从入场开始固定 `100%`。
- `dynamic`：`35%` 起步，根据冻结概率与 MFE 离散加到 `70/85/100%` 或减回 `35%`。

因此 dynamic 与 static 的差异只来自仓位变化及其成本，不存在“动态政策碰巧选了另一批交易”的混淆。

### 标准成本结果

| 方向/政策 | net return | Sharpe | MDD | trades | win rate | avg hold | turnover/yr |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Long static seed | `-2.08%` | `-1.32` | `-2.79%` | 37 | `27.0%` | `12.2h` | `7.02` |
| Long static full | `-5.87%` | `-1.32` | `-7.80%` | 37 | `27.0%` | `12.2h` | `20.06` |
| Long dynamic | `-3.10%` | `-1.28` | `-3.48%` | 37 | `21.6%` | `12.2h` | `9.98` |
| Short static seed | `-1.70%` | `-1.11` | `-2.65%` | 34 | `35.3%` | `15.3h` | `4.84` |
| Short static full | `-4.83%` | `-1.11` | `-7.40%` | 34 | `35.3%` | `15.3h` | `13.83` |
| Short dynamic | `-2.06%` | `-0.83` | `-3.79%` | 34 | `32.4%` | `15.3h` | `7.14` |

- Dynamic 比 static full 少亏，是因为多数时间只持有较小仓位，不是加减仓产生了正 edge。
- 真正公平的增量基准是 static seed：Long dynamic 多亏约 `1.02pp`，Short 多亏约 `0.35pp`。
- 配对到每个相同 campaign，dynamic-static seed 平均差为 Long `-2.82 bps/trade`，95% CI `[-7.27,+1.15] bps`；Short `-1.04 bps/trade`，CI `[-5.08,+2.86] bps`。两者均没有正增量。
- Dynamic 模块并非 dormant：Long `16` 次 add、`11` 次 reduce；Short `21/11`。失败就是动态动作发生后的实际结果。

### 不是成本单独造成

| 方向 | dynamic gross | base | 8bps slippage stress |
| --- | ---: | ---: | ---: |
| Long | `-1.83%` | `-3.10%` | `-3.38%` |
| Short | `-1.39%` | `-2.06%` | `-2.28%` |

即使手续费、滑点、funding 全部设为零，两边仍亏；成本扩大失败，但没有制造失败。

### 为什么没有吃到 3–14 天趋势

- Long 37 个 campaign 中，28 个因概率低于 0.50 或 24h 方向翻转退出，9 个触发价格 stop；平均持有仅 `12.2h`，最长 `57h`。
- Short 34 个中，30 个由概率/方向退出，4 个 stop；平均 `15.3h`，最长 `48h`。
- 顺序概率不是缓慢变化的“趋势生命值”，而是快速波动。把它每 4h 用作控制量，重新制造了短持仓和反复试错，根本没有达到目标 `3–14d`。
- Long 只有 3 笔达到 `2R`，Short 为 0；所以半 MFE 保护没有足够的右尾事件可发挥。

### 半 MFE 与风险账本

- 达到 `2R` 的 Long campaign 均机械保留至少一半价格 MFE，违规为 0；删除 MFE floor 后 Long 从 `-3.10%` 变为 `-2.86%`，说明保护规则正确但本样本没有净增益。
- Short 没有任何 `2R` campaign，含/不含 MFE floor 完全 path-equal。
- Short dynamic 无 R0、3% disaster 或 3x leverage breach。Long 最大 open risk `1.00095%`，因持仓期间 funding/成本漂移形成 14 个严格大于 `1%` 的微小记录，但最差 campaign 仅 `-0.40%`、最大有效杠杆 `0.32x`，远低于 `3%/3x` 灾难上限。该细微账本偏差不是收益失败原因，但仍阻止 live-readiness。

### 动态控制门禁

| gate | Long | Short |
| --- | --- | --- |
| Return/Sharpe 高于 static seed | FAIL | FAIL |
| 配对增量 bootstrap CI 下界 > 0 | FAIL | FAIL |
| 风险不差于 static full | PASS | PASS |
| Base 与 stress 都正收益 | FAIL | FAIL |
| ≥20 campaigns、平均 ≥24h、换手合格 | FAIL（持有） | FAIL（持有） |
| Add/reduce 非 dormant | PASS | PASS |
| 风险与杠杆完全清洁 | FAIL（微小 R0 漂移） | PASS |
| 半 MFE 执行清洁 | PASS | PASS |
| `dynamic-control-supported` | **FALSE** | **FALSE** |

## 理论复盘

本轮把“静态预测没有验证”向前推进了一步：即使每 4h 因果重训、加入 7d/14d 外部价格尺度、趋势年龄和回吐状态，过去价格仍不能形成稳定的延续概率。失败链条是：

```text
过去价格路径可描述
  -> 延续概率不可校准
  -> 概率每 4h 快速翻动
  -> campaign 平均 12–15h 就退出
  -> 加仓集中在错误或短暂高置信时点
  -> 零成本仍负，标准成本更差
```

因此，当前证据不仅否定旧技术指标实现，也否定了本轮冻结的“局部纯价格状态足以提供趋势生命值并驱动仓位”这一具体理论。它不构成数学上“不可能存在任何趋势策略”的证明；但继续在同一历史上换窗口、概率阈值或加仓层级，已经没有研究可信度。

## 决策

1. `HYPE-1H-PKTSC` 保持 `explore / diagnostic-only / not promoted / not live-ready`，不创建 `V1`。
2. 不在已揭示历史上把 `p<0.50` 改慢、删除概率退出、挑 Short IC 或调整层级后重新报结果。
3. Prospective OOS 保持未揭示；当前机制没有历史支持，不应以 prospective 数据承担“救参数”的角色。
4. 若继续验证趋势生命值，必须加入 materially new 的外部状态，例如跨市场价格 lead-lag、OI/清算、主动成交失衡或流动性变化；否则只能等待更长的 HYPE 历史，而不是继续堆叠价格变换。

## 证据

- [冻结合同](../specs/hype-1h-pktsc-initial-research-contract-2026-08-03.md)
- [机器主结果](../artifacts/hype_1h_pktsc_research_2026-08-03.json)
- [总体预测指标](../artifacts/hype_1h_pktsc_prediction_metrics_2026-08-03.csv)
- [月度预测稳定性](../artifacts/hype_1h_pktsc_monthly_metrics_2026-08-03.csv)
- [逐锚点 prequential 预测](../artifacts/hype_1h_pktsc_prequential_predictions_2026-08-03.parquet)
- Long：[campaigns](../artifacts/hype_1h_pktsc_long_2026-08-03_campaigns.csv) · [schedule](../artifacts/hype_1h_pktsc_long_2026-08-03_campaign_schedule.csv) · [dynamic trades](../artifacts/hype_1h_pktsc_long_2026-08-03_dynamic_trades.csv)
- Short：[campaigns](../artifacts/hype_1h_pktsc_short_2026-08-03_campaigns.csv) · [schedule](../artifacts/hype_1h_pktsc_short_2026-08-03_campaign_schedule.csv) · [dynamic trades](../artifacts/hype_1h_pktsc_short_2026-08-03_dynamic_trades.csv)
- [复现脚本](../scripts/research_hype_1h_pktsc.py)
