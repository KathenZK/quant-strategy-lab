# Decision Log — Binance-1D-Multi-Asset-TSMOM-Vol-Target

## 2026-07-27 家族立项 + P0 演示基线：因子确认，成本层不合格

- 决策：应用户要求，以学术证据最厚的因子组合（多资产时序动量 + 波动率目标，Moskowitz-Ooi-Pedersen 2012）立演示基线线。契约先冻结后跑数、零参数搜索。结果：毛价格 PnL 2021–2025 逐年为正（+47.3%/+3.9%/+3.2%/+9.6%/+0.4%）、多空腿轮动互补、实现波动 20.8% 精确命中 20% 目标、回撤 −31.4%（同期 BTC 持有 −76.7%）；但年 34 倍单边换手在 taker 成本下漏损约 4.8%/年，叠加资金费 −11.7%，净收益仅 2021 为正，预注册评价 4 条过 2 条（波动、回撤过；年度为正数、利润集中度不过）。判定：因子存在性与风控骨架成立，净收益不合格的根源是执行成本结构与单资产类别广度不足；后续任何改进（再平衡缓冲带、降频、maker 口径、TradFi 永续扩展、carry 信号化）须另立契约预注册，不得继承本轮结果择优。
- 证据：[P0 演示诊断](diagnostics/bin-1d-tsmom-vt-p0-demo-2026-07-27.md)、[演示契约](specs/bin-1d-tsmom-vt-demo-contract-2026-07-27.md)、[tsmom_vt_demo_report.json](artifacts/tsmom_vt_demo_report.json)
