# HYPE-1H-PKC 初始价格运动学验证（2026-08-02）

## 结论

本轮没有发现可以称为稳定“价格运动惯性”的证据。Long 与 Short 均为 `kinematic-evidence-supported = false`；研究线保持 `explore / diagnostic-only / not promoted / not live-ready`，不得据此设计 SEED、CORE、加仓或退出。

最重要的现象不是局部速度或加速度，而是 Train 与 Validation 之间方向基准率整体翻转：

- Train 中，过去 `24h` 为负后的未来顺势延续率随 horizon 为 `52.3% / 56.4% / 55.1%`；Validation 降为 `41.4% / 43.9% / 29.3%`。
- Long 则从 Train 的 `49.4% / 44.7% / 41.8%`，变为 Validation 的 `51.1% / 51.1% / 60.4%`。
- Validation 的 Short 平均标准化未来位移为 `-0.19 / -0.32 / -0.54`；也就是过去下跌以后，未来 `3d/7d/14d` 平均反而向上。

这更像非平稳市场中的阶段性外部漂移，而不是局部价格轨迹遵循一条跨时期稳定的惯性定律。

## 冻结边界与数据

- 本轮在查看新统计结果前冻结了[研究合同](../specs/hype-1h-pkc-initial-research-contract-2026-08-02.md)。
- 只使用价格；成交量、funding、OI、清算、盘口和传统技术指标均未进入 `X` 或 `y`。
- Binance HYPE perpetual `15m`：`41,108` 根，`2025-05-30 10:30` 至 `2026-08-01 15:15 UTC`；缺口、重复、关键 null、无效 OHLCV 均为 `0`，raw/normalized 全字段对拍通过。
- 聚合得到 `10,276` 个完整无缺口 `1h` 价格点；时间戳表示上一完整小时首次可见时点。
- 主观察锚点固定为 UTC `00/04/08/12/16/20`，未由结果选择。
- Train：`[2025-06-03, 2026-02-01 UTC)`；Validation：`[2026-02-15, 2026-08-02 UTC)`，每个标签均在边界前完整结束。
- Prospective OOS 锚点 `[2026-08-02, 2026-11-02 UTC)` 未读取；脚本在输入出现该区间后 fail closed。
- 每个方向/标签的历史 Validation 主相位样本约 `460–495`，对应最少 `11` 个非重叠 `14d` block。bar 样本不少，但真正独立的长周期历史仍很有限。

## 验证对象

过去窗口固定为 `6h/24h/72h`，只从对数价格轨迹计算：

- 净位移与平均速度；
- 实际路径长度与路径速度；
- 净位移/路径长度的一致性；
- 最大单步变化/路径长度的脉冲集中度；
- 单步 RMS 噪声；
- 相对起终点直线的路径粗糙度；
- `6h-24h` 与 `24h-72h` 的方向对齐加速度；
- 三尺度速度方向一致数。

过去方向仅为 `sign(24h 位移)`，不设阈值。未来标签为同方向 `3d/7d/14d` 位移、以过去 `72h` 单步噪声构造的标准化位移 `Z`、MFE/MAE、路径一致性和首次触及正负扩散尺度的顺序。

第一阶段没有任何订单、仓位、成本或策略收益。

## 无条件未来路径

| direction | period | horizon | mean Z | continuation | 正尺度先触及 | 负尺度先触及 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Long | Train | `3d` | `+0.02` | `49.4%` | `25.2%` | `25.1%` |
| Long | Validation | `3d` | `-0.02` | `51.1%` | `31.0%` | `27.6%` |
| Long | Train | `7d` | `-0.08` | `44.7%` | `27.1%` | `28.5%` |
| Long | Validation | `7d` | `+0.08` | `51.1%` | `32.6%` | `32.2%` |
| Long | Train | `14d` | `-0.17` | `41.8%` | `23.7%` | `39.4%` |
| Long | Validation | `14d` | `+0.29` | `60.4%` | `29.7%` | `26.4%` |
| Short | Train | `3d` | `+0.05` | `52.3%` | `30.4%` | `21.1%` |
| Short | Validation | `3d` | `-0.19` | `41.4%` | `21.6%` | `31.1%` |
| Short | Train | `7d` | `+0.04` | `56.4%` | `29.9%` | `22.2%` |
| Short | Validation | `7d` | `-0.32` | `43.9%` | `29.8%` | `35.8%` |
| Short | Train | `14d` | `+0.12` | `55.1%` | `39.9%` | `23.2%` |
| Short | Validation | `14d` | `-0.54` | `29.3%` | `15.7%` | `39.3%` |

过去 `24h` 方向本身不具有跨时期稳定延续率；在此基础上寻找精细“物理状态”必须证明能够抵抗这个基准率翻转。

## 固定透明模型

Baseline 只使用三尺度方向对齐速度；Full 加入路径速度、一致性、脉冲、噪声、粗糙度、加速度和尺度一致数。所有标准化只用 Train，Ridge `alpha=10`、Logit `C=0.1`，未搜索超参数。

### Ridge 排序 IC

