# Decision Log — Multi-Asset-1D-Classic-EWMAC-Replication

## 2026-08-10 立项并冻结经典 EWMAC 代理复现契约

- 决策：按用户要求新建经典 EWMAC 复现诊断线，资产池限定为趋势跟踪文献的传统四大类（股票指数、债券、商品、外汇），信号使用 Carver EWMAC 四速连续 forecast 与文献 scalar，零逐资产调参。由于仓库没有连续期货总收益数据库，本轮只使用 Yahoo ETF/FX 代理验证文献性质，不声明严格复刻、不登记版本、不进入 promotion。
- 证据：[复现契约](specs/xa-1d-classic-ewmac-replication-contract-2026-08-10.md)

## 2026-08-10 首轮跑数：经典趋势性质在公开代理上部分复现，ETF 压力成本不经济

- 决策：按冻结契约完成 `30` 个传统资产 ETF/FX 代理复现。Gross 与 `2bps/边` 台账复现了长期正收益、低相关和压力期分散：低成本台账 `2002-10-29` 至 `2026-08-07` 总收益 `+289.4%`、Sharpe `0.491`、MDD `-24.54%`、与 `SPY` 相关 `-0.025`，GFC/COVID/2022 三个窗口分别 `+30.63%/+8.75%/+19.45%`。但 `10bps/边` ETF 压力台账 Sharpe 仅 `0.295`，年换手 `31.26x` 使成本拖累 `3.13%/年`；因此只能记录为公开代理上的部分复现，不登记版本、不 promotion。
- 证据：[首轮诊断](diagnostics/xa-1d-classic-ewmac-replication-2026-08-10.md)、[汇总 JSON](artifacts/xa_1d_classic_ewmac_replication_2026-08-10_summary.json)
