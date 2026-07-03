# HYPE PBTR V6.2.1 + MII V1.3 共享子账户单仓组合诊断 2026-07-02

## 结论

在同一个子账户只允许一个 HYPEUSDT 持仓时，两个策略不能简单相加。按共同样本窗口和保守全局单仓回放，组合会明显提高交易频率和样本内复利收益，但严格逐 K mark-to-market 后，风险读数必须分成三层：已平仓权益 DD、bar-close MTM DD、intrabar adverse MTM DD。`HYPE-5M-PBTR-V6.2.1` 的原始已平仓 `-22%` 级别回撤仍成立；如果按每根 K 收盘标记，回撤仍在可解释范围内；只有按每根 K 的最不利 high/low 做强制平仓式标记时，才会看到约 `-55%` 的极端浮亏压力。这不是更安全的合并，只是两个正期望样本流在高杠杆口径下的收益叠加诊断。

- 共同窗口：`2025-06-02T21:40:00+00:00` 到 `2026-06-18T18:45:00+00:00`。只统计 entry 落在共同窗口内的候选事件。
- `PBTR only`：`218` 笔，总收益 `1078.68%`，已平仓 DD `-22.35%`，Close MTM DD `-26.10%`，Intrabar adverse DD `-54.93%`。
- `MII only`：`182` 笔，总收益 `523.41%`，已平仓 DD `-17.23%`，Close MTM DD `-21.54%`，Intrabar adverse DD `-22.24%`。
- `combo_pbtr_priority`：`368` 笔，总收益 `7187.12%`，已平仓 DD `-30.28%`，Close MTM DD `-32.34%`，Intrabar adverse DD `-55.23%`；其中 PBTR 成交/阻塞 `206/211`，MII 成交/阻塞 `162/61`。
- `combo_mii_priority`：`368` 笔，总收益 `7187.12%`，已平仓 DD `-30.28%`，Close MTM DD `-32.34%`，Intrabar adverse DD `-55.23%`；本窗口内同 timestamp 优先级改变没有影响，说明冲突主要来自持仓区间重叠，而不是同一时刻抢单。

直观解释：`PBTR` 信号更多、持仓更碎，会占掉一部分 `MII` 入场；但这次样本里被保留下来的 `MII` 子集反而更强，来源内复利收益高于 `MII only`。真正的问题不是原始已平仓 DD 从 `-22%` 变成 `-55%`，而是如果按每根 K 的最不利 high/low 做强制平仓式标记，`PBTR` 的 `3x` 持仓内压力在共享账户里仍然很大。若要共用子账户，应先降 PBTR sizing 或设置全局风险预算，而不是直接把两个默认暴露放在一起跑。

## 给同事看的关键表

这张表里的 `Close MTM DD` 更接近平常说的持仓回撤；`Intrabar adverse DD` 是用 K 线 high/low 做最不利标记的压力测试，不应和常规最大回撤混用。

| 场景 | 成交 | 总收益 | 已平仓DD | Close MTM DD | Intrabar adverse DD | 胜率 | PF | 笔/天 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `PBTR only` | `218` | `1078.68%` | `-22.35%` | `-26.10%` | `-54.93%` | `64.68%` | `1.831` | `0.572` |
| `MII only` | `182` | `523.41%` | `-17.23%` | `-21.54%` | `-22.24%` | `84.62%` | `2.154` | `0.478` |
| `combo` | `368` | `7187.12%` | `-30.28%` | `-32.34%` | `-55.23%` | `74.73%` | `2.050` | `0.966` |

## 回放口径

- `HYPE-5M-PBTR-V6.2.1`：复用既有 `V6.2.1` long/short filtered signal，下一根 `5m` open 入场，入场即固定 TP/SL，fixed `3x` 回测口径。
- `HYPE-15M-MII-V1.3`：复用 `V1.2` ATR bracket 候选，`K+1` 下一根 `15m` open 入场，`TP=1.25*ATR96%`、`SL=5*ATR96%`、`hold=24`，fixed `2.5x` exposure。
- 全局单仓：按候选 `entry_ts` 排序；若已有持仓未退出，后续候选信号直接视为 blocked；若 entry 与上一笔 exit 同 timestamp，也保守视为 blocked。
- 同 timestamp 优先级：分别测试 `PBTR` 优先和 `MII` 优先。真实 runner 必须显式配置这一规则。
- 回撤口径：`已平仓DD` 只在交易退出后更新权益；`Close MTM DD` 在持仓期间逐根 K 用 close 做可清算标记；`Intrabar adverse DD` 在持仓期间逐根 K 用 long 的 low / short 的 high 做最不利可清算标记，因此是 OHLC 下偏保守的浮亏压力读数。

## 汇总

| 场景 | 候选 | 成交 | 阻塞 | PBTR 成交/阻塞 | MII 成交/阻塞 | 总收益 | 年化 | 已平仓DD | Close MTM DD | Intrabar adverse DD | 胜率 | PF | 笔/天 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `pbtr_only` | `417` | `218` | `199` | `218/199` | `0/0` | `1078.68%` | `965.21%` | `-22.35%` | `-26.10%` | `-54.93%` | `64.68%` | `1.831` | `0.572` |
| `mii_only` | `223` | `182` | `41` | `0/0` | `182/41` | `523.41%` | `478.31%` | `-17.23%` | `-21.54%` | `-22.24%` | `84.62%` | `2.154` | `0.478` |
| `combo_pbtr_priority` | `640` | `368` | `272` | `206/211` | `162/61` | `7187.12%` | `6011.25%` | `-30.28%` | `-32.34%` | `-55.23%` | `74.73%` | `2.050` | `0.966` |
| `combo_mii_priority` | `640` | `368` | `272` | `206/211` | `162/61` | `7187.12%` | `6011.25%` | `-30.28%` | `-32.34%` | `-55.23%` | `74.73%` | `2.050` | `0.966` |

