# HYPE-1D-PKC 初始纯价格运动学验证（2026-08-03）

## 结论

真正按日 K 观察后，**当前 Validation 的做多条件排序明显强于 15 分钟和小时状态，但仍不能证明存在稳定的日线趋势延续定律**。

- Long Validation Full Ridge IC：未来 `3d/7d/14d = +0.264/+0.336/+0.450`，点估计有经济上值得继续观察的强度。
- 但 Long Train expanding OOF 为 `-0.196/-0.101/+0.256`，只有 `1/3` 与 Validation 同号；前两个尺度完整反转。
- Short Train/Validation Full IC 虽 `3/3` 同号，Validation 只有 `+0.022/+0.128/+0.127`，Full 中位 IC 还不如只用速度的 Baseline。
- Long/Short 都只有一个 horizon 的 Logit 同时优于随机分类和常数 Brier；都没有两个结构特征跨两个 horizon 获得 expected-sign bootstrap 支持。
- Q1/Q5 稳健性检验最少只有 Long `9`、Short `6` 个独立 14 日块，远低于冻结的 `20` 块门槛。

所以本轮最准确的判断是：**日线比 15 分钟更有“候选信号形状”，尤其是 Long `14d`；但 HYPE 历史太短且市场阶段翻转太强，当前只能保留为前瞻观察假设，不能落成策略。**

## 数据与时序

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 源数据：`41,108` 根闭合 `15m` K，`2025-05-30 10:30` 至 `2026-08-01 15:15 UTC`；缺口、重复、关键空值、OHLC 异常均为零，raw/normalized 对账通过。
- 完整日 K：只保留恰有 `96` 根源 K 的 UTC 日，共 `427` 根；可用时刻范围 `2025-06-01` 至 `2026-08-01 UTC`。
- 两个不完整源日仅为数据集首尾边界，未填补、未进入完整日 K；完整日序列无缺口。
- Train：`[2025-06-15, 2026-02-01 UTC)`；14 日 embargo；Validation：`[2026-02-15, 2026-08-03 UTC)`，并按每个 horizon purge 尾部。
- Prospective OOS：`[2026-08-03, 2026-11-03 UTC)`，未读取、未生成标签。

所有预测特征只来自闭合日线价格；OHLC 只用于完整日 K 质量审计和未来路径，不使用传统指标、成交量、资金费率、OI 或订单数据。本轮无订单、仓位、成本或收益回测。

## 无条件延续基准

| 方向 | 时期 | 未来 3d | 未来 7d | 未来 14d |
| --- | --- | ---: | ---: | ---: |
| Long | Train | `43.8%` | `36.2%` | `31.5%` |
| Long | Validation | `54.5%` | `51.1%` | `54.5%` |
| Short | Train | `49.2%` | `52.3%` | `48.8%` |
| Short | Validation | `42.9%` | `43.8%` | `18.2%` |

对应平均方向归一化 `Z`：Long 从 Train 的 `-0.13/-0.24/-0.33` 翻为 Validation 的 `+0.10/+0.16/+0.41`；Short 从 Train 约零翻为 Validation 的 `-0.15/-0.37/-0.62`。

这不是一个平稳的“上涨后继续涨、下跌后继续跌”基准。它首先说明样本后半段偏上涨：过去 7 日上涨状态后略偏继续上涨，而下跌状态尤其在未来 14 日大多反转或失败。

## 透明模型结果

Full 模型加入路径速度、一致性、脉冲、噪声、粗糙度、加速度和尺度一致数；Ridge `alpha=10`、Logit `C=0.1` 固定，没有搜索参数。

| 方向 | horizon | Train OOF Full IC | Validation Baseline / Full IC | Full 顶底五分位 Z 差 | Full AUC | Full / 常数 Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Long | `3d` | `-0.196` | `+0.229 / +0.264` | `+0.707` | `0.613` | `0.272 / 0.260` |
| Long | `7d` | `-0.101` | `+0.154 / +0.336` | `+1.017` | `0.637` | `0.273 / 0.272` |
| Long | `14d` | `+0.256` | `+0.278 / +0.450` | `+1.740` | `0.771` | `0.223 / 0.301` |
| Short | `3d` | `+0.131` | `+0.061 / +0.022` | `-0.200` | `0.586` | `0.250 / 0.249` |
| Short | `7d` | `+0.075` | `+0.228 / +0.128` | `+0.065` | `0.543` | `0.280 / 0.253` |
| Short | `14d` | `+0.052` | `+0.360 / +0.127` | `+0.040` | `0.670` | `0.239 / 0.243` |

- Long `14d` 是本轮唯一同时具有 Train/Validation 同号、明显 Validation 排序和有用概率校准的组合。
- Long `3d/7d` 的 Validation 漂亮，但 Train OOF 为负，不能解释成跨时期规律。
- Short 的正 IC 只是在整体不利的 Short 状态内排序“更差与较不差”；它没有修复 Validation 的负平均 `Z` 和低绝对延续率。
- 删除 `|Z|` 最大 `1%` 后，Long 三个 IC 全部保号，Short `2/3` 保号；点估计不是单个极端标签制造，但这不能修复阶段与功效问题。