| direction | horizon | Train OOF baseline/full | Validation baseline/full | Full 顶底五分位 Z 差 |
| --- | ---: | ---: | ---: | ---: |
| Long | `3d` | `-0.082 / +0.171` | `-0.073 / -0.039` | `-0.167` |
| Long | `7d` | `+0.105 / +0.132` | `-0.051 / -0.010` | `-0.014` |
| Long | `14d` | `+0.144 / +0.209` | `+0.114 / +0.100` | `+0.022` |
| Short | `3d` | `-0.190 / -0.193` | `+0.024 / +0.037` | `+0.102` |
| Short | `7d` | `-0.114 / -0.281` | `+0.067 / +0.242` | `+0.748` |
| Short | `14d` | `+0.028 / +0.237` | `+0.119 / +0.193` | `+0.386` |

- Long Full 在 Train OOF 三个尺度均为正，但 Validation 的 `3d/7d` 翻负，只剩 `14d` 弱正。
- Short Full 在 Validation 三个尺度均为正，`7d/14d` 有排序能力；但 Train OOF 的 `3d/7d` 为负，方向同样翻转。
- 两个方向均只有 `1/3` horizon 的 Train OOF 与 Validation IC 同号。冻结合同没有把这条常识性一致性单列成 gate；揭示后只作为更严格可信度 blocker 记录，没有修改公式、模型或重新选择结果。
- Short Validation 的正 IC 主要表示能区分“更差与较不差的下跌后路径”，不能掩盖所有 `7d/14d` 相空间格子的平均 `Z` 都为负。

### Logit

- Long Validation Full AUC 为 `0.450 / 0.443 / 0.621`；只有 `14d` 优于随机且 Brier 优于常数概率。
- Short Validation Full AUC 为 `0.545 / 0.626 / 0.673`；`7d/14d` Brier 略优于常数概率，`3d` 更差。
- 删除 `|Z|` 最大 `1%` 后，各 horizon IC 符号均保留，说明结论不是单个极端标签造成；但不能修复跨时期翻转。

## 单变量与相空间

- Long 没有任何预声明结构量在任一 horizon 获得 expected-sign block-bootstrap 95% CI 排除零。
- Short 只有两条孤立关系通过：`6h` 脉冲集中度在 `7d` 为负向，`24h-72h` 方向对齐加速度在 `14d` 为正向；没有任何变量在两个 horizon 同时通过。
- 因而 Long/Short 的 `robust_structural_features` 都为空，未达到“至少两个结构量、每个至少两个 horizon”的门槛。
- `5×5` 速度—加速度相图每格只有约 `5–47` 个相关样本。Long 图呈斑块状且主锚点 `7d IC=-0.010`，其余三相位转为小幅正值；只有 `1/4` 相位同号。
- Short `7d` 四相位 IC 均为正（`0.163–0.242`），但所有 Validation `7d/14d` 相图格子的平均 `Z` 均为负，反映的是条件排序而非绝对趋势延续。

## 冻结门槛

| gate | Long | Short |
| --- | --- | --- |
| Validation Full Ridge IC 至少 `2/3` 为正 | FAIL | PASS |
| Full IC 中位数不差于 Baseline | PASS | PASS |
| Logit AUC/Brier 至少 `2/3` 有用 | FAIL | PASS |
| 至少两个结构量跨两个 horizon bootstrap 通过 | FAIL | FAIL |
| 删除极端 `1%` 后多数 IC 符号保留 | PASS | PASS |
| 至少 `3/4` 锚点相位的 `7d` IC 同号 | FAIL | PASS |
| 至少 `10` 个独立 `14d` block | PASS | PASS |
| 最终 `kinematic-evidence-supported` | **FALSE** | **FALSE** |

## 解释边界

本轮否定的是冻结的 `6h/24h/72h` 局部价格运动学状态具有稳定预测力，不是否定所有“价格运动物理类比”。现有证据支持三个更谨慎的判断：

1. HYPE 在这段短历史里首先是非平稳的；市场阶段方向漂移大于局部惯性。
2. 路径一致性、粗糙度、脉冲和加速度存在若干局部相关，但没有跨 horizon、跨时期形成稳定定律。
3. 当前结果不允许从 Validation 挑出 Short `7d/14d`，也不允许新增更长过去窗口后继续使用同一 Validation。

若继续研究，必须提出 materially new 且事前冻结的“外部场”价格表示，例如更长 `7d/30d` 纯价格漂移与局部运动的相对关系，并等待新的 prospective OOS；不能在本次已揭示历史上修补。

## 证据

- [机器结果](../artifacts/hype_1h_pkc_research_2026-08-02.json)
- [未来标签基准](../artifacts/hype_1h_pkc_label_summary_2026-08-02.csv)
- [单变量分箱](../artifacts/hype_1h_pkc_univariate_bins_2026-08-02.csv)
- [单变量 bootstrap 效应](../artifacts/hype_1h_pkc_univariate_effects_2026-08-02.csv)
- [模型指标](../artifacts/hype_1h_pkc_model_metrics_2026-08-02.csv)
- [标准化系数](../artifacts/hype_1h_pkc_model_coefficients_2026-08-02.csv)
- [相空间网格](../artifacts/hype_1h_pkc_phase_space_2026-08-02.csv)
- [锚点相位敏感性](../artifacts/hype_1h_pkc_phase_sensitivity_2026-08-02.csv)
- [逐锚点特征与标签](../artifacts/hype_1h_pkc_labelled_observations_2026-08-02.parquet)
- [复现脚本](../scripts/research_hype_1h_pkc.py)
