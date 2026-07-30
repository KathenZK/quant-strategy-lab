# BIN-15M-EMAX 特征/标签双消融：局部形态信息真实存在（毛 +0.13 ATR、逐年为正），但只有成本墙的一半

- 日期：2026-07-29（UTC+8）
- 状态：家族维持 `archived / HARD-GATE-FAILED`；本报告为死因复核，不重开研究线、不支持 promotion
- 契约：[`bin-15m-emax-feature-ablation-contract-2026-07-29.md`](../specs/bin-15m-emax-feature-ablation-contract-2026-07-29.md)（跑数前冻结；已揭示的 2026H1 完全未使用）
- 假设来源：用户质疑 15m 线失败是"特征构造有问题"——挤压突破/放量/趋势末端等局部形态未被表达，或绝对收益标签让行情淹没了交叉质量信号
- 数据：冻结开发集 [`event_dataset_dev.parquet`](../artifacts/event_dataset_dev.parquet) 交易池 292,421 事件（2021–2025），`b4_2` 含成本；扩窗 purged 年度 OOF（2022–2025），LightGBM 回归，四变体仅特征集/标签变换不同
- 脚本：[`research_feature_label_ablation.py`](../scripts/research_feature_label_ablation.py)；产物：[`feature_ablation_report.json`](../artifacts/feature_ablation/feature_ablation_report.json)、[`oof_scores_ablation.parquet`](../artifacts/feature_ablation/oof_scores_ablation.parquet)

## 1. 2×2 结果

| 变体 | 特征 | 标签 | 十分位 Spearman | 顶桶净 ATR（合并） | 顶桶逐年为正 | 预注册双门 |
|---|---|---|---:|---:|---|---|
| `ref` | 全部 | 绝对 | 1.00 | **+0.083** | 3/4 年 | **通过** |
| `a_local_abs` | 仅局部 | 绝对 | 1.00 | −0.175 | 0/4 年 | 未过 |
| `b_full_rel` | 全部 | 相对（日×侧组内百分位） | 1.00 | −0.195 | 0/4 年 | 未过 |
| `c_local_rel` | 仅局部 | 相对 | 0.99 | −0.213 | 0/4 年 | 未过 |

**预注册判定：特征假设不成立**（局部变体无一过 Gate B）。

## 2. 关键分解：局部信息存在，但付不起门票

`a_local_abs` 顶部十分位（22,961 事件）的毛/净/成本拆解：

- **毛期望 +0.125 ATR，且逐年为正**（2022 +0.25、2023 +0.10、2024 +0.11、2025 +0.05）；底部十分位毛 −0.07——局部形态特征确实能把"好交叉"挑出来，十分位完美单调，头尾净差约 0.71 ATR；
- 成本均值 0.299 ATR → 净 −0.175 ATR。**被识别出的局部优势约等于成本墙的一半**；
- 局部毛优势自身也在衰减（2022 +0.25 → 2025 +0.05）。

对照 `ref`：行情特征把顶桶再抬高约 0.26 ATR（−0.175 → +0.083），头部重要性全是市场状态/结构类（`listing_age_log`、`universe_count`、`btc_atr_frac`、`mkt_funding_mean`）——与 P5 归因一致：**唯一能越过成本墙的成分是行情状态**。

## 3. 相对标签的反直觉结果

把标签改为同（UTC 日 × 方向）组内百分位（强制模型只学"这根交叉比同时刻同向的别的交叉好在哪"）后，全特征顶桶从 +0.083 **恶化**到 −0.195。行情中和不是揭示交叉质量信号，而是移除了唯一可变现的成分。"横截面相对化能救 15m 交叉"的假设同时被证伪。

## 3.5 增补 a2：补上本币多日趋势上下文后重测（同日）

