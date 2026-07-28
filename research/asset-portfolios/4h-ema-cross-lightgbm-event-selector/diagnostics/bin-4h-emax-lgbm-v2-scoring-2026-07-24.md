# BIN-4H-EMAX-LGBM V2 打分层验证：机制判据未过（2026-07-24）

- 家族：`Binance-4H-EMA-Cross-LightGBM-Event-Selector`（`BIN-4H-EMAX-LGBM`）
- 契约：[`bin-4h-emax-v2-scoring-contract-2026-07-24.md`](../specs/bin-4h-emax-v2-scoring-contract-2026-07-24.md)（评估规则与唯一阈值 `score > 0` 在训练前预注册）
- 口径：修正后开发窗（2020–2025）资格死叉空头 11,695 事件、57 个信号时刻特征、`b4_2` 三分类标签；扩窗逐年 purged 时序 CV（验证年 2021–2025，purge 16 天）；评估只看池内 OOF。成本（0.001/边 + 4 bps/边 + funding）已含于标签。
- 证据：[`v2_training_report.json`](../artifacts/v2_training_report.json)、[`v2_oof_scores.parquet`](../artifacts/v2_oof_scores.parquet)、[`v2_portfolio_report.json`](../artifacts/v2_portfolio_report.json)、脚本 [`build_v2_dataset.py`](../scripts/build_v2_dataset.py)、[`train_v2_scoring.py`](../scripts/train_v2_scoring.py)、[`backtest_portfolio_v2.py`](../scripts/backtest_portfolio_v2.py)

## 1. 判据一：十分位单调性 —— 未过

OOF 分数与实现净 ATR 的秩相关：**全期 −0.136**（要求为正）；逐年 2021 NaN（退化折）、2022 −0.069、2023 −0.062、2024 −0.128、2025 +0.104——可用四年中仅一年为正（要求 ≥3/5）。十分位表无单调结构，顶层十分位（d8）净 −0.049 反而最差。

## 2. 判据二：`score > 0` 过滤 —— 提升微弱

保留 61.6% 事件，净均值 +0.248 → +0.285（≈0.04 ATR），在净 ATR 标准差 2.8 的量级下无意义。

## 3. 判据三：组合叠加 —— 回撤仍未达标，表面提升是伪影

| | A1 同窗（2021–2025） | V2 `score>0` |
| --- | ---: | ---: |
| 全期收益 | +547% | +646% |
| 最大回撤 | −54.3% | **−49.1%**（仍 ≥40% 红线） |
| 2021 | −35.7% | **零交易** |

V2 的 2021 零交易不是模型识别了牛市，而是该折训练集只有 255 个事件（min_child_samples=200 下模型退化为一棵桩、分数恒 ≤0）——碰巧躲过最差年份的伪影。剔除该伪影后 V2 与 A1 的逐年形态基本一致。

## 4. 失败归因：又是行情状态记忆，不是交叉质量识别

- **训练集内秩相关 +0.62 vs OOF −0.14**：模型完全有能力"解释"历史，但排序能力不能跨年迁移。
- 增益 Top10 特征几乎全是行情状态量（`universe_count`、`btc_dist_ema96_1d`、`atr_frac_sig`、`btc_atr_frac`、`csd_96`、`atr_pos_30d`、`btc_rv_ratio`、`btc_gap_atr`、`btc_ret_96`、`breadth_above_slow`），交叉几何特征（斜率、纠缠度、间隔）基本未被使用——模型学的是"现在是什么行情"，而各年行情与空头收益的映射关系逐年改变（2022 高波动=好做空，2023 高波动=震荡磨损），扩窗 CV 下直接反噬。
- 与 15m 家族 P5 尸检结论同构：**EMA 交叉的截面特征里不含可跨期迁移的"质量"信息，模型只能退化为行情检测器**。该结论现已在 15m（锁定 OOS 揭示）与 4h（OOF 逐年）两个周期独立复现。

## 5. 裁决

- V2 打分层三项预注册判据全部未过或无效：**"LightGBM 识别死叉质量"的核心设想在 4h 周期、当前特征集下不成立**。
- 结合 P2（裸信号组合回撤 −54.3%/−40.7% 未过红线）：本家族 4h 死叉空头的原料真实（P1 净 +0.25 ATR）但两种可执行形态（裸做、LightGBM 打分）均未通过预注册门槛。家族维持 `explore / not promoted / not live-ready`，不注册版本。
- 若未来重启，改变的假设必须写明：换质量代理标签（如挤仓风险预测而非 TP/SL 三分类）、换特征域（衍生品持仓/爆仓数据）、或接受"行情检测器"定位并显式做成状态门控而非事件打分。
