# HYPE 1D MA7 原始趋势状态机前瞻观察协议

> 冻结日期：2026-08-09。状态：`observation protocol / explore / not promoted / not live-ready`。本协议不登记版本、不授权 runner、不承诺 promotion。

## 1. 目的

在不继续使用已揭示历史选择参数的前提下，平行观察[原始趋势状态机合同](hype-1d-ma7-original-trend-state-machine-contract-2026-08-09.md)的 A–D 四臂：

- A：核心 fresh cross + armed `0.75×ATR7` + strict slope；
- B：A + short `3d RSI6<30` 盈利止盈；
- C：A + `3d RSI6>70` 后 fresh down-cross 提前反空；
- D：B + C。

四臂平行记录，不先选择 B/D；E emergency stop 已在 development 中恶化，不纳入 prospective alpha 臂。

## 2. 起点与数据归属

- 冻结前最后数据 cutoff 为 `2026-08-06 07:00 UTC`；此后补到冻结时刻的数据仍是 pre-freeze backfill。
- prospective 从首个冻结后完整 UTC 日 `2026-08-10 00:00–2026-08-11 00:00` flat-start；该 bar 标记为 `2026-08-10 00:00`，最早信号在 `2026-08-11 00:00` close/open 边界形成并于该 UTC open 成交。
- 只有在每个 `1h` bar 闭合、标准数据湖质量检查通过后才能聚合；缺口、重复、未闭合 bar、OHLC/null/funding blocker 均 fail closed。
- 观察期间不得把新增数据回填进 development 参数搜索或改变 `N_cross=1`、`0.75 ATR7`、strict slope、`3/30/70`。

## 3. 冻结实现

- 状态机：[hype_1d_ma7_original_trend_engine.py](../scripts/hype_1d_ma7_original_trend_engine.py)，SHA256 `4e2bcfda0dd693968687f3cff1ca845df892e88d0eb5c82029333e828274f403`。
- 研究器只作历史复现，不是生产观察器：[research_hype_1d_ma7_original_trend.py](../scripts/research_hype_1d_ma7_original_trend.py)，SHA256 `961c9acdd888c2edd3b3cd88818b34dbe02cc15308bd1919f5e789d16a126087`。
- 任何改变逐笔路径的代码修正都必须关闭当前观察段并另起协议；文档或输出格式修正须证明 path-equivalent。

## 4. 记录字段

每个完整日、每臂至少记录：

- 当日 OHLC、MA7、ATR7、RSI6、slope/ATR、relation；
- side、entry price/qty、armed side/age、pending decision；
- signal timestamp、next-open fill、reason、fills、fee/slippage/funding；
- equity、MDD、MFE/MAE、short giveback；
- 数据质量、代码 hash、重启前后状态一致性。

四臂必须使用同一 market snapshot 和共同执行假设。不能只保留表现较好的臂。

## 5. 最低观察门槛与裁决

- 至少 `90` 个自然日且每臂至少 `5` 笔平仓；任一不足均为 `insufficient evidence`。
- B 相对 A 继续要求：short giveback 降低、short 腿不负、组合净收益改善或 MDD 改善至少 `2pp` 且净收益不低于 A 的 `90%`。
- C 必须至少发生 3 次实际 `overbought_fresh_down` 成交才允许方向性讨论；不足只记事件稀缺，不调阈值。
- D 只有在 B、C 各自通过且组合不破坏贡献时才可作为候选。
- 所有观察还需报告 `8 bps` shadow、额外延迟 shadow、rolling 与逐笔路径；观察通过也只允许提出“是否登记”的新请求，不自动登记或 promotion。

## 6. 禁止事项

- 不因观察结果调整 RSI 天数/阈值、slope 门槛、ATR 带或 armed 期限；
- 不删除亏损交易、改起点、改相位、改成本或回填缺失事件后继续沿用同一 OOS 标签；
- 不把 floating PnL 称为已实现收益；
- 不向 quant-runner 交接，不开 dry-run/live，不把本协议当作 runner spec。

当前没有自动观察服务或 runner instance；启动任何持续采集/执行前仍需单独实现、测试并通过 handoff 门禁。
