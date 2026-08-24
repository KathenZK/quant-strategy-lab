# Binance 1D MA7 P2-C Long Pullback Episode 归因

## 结论

long `pullback_reclaim` 的新增 long episode 在 BTC、ETH 上都是真实正贡献来源，但当前退出/保护链无法控制跨 regime 尾部风险。支持下一轮的跨资产共同因果只有两项：

1. 亏损单入场后显著逆行，而盈利单很少触及 `-2 ATR`；
2. 进入 `ma7_hysteresis_exit` 的交易在两资产上都系统性亏损。

不支持优先测试的假设是“短 flat gap 重入”“高 trend age”与“盈利后回吐”：这些分组在 BTC/ETH 上不一致，且多数亏损单在达到 `1 ATR` MFE 前已经失败。

因此下一轮只冻结 `2 ATR` long initial hard stop、`close<MA7` 单日结构破坏退出及二者组合；不搜索阈值、不测试 profit protection、不打开 researcher-exposed audit。

## 冻结范围

- 合同：[P2-C 归因合同](../specs/binance-1d-ma7-p2c-long-pullback-episode-attribution-contract-2026-08-12.md)
- 数据：P2 冻结 BTC/ETH direct `1h` + 实际 funding/mark
- 窗口：`2019-12-24` 至 `2025-08-07` exclusive，development-only
- Probe：long 仅 `entry_mode: reclaim -> pullback_reclaim`；其它参数和 short exact V1
- audit/prospective：未读取

## 账户级与 long-only 结果

| Asset | Path | Equity | MDD | Trades | PF |
| --- | --- | ---: | ---: | ---: | ---: |
| BTC | V1 combined | `1.2235x` | `-60.41%` | 81 | `1.096` |
| BTC | Probe combined | `6.3164x` | `-52.80%` | 117 | `1.395` |
| BTC | V1 long-only | `0.5494x` | `-74.13%` | 44 | `0.576` |
| BTC | Probe long-only | `3.1997x` | `-70.96%` | 83 | `1.311` |
| ETH | V1 combined | `2.2988x` | `-65.67%` | 80 | `1.413` |
| ETH | Probe combined | `6.0161x` | `-56.76%` | 116 | `1.301` |
| ETH | V1 long-only | `1.3238x` | `-71.03%` | 45 | `1.165` |
| ETH | Probe long-only | `5.2934x` | `-62.93%` | 80 | `1.277` |

Probe combined 的累计 turnover 达 BTC `790.1x`、ETH `732.9x`；成本相对初始权益累计为 `110.6% / 102.6%`。收益仍为正，但高换手与巨大回撤说明不能把约 `6x` 终值视为可直接冻结的 alpha。

## Added-entry 贡献

| Asset | Group | Trades | Win rate | Compound factor | Median return | Median MFE | Median MAE |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | Added | 64 | `32.81%` | `4.9166x` | `-3.14%` | `1.22 ATR` | `-1.20 ATR` |
| BTC | Native | 19 | `26.32%` | `0.6508x` | `-2.93%` | `1.35 ATR` | `-1.50 ATR` |
| ETH | Added | 65 | `36.92%` | `2.8501x` | `-2.76%` | `1.69 ATR` | `-1.55 ATR` |
| ETH | Native | 15 | `33.33%` | `1.8573x` | `-2.95%` | `0.91 ATR` | `-1.14 ATR` |

两资产 added-entry 都有正复合贡献，说明不应回退到原 V1 稀疏 long reclaim。它们依赖少数大趋势盈利，median trade 仍为负，因此必须保护尾部而不能按胜率删除全部 added entry。

## MAE/MFE 因果证据

| Asset | Losers | Loser median MAE | Winners | Winner median MAE | Losers breach `-2 ATR` | Winners breach `-2 ATR` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | 57 | `-1.62 ATR` | 26 | `-0.30 ATR` | `22/57` | `1/26` |
| ETH | 51 | `-1.84 ATR` | 29 | `-0.44 ATR` | `24/51` | `0/29` |

