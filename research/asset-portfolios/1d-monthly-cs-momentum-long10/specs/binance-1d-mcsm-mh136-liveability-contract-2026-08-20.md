# BIN-1D-MCSM-L10 MH136 可实盘化候选冻结合同（2026-08-20）

## 身份与因果动机

- Family：`Binance-1D-Monthly-Cross-Sectional-Momentum-Long10`（`BIN-1D-MCSM-L10`）的 materially new multi-horizon observation；当前仍为 `explore / not promoted / not live-ready`。
- 前序 `BTC SMA200` 市场 gate 候选在揭示后未通过：它降低 MDD，但显著降低 Sharpe/CAGR，并在 exposed-regime 后段失效；不得从其 `SMA150/200/250` 邻域挑 winner。
- 本轮只检验一个新机制：固定 `1M/3M/6M` 三个形成期 sleeve 等资本合成，以降低单一 1M 排名的 regime 集中；不搜索形成期集合、不按结果改变 sleeve 权重。
- 全历史的基础路径已经揭示，本轮仍不属于 clean OOS；规则先冻结、再一次性运行，后段只称 `locked historical holdout / exposed-regime`。

## 冻结主候选 `ADV10M_MH136_TV15`

1. 主要宇宙固定为截至信号日 `30d ADV >= 1000万 USDT` 的点时 Binance USD-M USDT 永续；稳定币等排除、覆盖与端点要求继承 [原 Long10 合同](binance-1d-mcsm-long10-diagnostic-contract-2026-08-18.md)。
2. 三个 sleeve 分别按过去 `1/3/6` 个完整日历月的端点收益排序，各自选择 Top10；不跳过最近月。
3. 每个 sleeve 占未缩放组合 gross 的 `1/3`，sleeve 内 10 币等权；同一名字跨 sleeve 重合时权重相加，单名未缩放上限自然为 `10%`。
4. 每月 1 日 UTC 开盘按合成目标换仓；无月中择时、止损、buffer 或正收益门槛，不做空。
5. 合成未缩放组合使用 `90d` realized volatility、至少 `60d`、额外保守滞后一日；scale=`clip(0.15 / trailing_vol, 0, 1)`，禁止杠杆。
6. 手续费 `0.001/边`、不利滑点 `0.0004/边`、逐日实际资金费；末日收盘强平并计成本，现金收益为 0。

## 固定对照、消融和扰动

- 单袖对照：`1M target15`、`3M target15`、`6M target15`。
- 主候选：`1M+3M+6M` 等权 sleeve target15。
- sleeve 消融：`1M+3M`、`1M+6M`、`3M+6M`，剩余 sleeve 重新等权；只用于确认贡献，不据此选子集登记。
- 风险预算扰动：完整 MH136 的 target `12%/18%`；不得从扰动中另选 winner。
- 跨宇宙：`all_listed` MH136 target15 只作一致性控制。
- 公平 beta 基准：同一 ADV 宇宙全市场月度等权 + 相同 target15，不加市场 gate。

## 时间、压力、MC 与容量

- 共同评估起点 `2020-08-01`（满足 6M 形成端点）；开发段至 `2023-12-31`，后段 `2024-01-01`–`2026-06-30`。
- 报告非重叠完整 `12m` cohort；recent slices 不替代结构化时间证据。
- 压力：费用与滑点 `2x`、所有月度目标延迟一个 UTC 日开盘；旧仓在延迟前继续持有。
- MC：月度组合 cohort bootstrap，固定种子，至少 `5000` 条等长路径。
- 容量：按换仓前已知 `30d ADV` 和实际 `delta_weight`，报告 `0.5%/1%/2% ADV` 参与率 AUM 上限。

## 事前参考线与状态边界

- 主候选全段：净 Sharpe `>=0.8`、MDD `>=-25%`、CAGR `>=10%`。
- exposed-regime 后段：净收益 `>0`、MDD `>=-20%`。
- 完整非重叠 12m cohort 至少 `60%` 为正；`2x` 成本仍为正；target12/18 都为正；all-listed control 为正；无杠杆、无非正权益。
- sleeve 消融用于机制解释：若删掉某 sleeve 后全面改善，说明该 sleeve 没有增量贡献，MH136 不可按原样登记。
- 即使所有参考线通过，仍只进入正式 Gate 0–4 promotion review；没有 prospective evidence、runner parity、拒单/断流/重启审计前，不得生成 live spec 或进入 dry-run/live。

## 固定输出

- 主指标、逐年、开发/后段、12m cohort、最近切片、消融、风险扰动、压力、bootstrap、PnL attribution、逐月三袖持仓、日路径、容量与超额收益。
- 产物保存到 `../artifacts/`，脚本保存到 `../scripts/`，中文裁决保存到 `../diagnostics/`。
