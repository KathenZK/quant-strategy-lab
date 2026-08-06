# HYPE-15M-MDTP Campaign Successor 初始研究（2026-08-02）

## 结论

未登记的 campaign successor 保持 `explore / not promoted / not live-ready`；本轮不创建 `V2`。

工程目标已经实现：固定 quantity 持仓、离散 `35%→70%→85%→100%` 层级、`1% R0`、`3x` fill cap、净浮盈加仓、open-risk 检查、`2R` 后保留一半 MFE、`1h/4h` 收盘后更新保护线，以及多空独立评估。旧 V1 平均约 `5h` 的高频 campaign 被改成多头 `79.24h`、空头 `69.21h`，Validation 年化换手分别降至 `9.18` 和 `6.99`。

绩效证据仍不足：

- Long Validation base `+1.96% / Sharpe 0.70 / MDD -3.36% / 19 trades`，8 bps slippage stress 仍为 `+1.73%`；但冻结排名选中的同一配置在完整 Train 为 `-0.52% / Sharpe -0.10`，三个 Train fold 只有 `2/3` 为正。
- Long 的 10,000 次 trade bootstrap 正收益概率仅 `68.0%`，95% 总收益区间为 `[-4.44%, +10.05%]`，没有排除零或负优势。
- Short Validation 连 gross 都为 `-3.89%`，base `-3.87% / Sharpe -2.30 / 17 trades`；bootstrap 正收益概率仅 `0.31%`，95% 区间 `[-6.37%, -1.12%]`。
- Long 的 no-pyramid 为 `+2.20%`，高于 full `+1.96%`；no-MFE-floor 为 `+2.08%`，也高于 full。加仓和 MFE floor 在本窗口没有提供独立净增益。

因此：Long 只保留为有价值的机制观察，不是冻结候选；Short 明确失败。Validation 已揭示，禁止重新排名或修改参数后再次使用。

## 数据与冻结边界

- Binance USD-M `HYPE/USDT:USDT` perpetual `15m`，闭合数据 `2025-05-30 10:30 UTC` 至 `2026-08-01 15:15 UTC`，`41,108` 根。
- 缺口、重复、关键 null、无效 OHLCV 均为 `0`；raw/normalized `41,108/41,108` 全字段对拍通过。
- Train：`[2025-05-30 10:30 UTC, 2026-02-01 00:00 UTC)`。
- Embargo：`[2026-02-01 00:00 UTC, 2026-02-15 00:00 UTC)`。
- Validation：`[2026-02-15 00:00 UTC, 2026-08-02 00:00 UTC)`，本轮每个方向揭示一次。
- Prospective OOS：`[2026-08-02 00:00 UTC, 2026-11-02 00:00 UTC)`，仍未揭示；输入数据终点早于其起点，复现脚本发现未来区间已进入输入后会 fail closed。
- Base cost：fee `10 bps/fill` + adverse slippage `4 bps/fill` + 实际 funding；stress slippage `8 bps/fill`。

## 冻结机制

- `4h` EMA 方向许可，`1h` Donchian 突破，下一可交易 `15m open` 建立 `35%` SEED。
- 后续完整 `1h` 仍站在原突破边界之外，补到 `70%` CORE。
- 净浮盈、趋势许可和 open risk 同时允许时，最多两次加到 `85%`、`100%`。
- 完整计划 quantity 按 `R0=entry equity × 1%`、entry-to-stop 距离及双边成本反推，并受 `3x` cap 限制。
- 数量在 fill 之间固定；只有 entry/layer/exit 产生换手和费用。
- 初始 stop 为 `1h ATR` 与前置 `24h` swing 的较宽者；`4h` Donchian 与 MFE floor 只能收紧。
- campaign 净 MFE 达到 `2R0` 后，保护目标为 `entry equity + 0.5 × peak net profit`。
- 反向 regime 先退出，不在同一时点反手；无固定止盈、无 `14d` timeout。

预声明搜索空间为 `4h EMA 30/42/60 × 1h entry 48/72/96 × stop 2.5/3.5 ATR × 4h exit 18/30/42`，每个方向 `54` 行。

## Train 搜索

| direction | rows | positive full Train | positive Sharpe | 3/3 positive folds | median Train return | best Train return |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Long | 54 | 20 | 20 | 0 | `-0.72%` | `+1.09%` |
| Short | 54 | 4 | 6 | 0 | `-0.71%` | `+0.62%` |

冻结排名优先正 fold 数和最差 fold，因而选中：

- Long：`EMA30 / entry72 / stop2.5 / exit42`，Train `-0.52% / Sharpe -0.10 / MDD -4.55% / 26 trades / avg hold 73.48h`；fold `+0.05% / +0.07% / -1.16%`。
- Short：`EMA30 / entry96 / stop2.5 / exit18`，Train `-0.54% / Sharpe -0.12 / MDD -6.99% / 21 trades / avg hold 85.96h`；fold `-1.88% / +1.54% / +0.15%`。

搜索合同遗漏了“选中行完整 Train 必须为正”的常识性可信度条件。这个问题在 Validation 揭示后才被发现。本轮只把它作为更严格 blocker，不重选候选、不重跑其他候选 Validation；否则会形成事后选择。

