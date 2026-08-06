# Decision Log — Binance-1D-Multi-Asset-TSMOM-Vol-Target

## 2026-08-05 用户决策：P1 契约暂停执行（未跑数）

- 决策：用户明确表示不想交易 Binance 山寨币池（"加密货币都是泡沫"，只保留 BTC/ETH/HYPE 大币种 + 通过 Binance TradFi 永续交易美股/商品的路线）。P1 契约保持冻结、**未执行任何回测**，家族维持 `explore / not promoted / not live-ready`；若未来重启，直接按已冻结契约跑数，不得修改。后续研究转向新家族（小资产池 EWMAC 通用趋势，见 [`1d-ewmac-universal-trend/`](../1d-ewmac-universal-trend/README.md)）。
- 证据：[P1 执行层改造契约](specs/bin-1d-tsmom-vt-p1-rebalance-execution-contract-2026-08-05.md)（冻结未跑）

## 2026-08-05 P1 执行层改造契约冻结（跑数前预注册）

- 决策：在 MA7 单资产研究线全线冻结、确认转向组合级 CTA 后，为本家族冻结 P1 契约：P0 信号层与仓位层原样继承（TSMOM 符号集成 + 两层 vol targeting + 月度 top-30 加密池 + 默认 taker 成本），唯一改动是预注册的再平衡纪律（主变体 E1 = 0.5% 权益缓冲带，另 5 个对照/单调性变体），kill gate 只对 E1 判定（含年换手 ≤12×、成本拖累 ≤2%/年、毛 PnL 保留率 ≥70% 等 6 条）。同时记录成本敏感性口径偏离：maker `2 bps` + 滑点 `4 bps`/边仅作报告性敏感度，理由是目标持仓无日内紧迫性、限价执行现实可行，不得用于翻转 gate。数据侧义务：`emax_1d_derived` 缓存与 inventory CSV 已在 2026-08-04 清理中删除，跑数前必须按记录口径重建并用 E0 复刻校验 P0。TradFi 永续历史仍仅约 6 个月，本轮维持纯加密池。
- 证据：[P1 执行层改造契约](specs/bin-1d-tsmom-vt-p1-rebalance-execution-contract-2026-08-05.md)、[P0 演示诊断](diagnostics/bin-1d-tsmom-vt-p0-demo-2026-07-27.md)

## 2026-07-27 家族立项 + P0 演示基线：因子确认，成本层不合格

- 决策：应用户要求，以学术证据最厚的因子组合（多资产时序动量 + 波动率目标，Moskowitz-Ooi-Pedersen 2012）立演示基线线。契约先冻结后跑数、零参数搜索。结果：毛价格 PnL 2021–2025 逐年为正（+47.3%/+3.9%/+3.2%/+9.6%/+0.4%）、多空腿轮动互补、实现波动 20.8% 精确命中 20% 目标、回撤 −31.4%（同期 BTC 持有 −76.7%）；但年 34 倍单边换手在 taker 成本下漏损约 4.8%/年，叠加资金费 −11.7%，净收益仅 2021 为正，预注册评价 4 条过 2 条（波动、回撤过；年度为正数、利润集中度不过）。判定：因子存在性与风控骨架成立，净收益不合格的根源是执行成本结构与单资产类别广度不足；后续任何改进（再平衡缓冲带、降频、maker 口径、TradFi 永续扩展、carry 信号化）须另立契约预注册，不得继承本轮结果择优。
- 证据：[P0 演示诊断](diagnostics/bin-1d-tsmom-vt-p0-demo-2026-07-27.md)、[演示契约](specs/bin-1d-tsmom-vt-demo-contract-2026-07-27.md)、[tsmom_vt_demo_report.json](artifacts/tsmom_vt_demo_report.json)
