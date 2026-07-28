# BIN-4H-EMAX V2 打分层契约（2026-07-24）

> 状态：`registered`（研究契约）。在查看任何训练/回测结果**之前**冻结；评估规则与过滤阈值全部预注册，禁止事后调参重跑再引用。核心问题：**LightGBM 能否识别 4h 死叉的质量**，并以此把 P2 对照组 A 的回撤压进判据（<40%）同时保住 2024/2025 山寨空头利润。

## 1. 数据

- 输入：[`v2_dataset_short.parquet`](../artifacts/v2_dataset_short.parquet)——修正后开发窗（2020–2025）全部可交易资格死叉空头事件 11,695 个（池内 7,969），57 个特征，标签 `b4_2`（0=先止损 57.2% / 1=先止盈 34.0% / 2=超时 8.8%）。
- 特征：复用 15m 家族特征模块（bar 数窗口随周期缩放，与信号/标签同尺度；全部相对化、无币种身份、只用信号 bar 收盘前信息；方向敏感特征按空头翻转）。注意两点 4h 语义：`atr_pos_30d`/`qv_rel_30d` 的 2880 bar 窗在 4h ≈ 480 天（长视界特征，年轻币 NaN ~22%，LightGBM 原生处理）；新增 `btc_dist_ema96_1d`（A2 门控变量的连续版）与 `cross_count_same_ts`/`cross_count_24h`（聚簇特征，P2 显示回撤主因是聚簇）。

## 2. 模型与验证

- 模型：LightGBM 三分类（multiclass logloss），保守参数：`num_leaves=31, max_depth=6, min_child_samples=200, learning_rate=0.03, n_estimators=2000, subsample=0.8, colsample_bytree=0.7, reg_alpha=1, reg_lambda=5`；早停用训练集时间尾部 10%（不碰验证年）。
- CV：扩窗逐年 purged 时序 CV。验证年 Y ∈ {2021…2025}；训练集 = `entry_ts ≤ Y-01-01 − 16 天`（96 根 4h 标签窗完整闭合于验证年之前）。训练用全部资格事件，评估只看池内事件。
- 权重：`1 / cross_count_same_ts`，裁剪到 `[0.05, 1]`（同 bar 聚簇降权）；不做币种平衡（特征无币种身份、样本小）。
- 打分：`score = p_tp·m_tp + p_sl·m_sl + p_to·m_to`，其中 `m_*` 为**训练折**内各标签类的 `b4_2_net_atr` 条件均值。不做等渗校准（样本量不足，预注册为已知限制）；score 仅用于排序与过零判断。

## 3. 预注册评估（全部 out-of-fold）

1. **十分位单调性**（机制验证）：池内 OOF score 十分位 vs 实现净 ATR；要求全期十分位秩相关为正、顶层十分位 > 底层十分位、且 5 个验证年中 ≥3 年方向一致。
2. **过滤规则**：唯一预注册阈值 `score > 0`（期望净收益为正才交易），无任何搜索；报告保留比例与净均值提升。
3. **组合叠加**：P2 契约 A1 同框架（同资金/并发/成本规则），入场限 OOF `score > 0` 的池内事件，窗口 2021–2025（2020 无 OOF 分）；对照组为同窗口重跑的 A1。判据沿用 P2：最大回撤 <40%、2022 利润占比 <70%、全期为正；另要求 2024+2025 合计利润不低于同窗 A1 对应值的一半（保住山寨熊利润）。
4. `2026H1` 仍为污染窗，不参与任何环节。

## 4. 产物

[`v2_oof_scores.parquet`](../artifacts/v2_oof_scores.parquet)、[`v2_training_report.json`](../artifacts/v2_training_report.json)、[`v2_portfolio_report.json`](../artifacts/v2_portfolio_report.json)、曲线图；脚本 [`train_v2_scoring.py`](../scripts/train_v2_scoring.py)、[`backtest_portfolio_v2.py`](../scripts/backtest_portfolio_v2.py)。