## 结构量与物理解释

- 预声明结构量中，只有 Short 的过去 `14d coherence` 对未来 `7d` 获得一次 expected-positive 支持：Q5-Q1 `Z=+1.055`，95% block CI `[+0.092,+1.723]`，但只有 `11` 个块。
- 没有任何结构特征在两个 horizon 同时通过；Long 一个都没有。
- Long 多个高 burst/roughness 点估计反而对应更高未来 `Z`，与“冲量集中后衰减、粗糙度越低越延续”的预声明方向相反。这说明 Full 模型的排序更可能依赖阶段内组合关系，而不是一条清晰、可解释的物理定律。
- `5×5` 速度—加速度相图每格中位数只有约 `2–5` 个样本，不具备解释资格。
- 七个 weekly stride 的 Long `7d` IC 有 `6/7` 为正，但每组只有 `11–14` 个 Validation 样本；Short 为 `5/7` 正、每组 `9–12` 个。该检验只能排除“完全由一个日历偏移产生”，不能增加独立历史。

## 与短周期的关系

| 观察状态 | 未来尺度 | Validation Full IC 特征 | 跨时期稳定性 | 结论 |
| --- | --- | --- | --- | --- |
| `15m` | `1h/3h/6h/12h` | 最大绝对值约 `0.034` | Long/Short 均 `0/4` 同号 | 接近随机噪声 |
| `1h`，每 4h 锚点 | `3d/7d/14d` | Long `-0.039/-0.010/+0.100`；Short `+0.037/+0.242/+0.193` | 两方向均 `1/3` 同号 | 有局部排序但阶段翻转 |
| `1d` | `3d/7d/14d` | Long `+0.264/+0.336/+0.450`；Short `+0.022/+0.128/+0.127` | Long `1/3`、Short `3/3` 同号 | 点估计更强，但方向基准和独立样本不够 |

因此“周期拉长后趋势更明显”在**当前 Validation 做多排序**上得到部分支持，但“延续性成为稳定可交易规律”没有得到支持。更长周期降低了微观噪声，同时也把可用历史压缩为少量市场阶段；HYPE 当前数据无法区分真正惯性与单边阶段漂移。

## 冻结门槛

| gate | Long | Short |
| --- | --- | --- |
| Validation Full IC 至少 `2/3` 为正 | PASS | PASS |
| Full 中位 IC 不差于 Baseline | PASS | FAIL |
| Logit 至少 `2/3` 有用 | FAIL（`1/3`） | FAIL（`1/3`） |
| 两个结构量各跨两个 horizon | FAIL | FAIL |
| Train/Validation IC 至少 `2/3` 同号 | FAIL（`1/3`） | PASS（`3/3`） |
| Trim `1%` 至少 `2/3` 保号 | PASS | PASS |
| 每 horizon 至少 50 个 Validation 日观察 | PASS（最少 `88`） | PASS（最少 `66`） |
| 至少 20 个独立 14 日块 | FAIL（最少 `9`） | FAIL（最少 `6`） |
| `daily-kinematic-evidence-supported` | **FALSE** | **FALSE** |

## 决策与下一步边界

1. 本轮保持 `explore / diagnostic-only / not promoted / not live-ready`，不创建策略 `V1`，不做加减仓、止盈止损或收益回测。
2. 不允许从已揭示 Validation 挑出 Long `14d` 后在同一时期调窗口、系数或阈值。
3. 最值得保留的前瞻假设是：日线 Long 状态中，过去 `3/7/14d` 的联合路径结构可能对未来 `14d` 有排序力；它必须原样等待 prospective OOS。
4. 单靠三个月 prospective OOS 仍只能增加约 6 个非重叠 14 日块。若希望更快区分规律与阶段，合理方法是把同一冻结假设分别应用到 BTC、ETH、SOL 等独立资产家族，分别报告、不混池、不共享参数；这不是 HYPE 结果的补救或 promotion。

## 证据

- [机器结果](../artifacts/hype_1d_pkc_research_2026-08-03.json)
- [未来标签基准](../artifacts/hype_1d_pkc_label_summary_2026-08-03.csv)
- [模型指标](../artifacts/hype_1d_pkc_model_metrics_2026-08-03.csv)
- [标准化系数](../artifacts/hype_1d_pkc_model_coefficients_2026-08-03.csv)
- [单变量分箱](../artifacts/hype_1d_pkc_univariate_bins_2026-08-03.csv)
- [单变量 bootstrap 效应](../artifacts/hype_1d_pkc_univariate_effects_2026-08-03.csv)
- [相空间网格](../artifacts/hype_1d_pkc_phase_space_2026-08-03.csv)
- [weekly stride 敏感性](../artifacts/hype_1d_pkc_weekly_stride_sensitivity_2026-08-03.csv)
- [逐日特征与标签](../artifacts/hype_1d_pkc_labelled_observations_2026-08-03.parquet)
- [复现脚本](../scripts/research_hype_1d_pkc.py)