`2 ATR` 不是通过扫描收益选出的最优点，而是跨资产 winner/loser MAE 分布的共同分离点。它有资格作为下一合同中的单一 initial hard-stop 机制臂，但历史分离不保证回测 MDD 一定合格。

Profit protection 不是主要修复方向：BTC/ETH 亏损单中只有 `19/57`、`19/51` 曾达到 `>=1 ATR` MFE；大亏损（`<=-8%`）中只有 `4/11`、`5/22` 曾达到该水平。多数损失并非“先大赚再回吐”。

## Exit 归因

| Asset | Exit | Trades | Win rate | Compound factor | Median MFE | Median MAE |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| BTC | `ma7_hysteresis_exit` | 12 | `8.33%` | `0.485x` | `1.22 ATR` | `-1.69 ATR` |
| BTC | `ma7_slope_exit` | 71 | `35.21%` | `6.592x` | `1.22 ATR` | `-1.13 ATR` |
| ETH | `ma7_hysteresis_exit` | 14 | `14.29%` | `0.328x` | `0.65 ATR` | `-2.42 ATR` |
| ETH | `ma7_slope_exit` | 66 | `40.91%` | `16.121x` | `1.88 ATR` | `-1.18 ATR` |

现有 long `2d + 1 ATR` 迟滞退出允许结构已经跌破 MA7 后继续承受风险。下一轮固定测试单日 `close<MA7` 退出，目的是删除已证实的迟滞尾部，不是搜索最佳 buffer。

## Regime 与 loss clusters

- 两资产共同最弱年份均为 `2022`：BTC long-only 该年复合约 `0.522x`，ETH 约 `0.562x`。
- BTC 最大连续亏损簇为 `2022-06-01` 至 `2022-12-30`，12 笔合计 `-49.62%`，其中 11 笔 slope exit。
- ETH 在 `2020-09`、`2022`、`2024-12` 至 `2025-04` 均出现约 `-25%` 至 `-36%` 簇，不是单一年份异常。
- trend-age 与 flat-gap 分桶没有跨资产单调关系：例如 ETH `3–5d` flat gap 很强，而 BTC 同桶接近持平；禁止据此冻结共享 cooldown/re-entry 阈值。

## 裁决

- Added-entry 是否有跨资产正贡献：`YES`
- 失败是否主要由 profit giveback 解释：`NO`
- `2 ATR` initial stop 是否有跨资产分布依据：`YES`
- 单日 `close<MA7` 结构退出是否有跨资产退出依据：`YES`
- cooldown/trend-age shared gate 是否有共同依据：`NO`
- P2-C 状态：`ATTRIBUTION_COMPLETE / explore / not promoted / not live-ready`

下一轮按已冻结的 P2-D 三个单项/组合机制臂运行 development-only；不增加其它阈值。

## 机器证据

- [主 JSON](../artifacts/binance_1d_ma7_p2c_long_pullback_episodes_2026-08-12.json) — SHA256 `c39857207016953ec06cb44beea698e4ea11a64c4f81808df155cfa41e4e462b`
- [逐笔 episode](../artifacts/binance_1d_ma7_p2c_long_pullback_episodes_2026-08-12_trades.csv) — SHA256 `25da175ca2bf3dd8c2c9cc5195cd02bed744287160e4928f0b31b1e8e662e03c`
- [分组汇总](../artifacts/binance_1d_ma7_p2c_long_pullback_episodes_2026-08-12_groups.csv) — SHA256 `5f01dbdc80756ea3c4da0eaa90e13dba894e34aeb1f035c82a6fcd99bb547cb0`
- [连续亏损簇](../artifacts/binance_1d_ma7_p2c_long_pullback_episodes_2026-08-12_loss_clusters.csv) — SHA256 `56aa80492f09e259ad39c69c195bd394d71d2ea57731cb0aeb135462921c5371`
- [复现脚本](../scripts/audit_binance_1d_ma7_p2c_long_pullback_episodes.py)

