# BIN-1D-MCSM-L10 可实盘化候选冻结合同（2026-08-20）

## 研究身份与边界

- Family：`Binance-1D-Monthly-Cross-Sectional-Momentum-Long10`（`BIN-1D-MCSM-L10`）。
- 当前状态：`explore / not promoted / not live-ready`；本合同冻结的是 promotion 前候选，不登记版本、不授权 handoff、dry-run 或 live。
- 目标：保留已显示历史右尾收益的 `1M Top10` 横截面信号，只增加一个少自由度、closed-bar 可执行的账户级风险层，检验是否能把共同市场回撤压到可运行区间。
- 已知污染：`2020-03-01`–`2026-06-30` 的 baseline、target20、正收益限定和宽度结果已揭示；因此本轮后段只能称 `locked historical holdout / exposed-regime`，不是 clean OOS。

## 继承口径

- 数据、点时上市资格、稳定币排除、月度形成、月初开盘、实际资金费、手续费 `0.001/边`、滑点 `0.0004/边`继承 [Long10 诊断合同](binance-1d-mcsm-long10-diagnostic-contract-2026-08-18.md)。
- 主要宇宙固定为截至上月末 `30d ADV >= 1000万 USDT`；`all_listed` 仅作跨宇宙控制，不用于挑选参数。
- 每月按上一完整日历月收益选择 Top10；每个名字未缩放目标权重 `10%`；不做空。
- BTC 市场状态使用同一 Binance USD-M panel 中的 `BTC` 日收盘，不引入外部现货代理。

## 冻结主候选 `ADV10M_TOP10_TV15_BTC200`

1. **风险许可**：每月换仓前一日 UTC 收盘 `BTC close >= BTC SMA200` 才允许建仓；`SMA200` 只含截至该闭合日的 200 个有效日收盘。暖机不足时现金。
2. **组合风险缩放**：沿用已审计的组合价格收益估计，`90d` trailing realized volatility、至少 `60d`，再保守滞后一日；当月 scale=`clip(0.15 / trailing_vol, 0, 1)`，不允许杠杆。
3. **月中风险退出**：持仓后若任一 UTC 日闭合时 `BTC close < BTC SMA200`，下一 UTC 日开盘把所有腿平到现金；当月不重新进入，最早在下月月初重新按完整规则判断。
4. **缺数 fail-closed**：BTC close/SMA、换仓开盘或风险缩放输入缺失时不新增风险；持仓期 BTC 风险状态不可判定时，下一可交易开盘退出并记录数据事件。
5. **期末处理**：样本末收盘强制平仓并计一边手续费和滑点；现金收益固定为 0。

## 事前对照、消融与稳定性

- 对照：原始 Top10、Top10 target20、同起点 Top10 target15、`BTC SMA200` gate-only，以及 full candidate。
- 消融：删除 target15、删除月初 BTC gate、删除月中退出，必须验证权重/成交路径确实变化。
- 参数邻域只作 `mc4`：`SMA150/200/250` 与 `target vol 12%/15%/18%`；不得从扰动矩阵另选 winner 或登记新版本。
- 时间证据：开发段 `2020-08-01`–`2023-12-31`；一次性后段 `2024-01-01`–`2026-06-30`。后段是规则冻结后的历史揭示，但因 regime 已知只记为 exposed-regime holdout。
- 低频结构化 OOS：按连续 `12m` cohort 报告净收益、Sharpe、MDD、有效换仓与正收益占比；recent slices 只作附录。

## 压力、容量与实盘门禁

- 成本压力：基础成本、费用和滑点各 `1.5x`、`2x`；执行延迟压力为所有目标换仓延迟一个 UTC 日开盘，旧仓在延迟前继续持有。
- MC：以月度组合 cohort 为单位 bootstrap，固定种子，至少 `5000` 条与原样本等长路径，报告终值、Sharpe 与 MDD 的中位及 `5%/10%/90%/95%` 分位。
- 容量：按换仓前已知 `30d ADV` 和每笔目标权重变化，报告 `0.5%/1%/2% ADV` 参与率下的 AUM 上限分布；这不是实际下单授权。
- 本轮主候选同时满足以下事前参考线才可进入正式 promotion review：全段净 Sharpe `>=0.8`、MDD `>=-25%`、CAGR `>=10%`；后段净收益 `>0`、MDD `>=-20%`；至少 `60%` 的 12m cohort 为正；`2x` 成本仍为正；邻域不得大面积转负；all-listed control 方向一致；无杠杆、无非正权益、无不可解释裸仓。
- 即使参考线全过，本轮也不能直接标记 `live spec`：仍需正式 Gate 0–4、runner parity、拒单/断流/重启状态机和新的 prospective evidence。任一主参考线失败则保持 `explore / not promoted / not live-ready`。

## 固定输出

- 主指标、逐年、最近 `1d/7d/1m/3m/6m/1y`、12m cohort、开发/后段、成本与延迟压力、消融、参数扰动、monthly bootstrap、PnL attribution、月度持仓/风险状态、日路径和容量表。
- Durable artifacts 位于 `../artifacts/`，复现脚本位于 `../scripts/`，中文结论位于 `../diagnostics/`。
