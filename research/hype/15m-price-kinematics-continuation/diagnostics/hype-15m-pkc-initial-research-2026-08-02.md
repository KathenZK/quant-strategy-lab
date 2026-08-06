# HYPE-15M-PKC 初始短周期价格运动学验证（2026-08-02）

## 结论

HYPE 的15分钟级别没有显示出比1小时研究更清晰、更稳定的趋势延续。Long 与 Short 均为 `short-horizon-kinematic-evidence-supported = false`；不得进入交易策略设计。

最强的反证是跨时期完整翻转：

- Long Full Ridge IC 在 Train 的未来 `1h/3h/6h/12h` 全为负，Validation 全为微弱正值，`0/4` 同号。
- Short 则在 Train 四个尺度全为正，Validation 全为负，仍为 `0/4` 同号。
- Validation Full IC 绝对值最大只有 `0.034`，Logit 没有一个方向在任何 horizon 同时做到 AUC `>0.5` 且 Brier 优于常数概率。

因此这不是“持续几小时的惯性更强”，而更接近带阶段漂移的短周期噪声。过去3小时的方向在未来1–12小时的无条件延续率基本围绕50%。

## 冻结边界与数据

- 在查看结果前冻结[研究合同](../specs/hype-15m-pkc-initial-research-contract-2026-08-02.md)。
- Binance HYPE perpetual `15m`：`41,108` 根，`2025-05-30 10:30` 至 `2026-08-01 15:15 UTC`；缺口、重复、关键 null、无效 OHLCV 为 `0`，raw/normalized 全字段对拍通过。
- 原始 timestamp 为 bar open，研究索引统一加 `15m` 后表示价格首次完整可见，未使用未闭合 K。
- 过去窗口 `4/12/24` bars，即 `1h/3h/6h`；方向为过去 `3h` 对数位移符号。
- 未来标签 `4/12/24/48` bars，即 `1h/3h/6h/12h`。
- 主样本为每小时 `:00`，`:15/:30/:45` 只作预声明相位敏感性。
- Train `[2025-06-03, 2026-02-01 UTC)`；Validation `[2026-02-15, 2026-08-02 UTC)`；每个标签在边界前完整结束。
- 每方向 Validation 主相位约 `1,982–2,032` 个样本，最少 `229` 个12小时 block，独立历史数量足以否定“大而稳定”的短周期效应。
- Prospective OOS `[2026-08-02, 2026-11-02 UTC)` 未读取；没有策略或 PnL 回测。

## 无条件延续

| direction | period | `1h` | `3h` | `6h` | `12h` |
| --- | --- | ---: | ---: | ---: | ---: |
| Long continuation | Train | `48.6%` | `47.8%` | `48.0%` | `49.2%` |
| Long continuation | Validation | `48.7%` | `50.2%` | `52.0%` | `50.7%` |
| Short continuation | Train | `47.6%` | `47.7%` | `47.8%` | `48.9%` |
| Short continuation | Validation | `47.7%` | `49.1%` | `50.5%` | `49.8%` |

仅凭过去3小时方向，没有看到稳定高于50%的未来延续概率。Long Validation 的 `6h` 为 `52.0%`，但 Train 同项仅 `48.0%`；这是阶段变化，不是可复现规律。

标准化未来位移也接近零：

- Long Validation mean Z：`-0.016 / +0.024 / +0.059 / +0.072`。
- Short Validation mean Z：`-0.049 / -0.029 / -0.017 / -0.033`。

这说明 Validation 本身略有向上漂移：过去上涨后的未来位移略偏正，过去下跌后的未来位移略偏负，但幅度很小。

## 固定模型

Baseline 只用过去 `1h/3h/6h` 方向对齐速度；Full 加入路径速度、一致性、脉冲集中度、噪声、粗糙度、两项加速度和三尺度一致数。Ridge `alpha=10`、Logit `C=0.1`，无超参数搜索。

### Full Ridge IC

| direction | period | `1h` | `3h` | `6h` | `12h` |
| --- | --- | ---: | ---: | ---: | ---: |
| Long | Train expanding OOF | `-0.042` | `-0.013` | `-0.008` | `-0.012` |
| Long | Validation | `+0.016` | `+0.007` | `+0.022` | `+0.023` |
| Short | Train expanding OOF | `+0.002` | `+0.054` | `+0.019` | `+0.007` |
| Short | Validation | `-0.034` | `-0.001` | `-0.031` | `-0.008` |

- 数值总体接近零，且 Long/Short 全部 `0/4` Train—Validation 同号。
- Long Validation 虽形式上 `4/4` 为正，但最大仅 `0.023`，顶底预测五分位实际 Z 差只有 `0.012 / 0.024 / 0.093 / 0.084`，且 Logit 全部不如常数概率。
- Short Validation 四个 IC 均不为正，模型没有数小时顺势排序能力。
- 删除 `|Z|` 最大 `1%` 后八个方向/horizon 的 IC 符号全部保留，结论不是极端 K 线造成。