主消融后核对特征清单发现真实表达缺口：本币价格类特征最长只看 24 小时，"多日尺度的趋势末端"无表达。按[增补契约](../specs/bin-15m-emax-feature-ablation-a2-addendum-2026-07-29.md)预注册 7 个多日趋势特征（7d/30d 动量、30 天区间位置与高低点距离、上一完整日的日线 EMA21/96 状态），加入 LOCAL 组重跑（[`research_feature_ablation_a2.py`](../scripts/research_feature_ablation_a2.py)、[`feature_ablation_a2_report.json`](../artifacts/feature_ablation/feature_ablation_a2_report.json)）：

- 缺口证实：新特征立即成为模型最重要的两个特征（`d1_gap_atr`、`d1_price_to_slow` 重要性第 1、2 名，`ret_672` 第 4）；
- 结果改善但不改判：顶桶净 −0.175 → **−0.134**（毛 +0.125 → **+0.167**），十分位仍完美单调；四个 OOF 年仍全负（最好 2022 −0.066），Gate B 未过；
- 结论：把用户主张的全部局部信息（形态 + 波动 + 量能 + 多日趋势）给满后，可识别的局部优势上限约 **毛 +0.17 ATR ≈ 成本墙（0.30）的 56%**。特征假设关闭：15m 独立事件策略的死因维持"信息量/成本比"，不是特征表达。

## 3.6 增补：换信号对 EMA30/120 重测（同日）

按[换对契约](../specs/bin-15m-emax-ema-pair-ablation-contract-2026-07-29.md)把信号对换成 `EMA30/120`（唯一自由度），bracket/成本/资格池/打分协议全部不动，重提取开发窗口事件并重跑 local+trend 打分层（[`research_ema_pair_ablation.py`](../scripts/research_ema_pair_ablation.py)、[`ema_pair_report.json`](../artifacts/ema_pair_ablation/ema_pair_report.json)）：

| 口径 | EMA30/120 | EMA21/96 |
|---|---|---|
| pool 事件数 | 218,086 | 292,421 |
| `b4_2` 裸基线 毛 / 净 ATR | +0.040 / −0.376 | +0.041 / −0.379 |
| `b4_2` 持仓中位（根）/ 成本均值 | 14 / 0.415 | 14 / 0.420 |
| 打分顶桶 净 / 毛 ATR | −0.165 / **+0.140** | −0.134 / +0.167 |

- 更慢的对只让事件少了 25%，单事件质量、持仓长度、成本分布与顶桶可识别优势全部原地踏步（顶桶还略差）；重要性榜仍由 a2 多日趋势特征领跑，Gate B 未过（四年顶桶全负）。
- 结论：**"15m 事件信息量/成本比不足"对信号对参数稳健**，换对关闭。慢对不改变 15m 刻度上一次交叉所含的信息量，只是把同样的硬币换了个面额。

## 3.7 增补 F：现有数据新表达（量价分布/90d 动量/VWAP）无增量（同日）

按 [A/F 增补契约](../specs/bin-15m-emax-af-feature-supplement-contract-2026-07-29.md)预注册 5 个 F 族特征（`ret_8640`、`donchian_pos_90d`、`vwap_dist_30d`、`vp_pos_30d`、`vp_hvn_dist_30d`），加入 local+trend 重跑（[`research_feature_ablation_f.py`](../scripts/research_feature_ablation_f.py)、[`f_supplement_report.json`](../artifacts/af_supplement/f_supplement_report.json)）：顶桶净 −0.144 / 毛 +0.158，与 a2（−0.134 / +0.167）噪声带内持平，Gate B 未过。结论：15m K 线自身的信息在 a2 之后已被榨干，量价分布位置与更长动量没有新信息。A 族（OI/多空比）见 3.8 节。

## 3.8 增补 A + 15m 极限终判：持仓数据零增量，四族特征全部给满后上限不动（同日）

