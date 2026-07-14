# BTC-1H-Adaptive-Regime-V4 结构优化顺序验证 - 2026-07-13

## 结论

按 2026-07-10 结构优化研究建议的顺序，完成：

1. `VWAP revert short-only` 相对 V4 的边际搜索；
2. `wick reject transition-only` 相对 V4 的边际搜索；
3. `MACD flip` 替换 Keltner；
4. 只有新增腿通过时才进入显式三态 regime router。

结果：

- VWAP short-only：`2,500` 组，严格增量 gate 命中 `0`；
- wick transition-only：`2,500` 组，严格增量 gate 命中 `0`；
- MACD replace-Keltner：`2,000` 组，严格增量 gate 命中 `0`；
- 三态 router：因没有通过 gate 的新增腿，按预先冻结协议跳过。

没有产生可登记 V5 的观察。V4 状态保持：

`registered / not promoted / not live-ready`。

这次结果不是“搜索空间还不够大”，而是三个优先方向分别暴露出明确失败原因：

- VWAP：组合层能抬 prefit，但候选腿自身 train/prefit 为负，且显著拉低组合胜率；
- wick：好看提升主要来自 1–3 笔交易，独立样本不足；
- MACD：2,000 组中没有任何一组相对 V4 的 prefit 边际收益为正。

因此不应通过放宽门槛、提高杠杆或读取 reused holdout 回调参数来强行制造 V5。

## 数据、成本与防泄漏

- 市场：Binance USD-M Futures `BTCUSDT` perpetual。
- 周期：`1h`。
- 数据：`17,520` 根闭合 K，UTC `2024-07-02T10:00:00Z` 至 `2026-07-02T09:00:00Z`。
- 数据质量：missing=`0`，duplicate=`0`；资金费 `2,190` 行。
- 成本：fee `0.001`/fill、slippage `4 bps`/fill、历史资金费。
- 执行：闭合 K 信号，下一根 open 入场；stop-first；单仓、不加仓。
- 选参只读取 train / validation / prefit。
- reused holdout 只在各阶段 winner 冻结后展示，不参与选择。

## 统一实验合同

### 加法腿

- V4 冻结交易拥有绝对优先级；
- 候选腿只能填充 V4 空仓时段；
- 候选统一 `fixed 1x`，禁止靠杠杆过 gate；
- entry delay 固定 `1`；
- fixed TP/SL；
- 不启用资金费、方向 ROC 等 V4 已证明空转的过滤器。

### MACD 替换

- 移除 Keltner，保留 V4 CCI；
- MACD 固定 `2.4x`，与 V4 Keltner 曝光一致；
- 组合仍按 prefit leg score 冲突排序；
- 不改变其他执行合同。

### 严格 gate

- 候选 prefit trades `>=25`；
- 候选 validation trades `>=10`；
- 候选 train / validation 同正；
- 组合 prefit 边际收益 `>0`；
- 组合 validation 边际收益 `>=0`；
- prefit DD 相对 V4 不恶化超过 `2pp`；
- prefit 胜率相对 V4 不下降超过 `3pp`；
- 与 V4 ±3h entry overlap `<40%`；
- 加法腿新增 prefit trades `>=8`。

## 阶段一：VWAP revert short-only

### 搜索空间

- 样本：`2,500`；
- `side_mode=short`；
- VWAP window：`24/48/96/168`；
- deviation threshold：`0.5–2.0 ATR`；
- `max_adx=24–45`；
- RVOL、ATR 下限、EMA 距离、TP/SL、最长持仓做受约束随机搜索；
- `fixed_leverage=1.0`。

### Gate 拆解

| 条件 | 通过组数 / 2500 |
| --- | ---: |
| 候选样本数足够 | `1,942` |
| 候选 train / validation 同正 | `23` |
| 组合 prefit 边际为正 | `113` |
| 组合 validation 边际非负 | `753` |
| DD 恶化不超过 2pp | `1,428` |
| 胜率下降不超过 3pp | `26` |
| 重叠低于 40% | `2,500` |
| 新增 prefit 交易至少 8 笔 | `2,449` |
| **全部同时满足** | **`0`** |

### 高分 winner（未过门）

参数摘要：

- `indicator_window=24`
- `band_k=2.0`
- `side_mode=short`
- `max_adx=40`
- `min_rvol=0.6`
- `min_atr_bps=75`
- `tp_atr=2.0`
- `sl_atr=2.5`
- `max_hold_bars=120`
- `fixed_leverage=1.0`

组合表现：

| Window | Annual | Return | DD | Win | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | `5.71x` | `+530.66%` | `-13.84%` | `66.67%` | `75` |
| validation | `7.53x` | `+215.50%` | `-11.59%` | `85.71%` | `49` |
| prefit | `6.29x` | `+1889.70%` | `-13.84%` | `74.19%` | `124` |
| reused holdout | `1.61x` | `+12.55%` | `-18.70%` | `64.71%` | `17` |
| current full | `5.25x` | `+2139.35%` | `-18.70%` | `73.05%` | `141` |

相对 V4：

- prefit 总收益 `+67.55pp`；
- validation 总收益 `+83.12pp`；
- prefit DD 恶化 `0.98pp`；
- prefit 胜率下降 `13.11pp`。

更关键的是候选 VWAP 腿自身：

- train `-32.76%`；
- validation `+15.14%`；
- prefit `-22.58%`；
- prefit DD `-37.69%`。