另有 `54/54` 个参数组中 `stop 2.5ATR` 与 `3.5ATR` 逐指标 path-equal：前置 `24h` swing 始终更宽，使 ATR 下限 dormant。该旋钮不提供有效搜索维度。

## 一次性 Validation

| direction/scenario | return | Sharpe | MDD | trades | win rate | avg hold | annual turnover | max fill/effective lev | max open risk |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Long gross | `+2.65%` | `0.87` | `-3.34%` | 19 | `36.84%` | `79.25h` | `9.81` | `0.267/0.274x` | `0.87%` |
| Long base | `+1.96%` | `0.70` | `-3.36%` | 19 | `36.84%` | `79.24h` | `9.18` | `0.242/0.248x` | `0.87%` |
| Long stress | `+1.73%` | `0.63` | `-3.30%` | 19 | `31.58%` | `79.05h` | `9.05` | `0.236/0.241x` | `0.86%` |
| Short gross | `-3.89%` | `-2.21` | `-5.04%` | 17 | `17.65%` | `69.21h` | `7.41` | `0.165/0.165x` | `0.82%` |
| Short base | `-3.87%` | `-2.30` | `-4.97%` | 17 | `17.65%` | `69.21h` | `6.99` | `0.155/0.155x` | `0.76%` |

两边都没有 risk breach；最差单笔分别约 `-0.76%`，低于正常 `1R` 和灾难 `3%` 上限。低杠杆不是人为压到固定值，而是宽结构止损与 `1%` 风险预算反推的结果。

## Campaign 与趋势捕获

Long 的 19 笔中：

- 7 笔盈利，4 笔达到 `2R`，4 笔实际发生 pyramid add，共 6 次 add。
- 最大赢家持有 `239.5h`，峰值 `4.88R`，退出保留 `2.44R`，capture ratio `50.02%`。
- 另两笔 `2R+` 赢家分别保留 `50%`；盈利单 capture ratio 中位数为 `50%`。
- 这证明“达到 2R 后最多回吐一半”的账本与止损换算按设计生效。
- 15 笔 opposite-regime exit 合计净收益约 `-2.22%`；4 笔 protective-stop exit 合计约 `+4.24%`。右尾来自少数被 MFE/结构保护的长趋势，但普通 regime exit 仍持续漏损。

Short 没有一笔达到 `2R`，没有 pyramid add；说明失败发生在基础方向/入场层，而不是成本或 MFE 规则。

## Validation 消融

| direction | full | no pyramid | no MFE floor | no structural stop | seed only |
| --- | ---: | ---: | ---: | ---: | ---: |
| Long return | `+1.96%` | `+2.20%` | `+2.08%` | `+1.96%` | `+1.46%` |
| Long Sharpe | `0.70` | `0.85` | `0.71` | `0.70` | `1.01` |
| Short return | `-3.87%` | `-3.87%` | `-3.87%` | `-4.39%` | `-1.86%` |

- Long 的 core confirmation 提高了绝对收益，但 pyramid add 没有增量，MFE floor 在该窗口略有成本，`4h` structural stop path-equal。
- MFE floor 仍正确执行了用户要求的 50% capture；“合同正确”与“提供样本增益”是两个不同判断。
- Short 的 pyramid 与 MFE 都 dormant；增加到 core 只扩大了失败方向的亏损。

## 最终判断

1. 高换手问题已被实质修复，不再是 V1 的隐形连续调仓。
2. Long 显示“少数 3–11 天趋势贡献右尾”的正确形态，但 Train 不稳、Validation 样本少、bootstrap 区间跨零，加仓和 MFE 未证明增量，不能登记。
3. Short 在 gross、base、stress 全部失败，应停止这条镜像式 short 机制。
4. 不得根据已揭示 Validation 改用 Train 收益最高行、删除 pyramid 或改退出后再看同一窗口。
5. Prospective OOS 保持未揭示。只有新的未来数据或 materially new、事前冻结的机制，才能继续作候选判断。

## 证据

- [冻结研究合同](../specs/hype-15m-mdtp-campaign-successor-contract-2026-08-02.md)
- [机器结果](../artifacts/hype_15m_mdtp_campaign_research_2026-08-02.json)
- [Train 全搜索](../artifacts/hype_15m_mdtp_campaign_train_search_2026-08-02.csv)
- [复现脚本](../scripts/research_hype_15m_mdtp_campaign_successor.py)
- Long：[Validation trades](../artifacts/hype_15m_mdtp_campaign_long_2026-08-02_validation_trades.csv) · [equity](../artifacts/hype_15m_mdtp_campaign_long_2026-08-02_validation_equity.csv) · [actions](../artifacts/hype_15m_mdtp_campaign_long_2026-08-02_validation_actions.csv)
- Short：[Validation trades](../artifacts/hype_15m_mdtp_campaign_short_2026-08-02_validation_trades.csv) · [equity](../artifacts/hype_15m_mdtp_campaign_short_2026-08-02_validation_equity.csv) · [actions](../artifacts/hype_15m_mdtp_campaign_short_2026-08-02_validation_actions.csv)
