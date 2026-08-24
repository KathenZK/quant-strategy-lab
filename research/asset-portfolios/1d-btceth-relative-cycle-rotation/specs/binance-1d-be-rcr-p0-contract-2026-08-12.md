# BIN-1D-BE-RCR P0 冻结合同（2026-08-12）

## 1. 研究问题与身份

目标是在 BTC/ETH 共同可交易历史上，测试“共同周期方向 + 相对强弱选币 + 单仓持有”能否在不超过 `1x` 毛杠杆下同时达到：

1. development 成本后组合净值倍数 `>=20.0x`；
2. 按真实 `1h` 事件顺序重放的组合 MDD `>=-20.0%`；
3. 通过成本、延迟、时间稳定性、资产参与度与收益集中度门禁。

标准家族名为 `Binance-1D-BTCETH-Relative-Cycle-Rotation`，短 id `BIN-1D-BE-RCR`。它不是 `BIN-1D-MA7-AS-SEARCH` 的 V2，不继承 HYPE V7.1 参数或版本身份；只继承冻结、消融、因果归因和唯一候选治理方法。

## 2. 数据与封存区间

- 来源：`data/features/binance_1d_ma7_rsi6_dapml_p0/` 的可信 BTC/ETH perp `1h` 与 funding/mark 快照；原始清单 blocker 为 0。
- BTC `1h` hash：`3e18066005c9747c040c2686e0b535769f293911e660ad8f923d81b0e2bee1cb`。
- BTC funding hash：`83e4043d905274dd11d3f7874605cbe05bfea927d80853dd96959d1effd45aca`。
- ETH `1h` hash：`29a5c7ba22831240629d48899b34c7cbfe9f411c139f7dd5220979958a416561`。
- ETH funding hash：`f16a71928dad18e930db63bfe70d1d949ce79f7061b83717de9c2b50ea7cdb54`。
- development：`[2019-12-24T00:00:00Z, 2025-08-07T00:00:00Z)`；唯一允许搜索、消融、排序的区间。
- researcher-exposed audit：`[2025-08-07T00:00:00Z, 2026-08-10T00:00:00Z)`；本轮开始时封存，只有 development 唯一候选完全过门后才可一次揭示。
- prospective：信号 candle open `>=2026-08-13T00:00:00Z`，首次可执行开盘 `>=2026-08-14T00:00:00Z`；不得回填、窥视或改变起点。

## 3. 冻结信号与执行

每个 UTC 日 `t` 闭合后，使用 `close[t]` 及更早数据：

- 对资产 `i`，`z_i(h,v)=log(close_i[t]/close_i[t-h]) / (std(log_return_i[t-v+1:t]) * sqrt(h))`；标准差使用样本标准差，非有限或分母为零时信号为空。
- `market_score=(z_BTC(regime_h,vol_h)+z_ETH(regime_h,vol_h))/2`。
- `relative_score=z_BTC(relative_h,vol_h)-z_ETH(relative_h,vol_h)`。
- 若 `market_score > deadzone`，候选为 long；`relative_score > switch_margin` 选 BTC，`relative_score < -switch_margin` 选 ETH，否则 flat。
- 若 `market_score < -deadzone`，候选为 short；`relative_score > switch_margin` 选较弱的 ETH，`relative_score < -switch_margin` 选较弱的 BTC，否则 flat。
- 其他情形为 flat。候选状态连续出现 `confirm_days` 个闭合日后才成为下一开盘目标。
- 信号日后的下一 UTC 日开盘成交；反转或换币先平旧仓再开新仓，计两个 fills；终点强制平仓。
- 入场目标名义价值为成交前 equity 的 `1.0x`，持有期间数量固定，不做逐日再平衡、vol targeting 或回撤缩放。
- 每 fill 费用 `0.001`；base slippage `0.0004`，stress `0.0008`；funding 按真实事件时间、方向、数量与 mark 记账。
- ordered MDD 以逐小时 open/high/low/close、成交与 funding 的真实时间顺序计算；同一小时先处理开盘成交，再处理小时内不利极值，funding 按其 timestamp 入账。

## 4. 冻结有限搜索空间

全笛卡尔积共 `7,560` 个配置，不得中途增删：

- `regime_h ∈ {20,40,60,90,120,180,270}`；
- `relative_h ∈ {10,20,40,60,90,120}`；
- `vol_h ∈ {14,28,56}`；
- `deadzone ∈ {0,0.25,0.5,0.75,1.0}`；
- `switch_margin ∈ {0,0.25,0.5}`；
- `confirm_days ∈ {1,2,3,5}`。

排序只可使用 development。先用日线 close 路径筛选；对 `equity>=20x` 且 daily-close MDD `>=-20%` 的全部配置做 ordered `1h` 重放。若数量过多，仍需重放全部，不得只取最好看者。

唯一候选的确定顺序：`ordered MDD` 降序、`stress log-growth retention` 降序、base `equity_multiple` 降序、换手升序、参数字典序。完全同路径配置先去重，保留字典序最小配置。

## 5. Development 硬门禁

候选必须全部满足：

1. base `equity_multiple >=20.0`，ordered `1h MDD >=-20.0%`；
2. stress `8bps/fill` 仍 `equity_multiple >=16.0` 且 ordered `1h MDD >=-22.0%`；
3. 额外延迟一日的 log-growth retention `>=70%`、equity `>=8.0x`、ordered `1h MDD >=-25%`；
4. 完整自然年净收益为正的比例 `>=70%`，滚动 `365d` 净收益为正的观测比例 `>=70%`；
5. BTC 与 ETH 各自持仓小时占比 `>=10%`、各自闭合交易数 `>=5`，long 与 short 各有 `>=5` 笔；
6. 最大单笔交易对总正向 log-growth 的贡献 `<=35%`；
7. 数据质量 blocker 为 0，逐笔费用、slippage、funding、换仓与终点平仓均可对账。

任一失败即 `HARD-GATE-FAILED / explore / not promoted / not live-ready`；不揭示 audit，不登记版本，不启用 risk scaling 救援。

## 6. Audit、prospective 与登记

- 只有 development 唯一候选全部通过第 5 节，才可冻结其参数并一次揭示 researcher-exposed audit；该段只能判定稳健性，不能再调参。
- audit 至少要求净正收益、MDD `>=-20%`、stress 净正、延迟净正、BTC/ETH 均有参与；失败即停止，不救援。
- audit 通过也只允许登记研究版本，主状态仍为 `registered / not promoted / not live-ready`；prospective 必须按已锁起点等待足够证据，promotion 另立合同。
- 交易路径发生实质变化并形成登记候选时，必须生成完整 HTML，逐笔入场与对应出场连线；失败路线只需保留机器产物与诊断报告。
