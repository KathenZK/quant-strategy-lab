# Binance 1D MA7 P2-F Frontier Tail-State 归因合同

## 1. 研究问题

P2-E 的固定 `3,600` 个共享 pairs 在真实 ordered `1h` 口径下没有任何两资产 `MDD<=20%` 组合；BTC 单资产有 `81` 个，ETH 为 `0`。在引入 materially new mechanism 前，先判断 frontier 的最大回撤事件是否稳定集中于可在当时观察到的慢趋势冲突、高波动状态或持仓生命周期失效。

本轮只作 outcome attribution，不运行候选 PnL、不修改交易、不选择参数、不打开 researcher-exposed audit/prospective。

## 2. 冻结样本

输入只使用 P2-E 固定 `3,600` pairs 与 development：

- growth stratum：按两资产较低终值降序前 `100`；
- risk stratum：按两资产最差 ordered MDD 降序前 `100`；
- balanced stratum：按 `log(min equity) - 3×max(0, abs(worst MDD)-20%)` 降序前 `100`；
- 三层去重后全部重放，不按归因结果增删样本。

## 3. 归因变量

每个资产、每个 pair 只取全账户 ordered MDD 最深事件。所有状态变量严格截于事件所在 UTC 日之前一根完整日线：

1. `SMA30/90/200` level alignment：long 为前收高于 SMA，short 为前收低于 SMA；
2. `SMA30/90/200` level+slope alignment：除 level 外，慢均线过去 `20d` 方向与持仓一致；
3. `NATR7=ATR7/close` 的 trailing `365d` percentile rank；
4. 事件时 trade age、side、entry mode、exit reason、最终净收益；
5. 从 entry 至 MDD event 的真实 `1h` MFE、MAE 与从 MFE 到事件的 giveback，仅作描述；
6. 从 entry 至事件日前一根完整日线 close 的已实现时点 MFE，以及从该 MFE 到 event 的 giveback；`LIFECYCLE` 机制门只使用这个 closed-daily 序列；
7. MDD event 的 calendar month/year 与 timestamp cluster。

不得使用事件日尚未收盘的日 high/low/close 构建状态标签；事件小时价格只用于事后 MFE/MAE 路径归因。

若早期 Binance 永续历史不足以形成某个 slow horizon 及其 `20d` slope，该事件对该 horizon 记为 `unavailable / not covered`，不得把缺失值伪装成 conflict，也不得用现货或其它交易所历史回填。

## 4. 机制升级门

本轮不设收益门，只决定下一份机制合同的优先级：

- `SLOW_REGIME`：同一 slow horizon 的 level+slope conflict 在 BTC、ETH 各自至少 `60%` frontier MDD events 出现，且三个 strata 方向一致；
- `VOL_STATE`：BTC、ETH 各自至少 `60%` 事件位于 development trailing NATR percentile `>=80%`，且三个 strata 一致；
- `LIFECYCLE`：至少 `60%` 事件在事件日前的完整日线 close 序列中已有正 MFE，且从该 MFE 到 event 回吐达到 MFE 的 `>=50%`；同一事件小时的 favorable extreme 不得用于此门；
- 若没有机制过门，不得组合弱标签；下一步转向新信号信息而不是风险 overlay。

若多个机制过门，先选跨资产覆盖率最低值最高者；并列优先顺序固定为 `SLOW_REGIME > VOL_STATE > LIFECYCLE`。后续 PnL 合同必须包含 exact P2-E controls、OAT、共享参数、真实 ordered 1h MDD、`1x` 与 hard target；本轮归因本身不能登记 V2。

## 5. 固定输出

- 去重样本 manifest；
- 每个 pair/asset 的 MDD event 明细；
- 按 asset/stratum 的覆盖率与 calendar cluster；
- 中文 diagnostic 与机器 JSON/CSV；
- 状态保持 `explore / not promoted / not live-ready`。
