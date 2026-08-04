# BIN-MTF-PTC Continuation Meter V0 Contract（2026-08-03）

## 1. 目的

在任何完整交易回测前，独立验证“价格冲量后未来路径是否可排序”。本批次只运行 development/validation，不读取 locked historical evaluation 绩效。

## 2. 事件与方向

- 基础 bar：完整 1h；每 4h 观察一次，避免逐小时高度重复。
- onset horizons：4h、12h、24h。
- direction：对应 horizon close-to-close log return 的符号。
- candidate floor：scaled move `>=0.5`，用于保留足够样本；threshold 不在本批次选择为交易规则。
- 过去 RMS：720h，向前 shift onset horizon，避免把当前冲量写进尺度。

## 3. Causal features

- scaled directional displacement；
- path efficiency；
- jump concentration；
- regression path R²；
- half-window acceleration；
- short/long true-range expansion；
- directional RSI(14) position。

全部特征只使用观察时点及以前数据。V0 不使用 volume/OI/funding，不做 tree model。

## 4. Future-path labels

R 使用观察前 hourly RMS 的 24h 尺度。对 24h/72h/168h 三个未来 horizon：

- success：顺方向先触及 `+1.0R`；
- failure：先触及 `-0.5R`；
- 同一小时两端都触及：保守记 failure；
- horizon 内两端都未触及：unresolved，不进入二分类拟合，但单独报告比例。

Label 只存在 y；不允许进入 X。

## 5. 模型与验证

- 每资产、每 onset、每 label horizon 独立固定 `StandardScaler + LogisticRegression(C=1, L2)`；
- development 拟合，validation 一次评估；
- dev observations 在边界前 purge 14d；validation labels 必须在 validation end 前完整；
- 输出 AUC、Brier、base rate、quintile continuation rate、top-bottom spread、quintile Spearman 和样本数。

本批次不挑“最好模型”进入策略。最低可继续研究信号：多个相邻 horizon AUC >0.53、top-bottom spread >5pct、quintile 方向基本单调，且不是单一资产/方向造成。失败则先修标签/机制，不增加技术指标救结果。