- 数据：按 [A/F 增补契约](../specs/bin-15m-emax-af-feature-supplement-contract-2026-07-29.md)范围化同步 Binance Vision USDM daily metrics（571 币 × 上市日 ≤ 2025-12-31，37.9 万文件、约 1 亿行 5m 粒度，仅 1 个文件失败；explore 级，[同步报告](../artifacts/af_supplement/metrics_sync_report.json)），落 `data/normalized/derivatives_metrics/`。`oi_chg_24h` 在 OOF 年 2022–2025 的事件覆盖率 99.4%–100%。
- 结果（[`research_feature_ablation_a.py`](../scripts/research_feature_ablation_a.py)、[`a_supplement_report.json`](../artifacts/af_supplement/a_supplement_report.json)）：local+trend+F+A 顶桶净 **−0.135** / 毛 **+0.168**，与 a2（−0.134 / +0.167）完全重合；四个 OOF 年仍全负，Gate B 未过。
- 关键细节：模型并非没用新特征——`ret_8640`（F）重要性第 1、`oi_chg_3d`（A）第 8——但顶桶期望纹丝不动：新数据源的信息与多日趋势特征**冗余**，不正交。
- **15m 极限终判**：局部形态、多日趋势、量价分布、衍生品持仓四族特征全部给满，可识别毛优势钉死在 ≈ +0.17 ATR，成本墙 0.30–0.42 ATR 不可逾越。特征方向对 15m 关闭；同一特征集在 1h/4h 的移植结果见跨周期标度表（[4h 移植诊断](../../4h-ema-cross-lightgbm-event-selector/diagnostics/bin-4h-emax-local-trend-selector-2026-07-29.md)）。

## 3.9 增补 K：蜡烛形态三尺度（本刻度/日/周）零增量（同日）

按 [K 族契约](../specs/bin-15m-emax-k-candle-supplement-contract-2026-07-29.md)预注册 18 个蜡烛形态特征（信号 K 实体/影线/吞没、上一完整日、上一完整周），加入 local+trend 重跑（[`research_feature_ablation_k.py`](../scripts/research_feature_ablation_k.py)、[`k_supplement_report.json`](../artifacts/k_candle_supplement/k_supplement_report.json)）：顶桶净 −0.141 / 毛 +0.157，与 a2（−0.134 / +0.167）噪声带内持平，Gate B 未过。周线实体/影线进入重要性前 15 但期望不动——周线实体 ≈ 7 天收益、影线 ≈ 区间位置，均已被趋势特征编码。同日 4h 同步验证还观察到轻微稀释（顶桶 +0.367 → +0.287，见 [4h K 族报告](../../4h-ema-cross-lightgbm-event-selector/artifacts/k_candle_supplement/k_supplement_report.json)）。至此五族特征（局部形态、多日趋势、量价新表达、衍生品持仓、蜡烛形态）全部测毕，15m 上限结论不变。

## 4. 结论

1. 用户直觉的毛层面被证实：波动收缩/放量/趋势位置等局部形态可以稳定识别毛期望为正的 15m 交叉（OOF、逐年为正）；
2. 净层面被证伪：+0.13 ATR 的可识别局部优势 < 0.30 ATR 成本，且逐年衰减——15m 独立事件策略的死因不是特征表达，是**信息量/成本比**；
3. 该结果反向支持"触发器化"重构：约 +0.1~0.2 ATR 的入场时点改善在独立 15m bracket 结构里付不起成本，但若作为日线级趋势持仓的入场计时（成本由日线持仓结构承担一次），该量级的改善恰好有意义。任何此类重构按重启规则须以新机制线立项，不继承本线证据。
4. （2026-07-29 终判后补）跨周期移植给出了此结论的正面版本：同一 local+trend 选择器在 1h 顶桶净转正（+0.030）、在 4h 顶桶净 +0.367 且四年全正（Gate B 过 / Gate A 未过）。可识别优势是真实的，能否变现由刻度的成本结构决定；机制线的活路在 4h/1d，见 [1h 移植诊断](../../1h-ema-cross-lightgbm-event-selector/diagnostics/bin-1h-emax-local-trend-selector-2026-07-29.md)与 [4h 移植诊断](../../4h-ema-cross-lightgbm-event-selector/diagnostics/bin-4h-emax-local-trend-selector-2026-07-29.md)。
