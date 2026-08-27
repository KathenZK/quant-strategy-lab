# HYPE-1D-MA7-MLT P0：365 日训练 / 后段验证冻结合同

> 冻结日期：2026-08-27。状态：`explore / diagnostic-only / not promoted / not live-ready`。本合同在读取验证收益、交易、模型预测和候选排名前写入。

## 1. 研究问题与家族边界

回答：在完全相同的数据、成本、固定持有期和下一日开盘执行下，使用训练集拟合的机器学习模型，能否在后续未参与训练/选择的 81 日中，优于“在训练集持续搜索 MA 参数”的规则策略。

- 新家族：`HYPE-1D-MA7-Machine-Learning-Trend`（`HYPE-1D-MA7-MLT`）。
- 不修改、不继承 `HYPE-1D-MA7-Asymmetric-Body-Trend-V7.1`。
- exact V7.1 若列入报告，只能标为已看过验证历史的 descriptive reference，不属于公平 OOS 对照。

## 2. 数据冻结

- 市场：Binance USD-M `HYPEUSDT` perpetual。
- 原始消费层：标准数据湖 trusted `1h` OHLCV；24 根显式闭合小时 K 聚合为 UTC `1d`。
- 完整日 K：`2025-05-31 00:00 UTC` 至 `2026-08-19 00:00 UTC`，共 `446` 日；`2026-08-20 00:00 UTC` 只作 terminal open。
- 训练集：最前 `365` 日，`2025-05-31` 至 `2026-05-30`。
- 锁定验证集：随后 `81` 日，`2026-05-31` 至 `2026-08-19`，最终在 `2026-08-20` open 强制计价/平仓。
- 训练标签必须完整结束在 `2026-05-31 00:00 UTC` 之前；不得让未来持有路径跨入验证集。

## 3. 共同执行与收益合同

- 决策：日 `t` 收盘后；入场：最早 `t+1` UTC open。
- 固定 `1x`、单仓、非加仓；有仓时忽略新信号。
- 候选持有期：`3/7/14` 日；到期在 UTC open 平仓。
- P0 不使用盘中 stop、trailing、OAPP、PEHC、cooldown 或部分仓位；这一简化对 ML 与规则搜索完全相同，但构成 live-ready blocker。
- 每 fill：手续费 `0.001` + adverse slippage `0.0004`；完整往返名义成本 `28 bps`，另按持仓方向结算实际 funding。
- 验证结束仍有持仓时在 terminal open 强平并计退出成本。

## 4. 因果特征

只读取当前闭合日及历史。固定特征组：

- log return：`1/2/3/5/7/14/21d`；
- `SMA3/5/7/10/14/21/30` 的 close gap / `ATR7`；
- `SMA7` 的 `1/3/5d` slope / `ATR7`；
- Wilder `RSI6/14`；
- Wilder `ATR7/14` / close；
- realized volatility `3/7/14/30d`；
- Kaufman `ER7/14`；
- body、range、upper/lower wick / `ATR7` 与 close location；
- volume `1d` log change、`7/30d` z-score；
- 前一完整 UTC 日 funding sum。

缺失采用模型 pipeline 内训练样本中位数；缩放参数只在相应训练折拟合。不得使用未来 exit、MFE/MAE、验证期分布或验证期归一化统计。

## 5. 标签与 ML 候选

对每个特征日、每个 `3/7/14d` 持有期分别计算：下一 UTC open 入场、到期 open 出场、扣双边费用/滑点与实际 funding 后的 long / short 净收益。分别拟合 long 与 short 回归器。

冻结候选：

- Ridge：`alpha ∈ {0.1, 1, 10, 100}`；
- LightGBM 小模型两档：
  - `LGBM_A`：`num_leaves=7, max_depth=3, min_child_samples=30, learning_rate=0.03, n_estimators=120`；
  - `LGBM_B`：`num_leaves=15, max_depth=4, min_child_samples=20, learning_rate=0.03, n_estimators=160`；
- entry edge：预测的最佳方向净收益必须严格大于 `{0, 0.28%, 0.50%, 1.00%}`；否则空仓。

模型只比较 long/short predicted net return，选择较高者；不另搜多空专属阈值。

## 6. 训练内 walk-forward 与唯一候选选择

- 固定四个外层训练内 OOS 块：特征日 index `150–199 / 200–249 / 250–299 / 300–(363-horizon)`；末端减一确保最后一笔标签在 `2026-05-30` open 已完整结束，不读取验证首日 open。
- 每折训练只用该折之前且完整标签未跨入该折的样本，形成 horizon-length embargo。
- 每个 ML 候选拼接四折 OOS 预测，并按共同执行合同逐折从 flat 回测。
- 候选最低要求：四折合计 `>=8` 笔。选择顺序固定为：正收益折数最多 → 四折收益中位数最高 → OOS 总收益最高 → PF 最高 → MDD 绝对值最低 → 候选 id 字典序。
- 即使所有候选都弱，也按上述顺序锁定唯一 diagnostic champion 并只揭示一次验证；训练失败不得事后改候选或阈值。
- champion 锁定后，使用所有标签完整留在训练集内的样本重新拟合 long/short 模型，再生成验证预测。

## 7. “不断搜参数”规则基线

规则只在同一训练内四折 OOS 上选择，执行和 ML 相同：

- `MA window ∈ {5,7,10,14,20,30}`；
- slope lookback `∈ {1,3,5,7}`；
- minimum signed slope / ATR `∈ {0,0.02,0.05,0.10,0.20}`；
- close-to-MA entry gap / ATR `∈ {0,0.10,0.25,0.50}`；
- holding `∈ {3,7,14}`；
- direction `∈ {both,long_only,short_only}`。

共 `4,320` 个参数组合。long 条件为 close 在 MA 上方达到 gap 且 MA slope 达门槛；short 完全镜像。候选最低 `8` 笔，唯一规则 champion 使用与 ML 完全相同的选择顺序。验证期不得重新选参。

## 8. 验证与裁决

一次性报告：ML、train-only rule-search champion、validation buy-and-hold，以及 descriptive exact V7.1（若可精确复现）的总收益、MDD、PF、胜率、交易数、long/short、成本、funding、暴露天数、最近 `1d/7d/1m/3m/6m/1y` 可用切片和完整交易路径。

P0 判断：

- `ML_BEATS_RULE_OOS`：ML 验证净收益更高，且 MDD 不比规则恶化超过 `5pp`；
- `ML_BEATS_V7_1_DESCRIPTIVE`：只作描述，不能清除 V7.1 已看过验证历史的污染；
- `ML_NO_EDGE`：ML 验证净收益 `<=0`、PF `<1`，或少于 `3` 笔；
- 其余为 `MIXED`。

无论结果如何，P0 都保持 `diagnostic-only / not promoted / not live-ready`；不得在该 81 日验证结果上调阈值、换模型、加特征或重选 horizon。继续研究必须只使用未来新增数据或另立全新封存窗口。
