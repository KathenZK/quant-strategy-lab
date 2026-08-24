# BTC-1D-Classic-CTA-Trend 文献基线契约（2026-08-17）

本契约在跑数前冻结。参数全部取自经典 CTA / Carver EWMAC 文献，不对 BTC 历史做任何速度对、scalar、波动目标或缓冲带搜索。

## 研究问题

把「统一 alpha + 自适应风险 + 市场执行」三层经典 CTA 直接套到 Binance `BTCUSDT` 永续日线，能否在不调参的前提下得到正的绝对收益，并相对同成本 1x 买入持有形成超额？

这不是跨 50 个市场的 leave-one-market-out 优化；本仓库没有那份商品/利率/外汇期货池。替代纪律是：alpha 参数来自外部文献，BTC 只作为从未参与调参的应用市场。

## 三层规则

### Alpha（全市场同一套）

- EMA 速度对：`8/32`、`16/64`、`32/128`、`64/256`。
- EMA：`close.ewm(span=N, adjust=False, min_periods=N).mean()`。
- 价格波动：`close.diff()` 的 EWMA 标准差，`span=35`。
- `raw = (EMA_fast - EMA_slow) / price_vol`。
- 文献 scalar：`5.3 / 3.75 / 2.65 / 1.87`；标准 forecast 裁剪到 `[-20, 20]`。
- 组合 forecast：四条等权平均后再裁剪到 `[-20, 20]`；四条均有效才交易，否则空仓。

### Risk（按 BTC 自身 σ 缩放）

- 日收益波动：`pct_change` 的 EWMA 标准差，`span=35`。
- 年化：`σ_ann = σ_daily × √365`。
- 目标仓位：`w = (F / 10) × (0.20 / σ_ann)`，裁剪到 `[-2.0, 2.0]`。
- 主口径使用 `0.10 × (0.20 / σ_ann)` 的 no-trade buffer；精确跟踪只作执行敏感度，不用于挑选参数。

### Execution（BTC 永续个性化）

- 市场：Binance USD-M `BTCUSDT` perpetual。
- 数据：标准数据湖 native UTC `1d` 闭合 K；资金费用 `funding_rates` 全历史 8h 事件。
- 时序：当日收盘计算目标，下一根日 K 开盘调仓；开盘到开盘计收益。
- 成本：每单位换手手续费 `0.001` + adverse slippage `4 bps`；区间内实际 funding 在调仓前按上一持仓结算。
- 无止盈、止损、timeout、最小名义或数量步长模拟。
- 样本末按最后一根开盘 mark，不强制平仓。

## 对照与切片

- 必须报告：精确跟踪、`0.10` 缓冲主口径、四条 sleeve、1x 永续买入持有、多头-only / 空头-only 归因。
- 切片 `1d/7d/1m/3m/6m/1y` 锚定数据末端，只作审计，不参与选择。
- 不在本契约内改速度对、scalar、目标波动或 buffer。

## 防串线

- 不是 [`HYPE-1D-MHEF`](../../../hype/1d-multi-horizon-ema-forecast/README.md)：那里把 forecast `/20` 映射到 `±1x`，没有额外 20% 波动目标。
- 不是已关闭的 [`XA-1D-EWMAC-UT`](../../../asset-portfolios/1d-ewmac-universal-trend/README.md)：那是多资产 close-to-close、`halflife=20` 的通用趋势门禁；本线是 BTC 单资产、次日开盘成交、`span=35`。
- 不是 [`XA-1D-CLASSIC-EWMAC`](../../../asset-portfolios/1d-classic-ewmac-replication/README.md)：传统 ETF/FX 代理复现，明确不含 BTC。

## 状态

跑数后保持 `explore / not promoted / not live-ready`，除非用户另行要求登记版本。本契约不构成 promotion。