结论：组合提升来自交易时序与复利排列，不是稳定的独立 VWAP edge；拒绝。

## 阶段二：wick reject transition-only

### 搜索空间

- 样本：`2,500`；
- `side_mode=both`；
- wick threshold：`0.5–2.0 ATR`；
- close position：`0.15–0.35 / 0.65–0.85`；
- ADX transition band：下限 `24–38`、上限 `40–50`；
- `fixed_leverage=1.0`；
- 短持仓 fixed bracket。

### Gate 拆解

| 条件 | 通过组数 / 2500 |
| --- | ---: |
| 候选样本数足够 | `893` |
| 候选 train / validation 同正 | `38` |
| 组合 prefit 边际为正 | `139` |
| 组合 validation 边际非负 | `436` |
| DD 恶化不超过 2pp | `2,137` |
| 胜率下降不超过 3pp | `663` |
| 重叠低于 40% | `2,326` |
| 新增 prefit 交易至少 8 笔 | `1,545` |
| **全部同时满足** | **`0`** |

### 高分 winner（未过门）

参数摘要：

- `band_k=2.0`
- `threshold_low/high=0.25/0.70`
- `ADX=32–45`
- `min_atr_bps=100`
- `tp_atr/sl_atr=2.0/2.0`
- `max_hold_bars=72`
- `fixed_leverage=1.0`

组合表现：

- prefit `6.45x / +1974.84% / -12.87% / 87.69% / 65`；
- reused holdout 与 V4 完全相同；
- current full `5.49x / +2334.57% / -17.47% / 86.84% / 76`。

但候选 wick 腿自身：

- train `2` 笔；
- validation `1` 笔；
- prefit 合计 `3` 笔；
- V4 组合实际新增 prefit 交易仅 `2` 笔。

结论：收益由极少数交易决定，无法证明可重复 edge；拒绝。不能为了保留 winner 把最低交易数从 `25/10` 降到 `3/1`。

## 阶段三：MACD flip 替换 Keltner

### 搜索空间

- 样本：`2,000`；
- MACD：`8/21/5`、`12/26/9`、`21/55/9`、`34/89/13`；
- ADX、RVOL、ATR、HTF、TP/SL、最长持仓做受约束搜索；
- `side_mode=both`；
- `fixed_leverage=2.4`，与 V4 Keltner 相同。

### Gate 拆解

| 条件 | 通过组数 / 2000 |
| --- | ---: |
| 候选样本数足够 | `1,267` |
| 候选 train / validation 同正 | `77` |
| **组合 prefit 边际为正** | **`0`** |
| 组合 validation 边际非负 | `2` |
| DD 恶化不超过 2pp | `206` |
| 胜率下降不超过 3pp | `0` |
| 重叠低于 40% | `1,934` |
| **全部同时满足** | **`0`** |

高分 winner：

- MACD `8/21/5`
- `ADX >=40`
- `htf_mode=h4`
- `tp_atr/sl_atr=2.5/4.0`
- `max_hold_bars=72`
- `fixed_leverage=2.4`

组合表现：

- prefit `4.99x / +1265.95% / -22.18% / 71.64% / 67`；
- reused holdout `2.52x / +25.93% / -17.47% / 75.00% / 8`；
- current full `4.56x / +1620.17% / -22.18% / 72.00% / 75`。

相对 V4：

- prefit 总收益减少 `556.20pp`；
- prefit DD 恶化 `9.31pp`；
- prefit 胜率下降 `15.66pp`。

结论：MACD 在后段有一定互补，但无法替代 Keltner 的 prefit 主贡献；拒绝。

## 阶段四：三态 regime router

预先协议规定：只有 VWAP 或 wick 至少一条腿通过严格增量 gate，才允许进入 router，以免用路由参数掩盖没有独立 edge 的腿。

本轮两条加法腿 gate 命中均为 `0`，因此：

- router 状态：`skipped_no_passing_add_leg`；
- evaluated：`0`；
- gate passes：`0`。

这不是未完成，而是按停止条件正常终止。

## 最终决策

### 已否决

- 继续调 V4 的 19 参数；
- 现有引擎内 `VWAP short-only` 直接加法；
- `wick transition-only` 直接加法；
- `MACD flip` 替换 Keltner；
- 在无有效新增腿的情况下实现三态 router；
- 放宽交易数、胜率或独立正收益门槛保留 winner。

### 后续可选方向

当前 16 类 style 的前三优先方向已经按冻结协议失败。若继续研究收益提升，应转向**现有 OHLCV 指标 style 之外的新信息源或新机制**，例如：

- funding / basis 的独立拥挤反转机制，而不是资金费上限过滤器；
- 更细粒度真实成交或订单流构建的 1h 聚合特征；
- 跨时间尺度 realized-vol / volatility-of-volatility 状态；
- BTC 与其他高流动性资产的已闭合 lead-lag 特征；
- 先等待 untouched forward，验证 V4 是否仍有实际 edge。

这些方向都需要新的数据质量审计和独立 research family/机制设计，不应继续扩充当前 V4 参数表。

## 证据

- `artifacts/btc_1h_ar_v4_structural_trials_2026-07-13.json`
- `artifacts/btc_1h_ar_v4_structural_trials_rows_2026-07-13.csv`
- `notes/btc-1h-ar-v4-structural-optimization-study-2026-07-10.md`

复现：

```bash
uv run research/btc/1h-adaptive-regime/scripts/research_btc_1h_ar_v4_structural_trials.py
```
