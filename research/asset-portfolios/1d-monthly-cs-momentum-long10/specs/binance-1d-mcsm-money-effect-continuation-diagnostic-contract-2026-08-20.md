# BIN-1D-MCSM-L10 赚钱效应与领涨延续诊断合同（2026-08-20）

## 研究身份与目标

- Family：`Binance-1D-Monthly-Cross-Sectional-Momentum-Long10`（`BIN-1D-MCSM-L10`）。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；本合同不登记新版本，不授权 runner handoff。
- 目标：解释原始 `ADV>=1000万 USDT`、上一完整月 Top10 的收益究竟来自 Binance 全市场赚钱效应、领涨资产延续，还是单纯高 beta；主目标是保留右尾利润和相对市场超额，不以压低 MDD 为优化目标。
- 前序 BTC SMA gate、MH136 和 target12 只作为负对照；本轮禁止扫描 SMA、波动目标、Top N、形成期、buffer、止损或阈值。
- 原日级引擎绩效已经标记 `PERFORMANCE_INVALIDATED`。本轮新建月度 `00:15 UTC` 点到点标签研究 alpha 结构；任何不可成交退出月份单独标记无效，结果仍不替代完整执行修复。

## 冻结信号、宇宙与标签

1. 信号仍为上一完整日历月端点收益，按降序选择 Top10；不跳过最近月。
2. 宇宙固定为信号日点时 `30d ADV>=1000万 USDT`、稳定币/指数排除、形成月覆盖 `>=80%`、端点 bars 合格的 Binance USD-M USDT 永续。
3. 新月 `00:15 UTC` bar 必须 `open>0`、`volume>0`、`trade_count>0` 且已闭合；不可成交名字按形成收益顺延，不足 10 个则该月无效。
4. 月度价格标签从本月 `00:15` open 到下月 `00:15` open；Top10 任一退出无效则该 Top10 月度标签无效，不把缺失当作 0。
5. 市场基准为同月 entry-valid 合资格宇宙中 exit-valid 名字的等权收益，并报告 exit coverage；这只用于 alpha 结构诊断，不能消除未来缺失导致的 benchmark coverage 限制。
6. Top10 净标签另扣完整进出手续费 `0.001/边` 与滑点 `0.0004/边`；资金费仅在该月 Top10 持有日覆盖完整时计入净标签，否则净标签无效但价格/超额标签仍保留。

## 冻结赚钱效应特征

所有特征只使用信号日及以前数据：

- `breadth_positive_1m`：合资格宇宙中 1M 形成收益 `>0` 的比例。
- `market_median_1m`：合资格宇宙 1M 收益中位数。
- `liquidity_participation`：最近 30 日 quote volume 大于此前 30 日的合资格资产比例；两段各至少 24 个有效日。
- `leader_spread_1m`：Top10 平均 1M 收益减去合资格宇宙中位数。
- `leader_3m_rank_pct`：本月 Top10 在合资格宇宙 3M 收益百分位的平均值。
- `rank_alignment_1m_3m`：合资格宇宙 1M 与 3M 收益的 Spearman rank correlation。
- 拥挤仅作解释：Top10 相对宇宙的过去 30 日 funding 差、实现波动率比；不得用其事后选择状态。

## 冻结因果 2×2 状态

每项“高/低”只与该特征此前 12 个可用月的 expanding median 比较，当前月不进入阈值；不足 12 个历史月时状态为 warmup，不参与 2×2 策略评价。

- `money_effect_strong`：以下三项至少两项成立：`breadth_positive_1m` 高、`market_median_1m>0`、`liquidity_participation` 高。
- `leader_continuation_strong`：以下三项至少两项成立：`leader_spread_1m` 高、`leader_3m_rank_pct` 高、`rank_alignment_1m_3m` 高。
- 四个冻结状态：`strong/strong`、`strong/weak`、`weak/strong`、`weak/weak`。
- 唯一状态候选读取：只在 `strong/strong` 月份持有原 Top10 100% gross，其余月份现金。该读取用于检验状态是否抓住右尾，不因结果改为 0.5x、OR gate 或重新组合指标。

## 延续衰减与收益分解

- 对每月 Top10 从 `00:15` entry 计算 `1d/3d/7d/14d/next-month` 价格收益与相对同期合资格市场超额；任一 Top10 端点无效则对应 horizon 标签无效。
- 报告 Top10、市场等权、Top10 excess 的月度均值、中位数、胜率、t 值和 bootstrap 均值区间。
- 报告各状态的 Top10 绝对收益、市场收益、选币超额、正收益月份占比、相对市场胜率、正 PnL 捕获率和右尾捕获率。
- 右尾固定定义为全部有效 Top10 月度净收益的最高 10% 月份；不得调整分位数。
- 资金费、手续费、滑点与价格贡献分开；不得把市场 beta 当作选币 alpha。

## 事前参考线

`strong/strong` 只有同时满足以下条件，才可作为后续 successor 机制的候选观察：

1. 其 Top10 下一月平均超额高于全状态平均超额，且相对市场胜率 `>=55%`。
2. 只交易 `strong/strong` 时保留原基准至少 `80%` 的正月净 PnL，并捕获至少 `80%` 的固定右尾净 PnL。
3. 非 warmup 完整 12m cohort 中，状态候选相对现金的净收益多数为正；不得只靠一个牛市 episode。
4. `1d→3d→7d→14d→1m` 衰减能解释延续发生在哪里；若超额只来自首日 gap 或少数不可成交月份，则机制失败。
5. 所有状态分类、阈值和标签可逐月复现，无同 bar 或未来数据。

任一收益保留参考线失败，则结论为“当前状态定义不能代表赚钱效应”，而不是继续搜索组合。即使全部通过，本轮仍只是已揭示历史上的 diagnostic；正式 successor 必须另行冻结并取得新的 prospective evidence。

## 固定输出

- `summary.json`：合同、数据、状态、参考线与裁决。
- `monthly-state-labels.csv`：逐月特征、因果阈值、状态、Top10/市场/超额、成本、资金费覆盖和可成交性。
- `feature-conditionals.csv`：每个冻结特征 causal high/low 的未来收益诊断。
- `state-2x2.csv`：四状态及 `strong/strong-only` 捕获指标。
- `continuation-decay.csv`：`1d/3d/7d/14d/1m` 绝对与超额衰减。
- `cohorts-12m.csv`、`bootstrap.csv`、`top10-holdings.csv` 与 `blockers.csv`。