## 来源拆分

### combo_pbtr_priority

| 来源 | 候选 | 成交 | 阻塞 | 成交占比 | 来源内复利总收益 | 已平仓DD | Close MTM DD | Intrabar adverse DD | 胜率 | PF | 平均单笔 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE-5M-PBTR-V6.2.1` | `417` | `206` | `211` | `55.98%` | `961.07%` | `-22.35%` | `-27.00%` | `-56.08%` | `65.05%` | `1.837` | `1.268%` |
| `HYPE-15M-MII-V1.3` | `223` | `162` | `61` | `44.02%` | `586.77%` | `-16.71%` | `-19.30%` | `-19.55%` | `87.04%` | `2.563` | `1.252%` |

### combo_mii_priority

| 来源 | 候选 | 成交 | 阻塞 | 成交占比 | 来源内复利总收益 | 已平仓DD | Close MTM DD | Intrabar adverse DD | 胜率 | PF | 平均单笔 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `HYPE-5M-PBTR-V6.2.1` | `417` | `206` | `211` | `55.98%` | `961.07%` | `-22.35%` | `-27.00%` | `-56.08%` | `65.05%` | `1.837` | `1.268%` |
| `HYPE-15M-MII-V1.3` | `223` | `162` | `61` | `44.02%` | `586.77%` | `-16.71%` | `-19.30%` | `-19.55%` | `87.04%` | `2.563` | `1.252%` |

## 阻塞矩阵

| 场景 | 被阻塞来源 | 占仓来源 | 阻塞次数 |
| --- | --- | --- | ---: |
| `pbtr_only` | `HYPE-5M-PBTR-V6.2.1` | `HYPE-5M-PBTR-V6.2.1` | `199` |
| `mii_only` | `HYPE-15M-MII-V1.3` | `HYPE-15M-MII-V1.3` | `41` |
| `combo_pbtr_priority` | `HYPE-15M-MII-V1.3` | `HYPE-15M-MII-V1.3` | `34` |
| `combo_pbtr_priority` | `HYPE-15M-MII-V1.3` | `HYPE-5M-PBTR-V6.2.1` | `27` |
| `combo_pbtr_priority` | `HYPE-5M-PBTR-V6.2.1` | `HYPE-15M-MII-V1.3` | `23` |
| `combo_pbtr_priority` | `HYPE-5M-PBTR-V6.2.1` | `HYPE-5M-PBTR-V6.2.1` | `188` |
| `combo_mii_priority` | `HYPE-15M-MII-V1.3` | `HYPE-15M-MII-V1.3` | `34` |
| `combo_mii_priority` | `HYPE-15M-MII-V1.3` | `HYPE-5M-PBTR-V6.2.1` | `27` |
| `combo_mii_priority` | `HYPE-5M-PBTR-V6.2.1` | `HYPE-15M-MII-V1.3` | `23` |
| `combo_mii_priority` | `HYPE-5M-PBTR-V6.2.1` | `HYPE-5M-PBTR-V6.2.1` | `188` |

## 数据质量与限制

- PBTR `5m` rows `113998`，范围 `2025-05-30T10:30:00+00:00` 到 `2026-06-30T06:15:00+00:00`，filtered 候选 `419`。
- MII `15m` rows `37607`，quality gate `True`，范围 `2025-05-30T10:30:00+00:00` 到 `2026-06-26T04:00:00+00:00`，filtered 候选 `225`。
- 这是 OHLC bar replay 的组合层诊断，未纳入资金费、盘口级滑点、真实 market/stop-market 延迟、交易所仓位/挂单对账和 runner 重启恢复。
- 两个策略各自都没有获得 live-ready 批准；组合运行还会新增跨策略优先级、全局 kill switch、全局 notional cap 和 state reconciliation 风险。

## 产物

- 脚本：`research/hype/cross-strategy-account/scripts/research_hype_pbtr_v621_mii_v13_shared_account.py`
- 汇总 CSV：`research/hype/cross-strategy-account/artifacts/hype_pbtr_v621_mii_v13_shared_account_summary_2026-07-02.csv`
- 来源拆分 CSV：`research/hype/cross-strategy-account/artifacts/hype_pbtr_v621_mii_v13_shared_account_sources_2026-07-02.csv`
- 阻塞矩阵 CSV：`research/hype/cross-strategy-account/artifacts/hype_pbtr_v621_mii_v13_shared_account_blocks_2026-07-02.csv`
- 成交明细 CSV：`research/hype/cross-strategy-account/artifacts/hype_pbtr_v621_mii_v13_shared_account_trades_2026-07-02.csv`
- JSON：`research/hype/cross-strategy-account/artifacts/hype_pbtr_v621_mii_v13_shared_account_2026-07-02.json`
