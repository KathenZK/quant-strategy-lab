# Binance 日线 MA7 平多即反手空诊断合同

> 冻结时间：2026-08-06（首次运行变体前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

用户观察到 HYPE V1 的做空捕获偏弱：当价格已明显跌破日 K MA7、原多单触发迟滞退出时，继续等待独立 short reclaim 可能错过下跌主体。本合同只检验一个最小机制变化：

**多头因原冻结 `ma7_hysteresis_exit` 退出时，在同一下一日 open 平多并立即反手开空，能否改善 HYPE V1 与 BTC/ETH 共享参数的做空贡献、组合收益和回撤。**

## 冻结变体

- `R0 baseline`：各路线原冻结多空参数与状态机。
- `R1 long-exit-short-reversal`：
  1. 仅当当前持有多单，且原冻结多头规则在日 `t` 收盘产生 `ma7_hysteresis_exit`；
  2. 在 `t+1` open 先平多，再按成交后权益建立约 `1x` 空单；两次成交分别计手续费与滑点；
  3. 该反手跳过原 short entry mode、斜率、确认、buffer 与 long cooldown；
  4. 空单建立后，hard stop、trailing stop、MA7/斜率退出、max-hold 与 cooldown 完全沿用该路线原冻结 short config；
  5. 多头因 protective stop、trailing stop、slope exit、max-hold 或 terminal flatten 退出时不强制反手；
  6. 原独立多头/空头入场仍保留。

`R1` 改变逐笔行为，属于 materially new diagnostic mechanism；无论结果如何都不回写 HYPE V1 或 BTC/ETH 共享参数身份，也不自动登记新版本。

## 路线与冻结参数

1. `HYPE_V1`：[`HYPE-1D-MA7-ABT-V1 规格`](../../../hype/1d-ma7-asymmetric-body-trend/specs/hype-1d-ma7-abt-v1-spec.md)第 `041` 组。
2. `BTC_ETH_shared / BTCUSDT`：2026-08-05 development-only 选出的 BTC/ETH 共享 long/short config。
3. `BTC_ETH_shared / ETHUSDT`：同一组共享 config，不分资产调参。

## 数据、执行与成本

- Binance USD-M perpetual，accepted `1h` raw/normalized 数据聚合完整 UTC 日 K；实际 event-time funding。
- `SMA7`、`ATR7`、closed-bar-only、stop 小时路径与原引擎一致。
- 手续费 `0.001/fill`；基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`。
- 主结果使用原证据共同终点 terminal open `2026-07-30 00:00 UTC`，避免 HYPE 新增观察数据与 BTC/ETH 旧终点不一致；HYPE 另报告最新数据延伸但不参与跨资产横比。
- 相位 `12h` 只作非强制检查项，不作单独否决。

## 预注册输出

- `R0` 与 `R1`：full、development / researcher-exposed holdout（沿各家族原切分）、`8 bps`、额外延迟一天、`0h/12h`。
- 总收益、MDD、Sharpe、交易数、换手和成本。
- 多头/空头交易数、净 PnL、profit factor；R1 强制反手空的笔数、胜率、净 PnL、逐笔明细与退出原因。
- 结论按三档：
  - `改善`：R1 在该资产 base 与 `8 bps` 均提高净收益，MDD不恶化超过 5 个百分点，且强制反手空净 PnL 为正；
  - `混合`：收益或做空贡献改善，但压力/回撤/分期至少一项明显恶化；
  - `失败`：强制反手空净 PnL 非正，或组合收益下降。

任何结果均为已揭示历史上的机制诊断，不是 clean OOS 或 promotion 证据。
