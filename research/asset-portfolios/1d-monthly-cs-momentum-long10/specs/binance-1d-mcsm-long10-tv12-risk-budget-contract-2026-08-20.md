# BIN-1D-MCSM-L10 target12 运营风险预算合同（2026-08-20）

- 身份：原始 `ADV>=1000万`、`1M Top10` long-only 信号的纯 sizing observation；`explore / not promoted / not live-ready`。
- 动机：BTC trend gate 与 MH136 结构候选均未通过后，只量化较低运营风险预算，不再修改 alpha、形成期、排名、buffer 或择时。
- 规则：沿用原始月初开盘换仓、实际资金费、手续费 `0.001/边`、滑点 `0.0004/边`；组合层 `90d` realized volatility、至少 `60d`、额外滞后一日；scale=`clip(0.12/trailing_vol,0,1)`，禁止杠杆。
- 公平窗口：`2020-08-01`–`2026-06-30`；开发/后段、非重叠 12m cohort、recent slices、`2x` 成本、`1d` 换仓延迟、all-listed 控制、同风险预算全市场等权基准、bootstrap 和容量均沿用可实盘化诊断口径。
- `12%` 是事前固定的风险预算读数，不与 `10%/11%/13%/14%` 扫描；即使 MDD 落入 `-25%`，也不改变 12m cohort 稳定性门禁，不构成新增 alpha、clean OOS 或 promotion 证据。
- 时序审计：上月最后一根 `15m` K 仅在新月 `00:00 UTC` 后闭合可知，因此另用真实 `15m` panel 的新月 `00:15` bar open 作为保守可执行成交价；旧仓持有至 `00:15`、新仓自 `00:15` 起计收益，换手成本仍在实际切换时计提。不得把原 `00:00` open 结果单独称为 runner parity。