## 路径结构量

唯一值得保留为物理解释线索的是脉冲集中度：

- Long `3h`：过去 `1h` 脉冲集中度 Q5-Q1 的未来 Z 差为 `-0.195`，95% block-bootstrap CI `[-0.350,-0.049]`。
- Long `3h`：过去 `3h` 脉冲集中度差为 `-0.184`，CI `[-0.349,-0.020]`。
- Long `6h`：过去 `3h` 脉冲集中度差为 `-0.203`，CI `[-0.387,-0.008]`。

含义是：同样向上移动，如果位移集中在一两根15分钟价格跳跃中，未来3–6小时往往更差；分散完成的移动相对更健康。

但这仍未通过冻结门槛：只有 `burst_12` 覆盖两个 horizon，合同要求至少两个结构量各覆盖三个 horizon。Short 没有任何结构量获得 expected-sign 置信支持；路径一致性、粗糙度、加速度和尺度一致数均未稳定成立。

## 相空间与相位

- 每个速度—加速度格约 `29–160` 个 Validation 样本，比1小时长周期相图充足，但正负区域仍交错。
- Long `6h` 主相位 IC `+0.022`，其他分钟相位为 `-0.001/-0.011/+0.023`，只有 `2/4` 同号。
- Short `6h` 主相位 `-0.031`，其他相位为 `+0.009/-0.032/+0.035`，同样只有 `2/4` 同号。
- 因而所谓惯性取决于从整点、15分、30分还是45分开始观察，不像稳定路径性质。

## 与1小时长周期研究对比

| 研究 | Validation 样本/方向 | 最大 Full IC | Train—Validation 同号 | 稳定结构量 | 结论 |
| --- | ---: | ---: | ---: | ---: | --- |
| `HYPE-1H-PKC`，未来 `3d/7d/14d` | `460–495` | Short `7d = 0.242` | `1/3` | `0` | 阶段翻转，未通过 |
| `HYPE-15M-PKC`，未来 `1h/3h/6h/12h` | `1,982–2,032` | `|IC| = 0.034` | `0/4` | `0` | 信号更弱，未通过 |

短周期增加了样本，却没有提高可预测性；反而把相关性压到更接近零。用户提出的“一阵一阵”在价格图上可能肉眼可见，但起点和终点是事后确定的。固定时间锚点下，无法提前区分哪一阵会继续。

## 冻结门槛

| gate | Long | Short |
| --- | --- | --- |
| Validation Full IC 至少 `3/4` 为正 | PASS | FAIL |
| Full IC 中位数不差于 Baseline | PASS | PASS |
| Logit AUC/Brier 至少 `3/4` 有用 | FAIL | FAIL |
| 至少两个结构量跨三个 horizon bootstrap 通过 | FAIL | FAIL |
| Train—Validation IC 至少 `3/4` 同号 | FAIL (`0/4`) | FAIL (`0/4`) |
| 删除极端 `1%` 后至少 `3/4` 同号 | PASS | PASS |
| 至少 `3/4` 分钟相位同号 | FAIL (`2/4`) | FAIL (`2/4`) |
| 至少30个独立12小时 block | PASS | PASS |
| 最终 evidence supported | **FALSE** | **FALSE** |

## 判断

1. 15分钟价格确实会连续涨跌几小时，但固定时间、当时可见的路径状态无法稳定预测这段运动是否还会继续。
2. 数小时尺度比3–14天尺度拥有更多独立样本，但预测关系更接近零，不是更明显。
3. “单根或少数 K 线完成的大幅脉冲更容易衰减”有局部证据，可以作为未来新合同中的风险削减假设，不能直接变成入场条件。
4. 不得在已揭示 Validation 上改成只做 Long、只用 `6h/12h` 或只保留 burst；这些都是事后挑选。

## 证据

- [机器结果](../artifacts/hype_15m_pkc_research_2026-08-02.json)
- [未来路径基准](../artifacts/hype_15m_pkc_label_summary_2026-08-02.csv)
- [单变量分箱](../artifacts/hype_15m_pkc_univariate_bins_2026-08-02.csv)
- [单变量 bootstrap 效应](../artifacts/hype_15m_pkc_univariate_effects_2026-08-02.csv)
- [模型指标](../artifacts/hype_15m_pkc_model_metrics_2026-08-02.csv)
- [标准化系数](../artifacts/hype_15m_pkc_model_coefficients_2026-08-02.csv)
- [相空间网格](../artifacts/hype_15m_pkc_phase_space_2026-08-02.csv)
- [分钟相位敏感性](../artifacts/hype_15m_pkc_phase_sensitivity_2026-08-02.csv)
- [逐锚点特征与标签](../artifacts/hype_15m_pkc_labelled_observations_2026-08-02.parquet)
- [复现脚本](../scripts/research_hype_15m_pkc.py)
- [1小时尺度对照](../../1h-price-kinematics-continuation/diagnostics/hype-1h-pkc-initial-research-2026-08-02.md)
