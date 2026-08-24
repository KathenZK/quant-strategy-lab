# BIN-1D-MCSM-L10 执行语义修复冻结合同（2026-08-20）

## 身份与停止线

- Family：`Binance-1D-Monthly-Cross-Sectional-Momentum-Long10`（`BIN-1D-MCSM-L10`）。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`。
- 本合同只修复数据与成交语义；冻结 alpha 为 `ADV>=1000万`、上一完整月 Top10、long-only，风险预算固定为无杠杆 `target12`。不得借修复改形成期、Top N、ADV 门槛、风险目标、buffer、gate 或成本。
- 原引擎与本轮所有基于原引擎的绩效证据标记为 `PERFORMANCE_INVALIDATED`；只有修复后全链路零 blocker 的重跑才可恢复绩效讨论。

## P0：点时合约生命周期账

1. 建立逐 symbol 的 point-in-time lifecycle ledger，至少包含 `listing_time`、`trading_start`、`status_change_time`、`delist_or_settlement_time`、`replacement_symbol`、事件来源与抓取时间。
2. 合约状态必须来自 Binance 可审计来源；K 线存在、价格非空或过去 ADV 达标都不能替代 `TRADING` 状态。
3. symbol rename、token swap、自动结算和下架必须显式建模；不得把旧 symbol 的静态占位 K 线解释成持续可交易。
4. 生命周期账、15m 原始分区和归一化分区必须能按研究截止日冻结并输出 provenance hash。

## P0：可成交入选与退出

月度候选必须同时满足：

- 信号只使用新月 `00:00 UTC` 前已经闭合的上月 15m 数据；
- 上月末点时 `30d ADV >= 1000万 USDT`；
- 计划成交时合约状态为 `TRADING`；
- 新月 `00:15 UTC` bar 的 `open > 0`、`volume > 0`、`trade_count > 0`；
- 原始与归一化 bar 时间戳、OHLCV、成交笔数一致。

若排名内名字不可成交，按冻结的形成收益排序顺延补足；不足 10 个时缺口持现金。顺延只是执行资格过滤，不改变信号定义。退出也必须在实际有成交的 bar 完成；无法退出时保留风险暴露、记录 blocker，并停止绩效计算，禁止假设零收益平仓。

## P0：持仓估值与缺数

- 持仓价格收益不得调用 `fillna(0)`；任何持仓日缺失 close、前收或资金费来源时必须 fail closed。
- 对 `FTM/KNC/MANA/MKR` 的 `2022-02-26`–`2022-02-28`、`BNX` 的 `2022-06-09` 等已知缺口，先从原始源补洞并完成 raw/normalized parity；无法修复则对应区间不得进入可比较绩效样本。
- 对下架/结算资产，以官方结算事件和实际可得成交路径计算退出；不允许用最后价格无限前填，也不允许把缺失收益设为 0。
- 每次重跑必须输出 `invalid_entry`、`invalid_exit`、`held_missing_close`、`unknown_contract_status` 四类 blocker 清单；任一计数非零则 `performance_valid=false`。

## P0：因果成交时序

1. 上月最后一根 `15m` bar 在新月 `00:00 UTC` 后才可用，因此不得用同一日 `00:00` open 成交新信号。
2. 研究统一以新月 `00:15 UTC` open 作为最早基准成交时点；旧仓承担 `00:00`–`00:15` 的真实收益，新仓只从 `00:15` 后开始计收益。
3. 若信号计算、状态快照或下单未在 `00:15` 前完成，则按实际后续 bar 成交并记录延迟；不得回填到更优价格。
4. 在新目标全部确认成交前，账本必须保留旧仓、部分成交和现金；拒单、断流、重启不得把目标权重直接写成实际权重。

## 冻结重跑与验收

- 只重跑 `ADV Top10 target12`，并保留同风险预算全市场等权基准；不再扫描参数。
- 成本保持手续费 `0.001/边`、滑点 `0.0004/边`、逐日实际资金费；另跑 `2x` 成本和 `1d` 延迟压力。
- 必须同时满足：四类 blocker 全为 0；逐日 `price + funding - fee - slippage = net`；换仓目标、订单、成交、实际持仓和权益可逐笔对账；原始/归一化/研究输入 hash 可追溯。
- 零 blocker 后重新报告全段、开发/后段、非重叠 12m cohort、recent slices、bootstrap、all-listed 控制、容量和超额收益。原数字不能沿用。
- 即使修复后通过研究参考线，也只允许进入正式 promotion review；在 runner parity、dry-run 对账、拒单/断流/重启演练和新 prospective evidence 完成前，仍不得进入 live。

## 固定证据

- [target12 风险预算合同](binance-1d-mcsm-long10-tv12-risk-budget-contract-2026-08-20.md)
- [可实盘化审计](../diagnostics/binance-1d-mcsm-long10-liveability-audit-2026-08-20.md)
- [执行 blocker 明细](../artifacts/binance-1d-mcsm-long10-target12-execution-timing-2026-08-20-blockers.csv)
- [执行审计汇总](../artifacts/binance-1d-mcsm-long10-target12-execution-timing-2026-08-20-summary.json)
