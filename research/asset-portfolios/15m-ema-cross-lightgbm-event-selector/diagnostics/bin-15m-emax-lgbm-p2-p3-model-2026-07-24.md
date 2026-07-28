# BIN-15M-EMAX-LGBM P2 数据集与 P3 模型验证（2026-07-24）

口径：Binance USD-M `15m`，开发窗事件 426,815 个（多空各 ~21.3 万），bracket `TP4/SL2`（P1 预注册选定），成本=手续费 `0.001`+滑点 `4bps`/次成交+as-of funding。完整数字见 [training_report.json](../artifacts/model_v1/training_report.json)、[event_dataset_dev.manifest.json](../artifacts/event_dataset_dev.manifest.json)。

## P2 数据集

- 60 个特征，八组（交叉几何/趋势动量/波动率/成交量/funding/BTC 与横截面/币种结构/时间），全部相对化、只用信号 K 收盘已知数据、不含 symbol 名；方向敏感特征按 side 对齐（对齐不变量抽查 100% 成立）。
- 无高缺失特征（>20% 的为零）；taker 特征在 7 个遗留币的历史行为 NaN（占事件 1.4%），显式缺失不填充。
- 权重 = 逐币均衡 × 同小时同向聚簇 `1/N`；训练时对极端权重按 50× 中位数截断。
- 工件：[event_dataset_dev.parquet](../artifacts/event_dataset_dev.parquet)（manifest 含特征清单与 SHA256）。

## P3 训练与验证

- 两套 `LGBMClassifier` 三分类（保守超参 + early stopping + 逐类 isotonic 校准），walk-forward 扩窗 5 折、2 天 embargo、同事件同折。
- 打分 = `P(TP)×4 − P(SL)×2 + P(timeout)×r̂_timeout − 该事件成本(ATR)`，即校准后的期望净 ATR。
- 排序能力：全部 10 个折×方向组合中交易池 top decile 均优于全体（lift 恒正）；但多头侧 top decile 净期望在 5 折中 3 折为负，空头侧 4/5 折为正——decile 粒度的高分组不足以稳定为正。
- 绝对阈值分层（交易池 OOF 合并）：`score>0` n=37,266 均值 `−0.017`；`>0.25` n=16,547 `+0.066`（4/5 折正）；`>0.5` n=9,259 `+0.115`；**`>0.75` n=3,996 `+0.251`（5/5 折正）**；`>1.0` n=622 `+0.375`（5/5 折正）。阈值-收益单调，模型确实分离出小的正期望子集。
- 留币批测（辅助诊断非门禁）：SOL/AVAX/SUI 两侧与 DOGE 空头侧 top quintile 均为正（如 SOL 空头 `+0.557`）；DOGE 多头负；**HYPE 零样本失败**（126 个事件，top quintile 两侧均负）——对"迁移到 HYPE"这一原始动机是明确的负信号。
- P3 gate 判定：以组合层实际交易口径（绝对阈值高分组）读为**通过**；以 decile 口径读多头侧不达标。两种读法都记录在案，最终裁决交给 P4/P5 组合级结果。

## 风险注记

- 高分事件密度逐折下降（fold5/2025 显著低于早期折），与 FML 的校准漂移死法方向相同；若 2026 继续收缩，锁定 OOS 可能因交易数 <60 触发硬门槛失败。
- score 与 net 同减 `cost_atr`，rank IC（0.2–0.5）含机械成分，不作为证据引用；只看阈值子集的已实现净期望。
