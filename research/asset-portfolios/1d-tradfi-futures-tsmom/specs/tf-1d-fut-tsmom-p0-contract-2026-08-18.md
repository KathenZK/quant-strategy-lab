# TF-1D-FUT-TSMOM P0 冻结契约

> 冻结时间：2026-08-18，跑数前冻结。状态：`explore contract / diagnostic-only / not promoted / not live-ready`。

## 1. 研究问题

固定黄金 `1M/3M/12M` TSMOM 规则扩展到传统股票指数、债券、外汇、商品期货后，能否
依靠跨资产分散取得优于永远做多风险平价的净 Sharpe、回撤和危机期表现。

## 2. 冻结市场

| 类别 | 连续期货代码 |
| --- | --- |
| 股票指数 | `ES=F`, `NQ=F`, `YM=F`, `RTY=F`, `NKD=F` |
| 美国国债 | `ZT=F`, `ZF=F`, `ZN=F`, `ZB=F`, `UB=F` |
| 外汇 | `6A=F`, `6B=F`, `6C=F`, `6E=F`, `6J=F`, `6S=F` |
| 商品 | `GC=F`, `SI=F`, `BZ=F`, `NG=F`, `HG=F`, `ZC=F`, `ZW=F`, `ZS=F` |

四大类各占 raw portfolio `25%`，类内按当月有效市场数等权；禁止按结果删减市场。

## 3. 数据与窗口

- Yahoo Chart API raw quote OHLC，`2020-01-01` 起用于预热；不使用 adjusted close。
- 评估从 `2022-01-03` 开始，结束于数据集最后完整自然月。
- 允许 close 超出同日 high/low 的相对偏差不超过 `0.5%`（供应商连续序列微小换月/舍入）；
  非正价格、重复日期、偏差超过 0.5% 或缺少 12M 预热均 fail closed。
- 数据无逐合约换月表、结算价核验和 roll cost，必须标记 `raw_unaccepted`。

## 4. 信号和时序

- 月末计算 `sign(P_t/P_{t-h}-1)`，`h=1/3/12` 个自然月末。
- Composite 为三个符号等权平均。
- 月末当日仍由旧仓位承担；新目标从下一交易日收益开始生效。
- Long-only risk parity 使用恒定 forecast `+1`，其余风险/成本层完全相同。

## 5. 两层波动率目标

- 资产波动：日简单收益平方先滞后 1 日，再以 `com=60, adjust=False, min_periods=60`
  计算 EWMA，年化 `sqrt(252)`。
- 单市场 subsystem：`forecast × 10% / sigma_i`。
- raw 组合：类别权重 `25%`，类内等权汇总 subsystem 收益。
- 组合层：raw 组合收益以同一滞后 `60-day COM EWMA` 估波动；月末 scalar
  `min(10%/sigma_portfolio, 3.0)`，下一月生效。
- 最终组合总名义杠杆上限 `3.0x`，超出时全市场同比缩小。

## 6. 成本与报告

- `0 bps` 毛对照和单边每单位目标权重变化 `2 bps` 主台账。
- 输出四信号分支 + Long-only risk parity：CAGR、年化收益/波动、Sharpe、Sortino、MDD、
  Calmar、日/月胜率、换手、毛/净收益、平均/峰值杠杆。
- 输出分年、分资产类别贡献、市场贡献、最近 `1d/7d/1m/3m/6m/1y` 审计切片和交互权益图。
- 不做参数搜索、资产删除或事后权重优化；P0 只回答固定规则是否有组合价值。

## 7. 预冻结长期代理验证

主期货表面只有 2022–2026，无法单独判断长期稳定性。跑完主表面后、查看长期代理结果前，
预冻结一个 secondary diagnostic：复用 `XA-1D-CLASSIC-EWMAC` 已冻结的 30 个 Yahoo
ETF/FX 调整价代理和原始 JSON，但只替换成本文 `1M/3M/12M` 月频信号与四类各 25% 规则。
起点机械确定为所有 30 个代理均具备 12M 信号后再预留 3 个月组合波动暖机的下一月首日；
成本为 `0/2/10 bps`。该验证不是期货回测，只用于检验机制是否跨越更长历史，不得与主期货
收益拼接或冒充连续期货证据。
