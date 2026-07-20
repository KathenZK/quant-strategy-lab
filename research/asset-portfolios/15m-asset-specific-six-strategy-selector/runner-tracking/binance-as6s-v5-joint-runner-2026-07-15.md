# V5 联合状态 Runner 对拍记录（2026-07-15）

状态：`implementation parity PASS / exchange-protection tests PASS / disabled / not promoted / not live-ready`。

独立 Runner kind `asset_specific_six_selector_v5_joint_state` 已实现 V5
`nonpreemptive` 路线的 15 条资产专属腿、闭合 K 候选、冻结 strength 排序、
单仓联合状态、真实成交后 cooldown 和同时间戳禁止重入。现已增加
`bin-15m-as6s-v5-joint-np-dry-run` 验证实例，但 TOML 与治理 manifest 均固定
`enabled=false / approval_level=none`，不构成持续 dry-run 或 live 授权。

## 对拍结果

- 15 条腿各抽 3 个历史候选，共 45 个：`side / raw_strength / strength` 全部一致。
- 15 条腿各抽 1 笔完整持仓，共 15 笔：`exit_ts / exit_reason` 全部一致。
- 全候选池账户路由：Runner strict router 与 V5 冻结 nonpreemptive 逐笔账
  `553 / 553` 一致；对拍字段为 sleeve、symbol、side、entry_ts、exit_ts。
- focused unit tests、完整 runner lib tests 与 `clippy -D warnings` 通过。
- CLI strict replay 已改为读取 `AS6S_V5_PARITY_FIXTURE`，复用同一冻结 fixture
  执行 45 个信号检查、15 条腿退出检查和 553 笔账户路由，不再使用无证据的
  placeholder handler。

## 交易所保护与重启对账

- 所有 V5 新仓均改为 `MarkPriceMarket` 保护；固定止盈腿同时挂 mark-price
  take-profit-market 与 stop-market，仅移动止损腿至少始终保留 stop-market。
- `ProtectionOwnership::Strategy` 现在只表示退出状态机由 V5 Driver 管理，不再
  隐含 `StrategyManaged` 裸仓。常规周期会先检查保护成交，再运行 Driver。
- 趋势腿的 trailing stop 只在闭合策略 K 更新；stop 变化后由同仓位
  `Immediate` target 同步重挂交易所保护。成功路径固定为先确认新 stop，再撤旧
  stop；TP 未变化时不重复撤挂。
- 修复多币种 dry-run symbol 绑定：例如 ETH 持仓的保护、查询和恢复均落在
  `ETHUSDT`，不会误用实例默认的 `BTCUSDT`。
- 定向模拟测试已覆盖：ETH 保护武装、mark 跌穿止损后的保护成交识别、BTC
  无孤儿仓位、进程重启后 ETH 缺失保护单的撤旧与重建。
- 完整 Runner lib suite：`198 passed / 0 failed / 3 ignored`；3 个 ignored
  数据湖对拍以冻结 fixture 单独运行后全部 PASS；`clippy -D warnings` PASS。
- CLI strict replay 复跑结果为 `45` signal checks、`15` exit sleeves、
  `553` routed trades、fixture SHA-256
  `5d50f05fbc939bee2676feb91021c078f1f989e0ad19d87dbb29ad1a5c42daaf`、
  `parity=PASS`；禁用实例 smoke `ok=true`，dry-run/live config 和治理
  lock/spec links 校验通过。

机器可读证据见
[`binance_as6s_v5_joint_state_runner_parity_2026-07-15.json`](../artifacts/binance_as6s_v5_joint_state_runner_parity_2026-07-15.json)。
供 manifest parity gate 使用的标准 schema 投影见
[`BIN-15M-AS6S-V5-JOINT-NP_parity_2026-07-15.json`](../artifacts/BIN-15M-AS6S-V5-JOINT-NP_parity_2026-07-15.json)。
CLI strict replay 使用的 53 MiB 冻结输入保存在
[`as6s_v5_runner_signal_parity_fixture_2026-07-15.json`](../artifacts/as6s_v5_runner_signal_parity_fixture_2026-07-15.json)，
其原始字节 SHA-256 即上述 `5d50f05f...42daaf`。

## 实现中发现并修正的问题

执行契约中的 6 个 `legacy_runner_reference` 只能作为机制和历史名字参考，不能
证明参数等价。实际对拍发现，同名 ETH RSI leg 与既有 `six_asset_ensemble`
配置在 RSI、ADX、TP/SL、最大持仓和 cooldown 等字段上均不同。V5 Runner
因此独立冻结研究时实际使用的六套 1h 参数，不复用既有模块的配置、持仓或
cooldown 状态。

另经源码核对，legacy CSV 保存的是 stateless 原始机会，不是预先做过 cooldown
筛选的路径；账户 cooldown 仍然只在被接受的真实持仓退出后创建，V5 联合状态
语义成立。

## 仍未解除的门禁

- 历史收益账仍是 trade-OHLC strict replay；真实 Runner 的 mark-price 保护可能
  比研究 K 线退出更早，持续 dry-run 必须单独核对该执行差异。
- 尚未完成持续 dry-run、真实 Binance testnet/小额订单生命周期 smoke、断网与
  API outcome-unknown 故障注入；manifest/config 只登记禁用验证实例。
- trailing protection 已消除成功路径的先撤后挂窗口，但仍需在测试网验证新 stop
  提交失败、旧 stop 撤单 outcome-unknown 与双 stop 暂存时的 reconcile 兜底。
- 最终未来 OOS 仍锁定为
  `[2026-07-14T09:00Z, 2026-10-14T09:00Z)`，窗口结束前不得查看部分结果。
