# Binance 1D MA7/MA30 浮盈加仓 BTC/ETH 直迁（2026-07-30）

## 结论

HYPE MA7/MA30 纯收益 observation 原参数直接迁移到 BTCUSDT、ETHUSDT 后失败。

在与 HYPE 完全相同的 `2025-05-31 00:00 UTC` 至 `2026-07-30 00:00 UTC` 共同窗口中：

- BTC 权益为 `0.6992x`，年化因子 `0.7353x`，保守 MDD `-63.88%`；
- ETH 权益为 `0.7865x`，年化因子 `0.8135x`，保守 MDD `-62.25%`；
- 两者均没有通过年化因子严格 `>20x`、MDD `<=20%` 的硬目标；
- BTC/ETH 下单目标最大杠杆均为 `3x`，但有效开盘杠杆分别最高漂移到 `5.37x`、`4.18x`，仍不满足“任何时刻最大 3 倍”的风险语义。

因此 direct-transfer 判定为 **NO-GO（研究决策语义）**。本家族保持 `explore / not promoted / not live-ready`，不登记版本、不交接 runner。

## 冻结与数据

本次在查看 BTC/ETH 策略结果前冻结来源配置，不搜索、不变异、不根据目标资产挑参数。完整参数与执行合同见[冻结迁移契约](../specs/binance-1d-ma7-ma30-pyramiding-transfer-contract-2026-07-30.md)。

BTC/ETH 数据均于 `2026-07-30` 从 Binance USD-M Futures API 刷新：

| 项目 | BTCUSDT | ETHUSDT |
| --- | ---: | ---: |
| 已收盘 `1h` K | 17,520 | 17,520 |
| `1h` 范围 | 2024-07-30 10:00 – 2026-07-30 09:00 UTC | 同左 |
| 缺失/重复/关键空值/OHLC 异常 | 0 | 0 |
| raw/normalized 未匹配或数值差异 | 0 | 0 |
| funding rows | 2,190 | 2,190 |
| 完整 UTC 日 K | 729 | 729 |
| 日线范围 | 2024-07-31 – 2026-07-29 | 同左 |
| data-quality blocker | 0 | 0 |

成本为每次实际成交手续费 `0.001`、基础不利滑点 `4 bps`、实际 funding；另审计 `8 bps` 与 `K+2`。信号在日 K 收盘确认，下一日 open 成交；止损使用前一收盘即可确定的价格，跳空穿越时按 open。

## 共同窗口结果

共同窗口用于与 HYPE 来源结果直接比较，共 `425` 日：

| 资产 | 权益倍数 | 年化因子 | 保守 MDD | campaign | 胜率 | PF | 加仓 | 最高有效开盘杠杆 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HYPE 来源 | `29.4589x` | `18.3089x` | `-63.38%` | 15 | `73.33%` | 9.977 | 12 | `6.86x` |
| BTC | `0.6992x` | `0.7353x` | `-63.88%` | 16 | `31.25%` | 1.006 | 12 | `5.37x` |
| ETH | `0.7865x` | `0.8135x` | `-62.25%` | 19 | `26.32%` | 1.273 | 12 | `4.18x` |

共同窗口的 buy-and-hold 倍数分别为 BTC `0.6153x`、ETH `0.7549x`。策略相对同期简单持有略有改善，但绝对收益仍为负，不能据此称为合格 alpha。

### 压力与延迟

| 资产 | `8 bps` 年化因子 / MDD | `K+2` 年化因子 / MDD |
| --- | ---: | ---: |
| BTC | `0.7156x / -64.08%` | `0.7542x / -52.14%` |
| ETH | `0.7914x / -62.67%` | `0.5494x / -73.37%` |

ETH 的 `K+2` 进一步恶化至净亏约 `-50.18%`；BTC 延迟版本虽然 MDD 略低，仍为显著亏损。不存在延迟稳健性证据。

## 两年扩展窗口

扩展窗口为 `2024-07-31` 至 `2026-07-30 UTC`，共 `729` 日：

| 资产 | 权益倍数 | 年化因子 | 保守 MDD | campaign | 胜率 | PF | 加仓 | 最高有效开盘杠杆 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BTC | `1.0929x` | `1.0455x` | `-75.38%` | 26 | `34.62%` | 1.443 | 18 | `5.37x` |
| ETH | `2.4512x` | `1.5671x` | `-63.68%` | 28 | `35.71%` | 1.873 | 19 | `4.27x` |

BTC 两年累计只盈利 `9.29%`，ETH 累计盈利 `145.12%`，但二者 MDD 都超过 `60%`，年化因子远低于 `20x`。扩展窗口没有挽救迁移结论。

## 最近切片

两年路径终点锚定的开盘权益切片：

| 资产 | 1m | 3m | 6m | 1y |
| --- | ---: | ---: | ---: | ---: |
| BTC | `-24.55%` | `+19.25%` | `-10.82%` | `-31.63%` |
| ETH | `-19.57%` | `-20.61%` | `+0.40%` | `+13.84%` |

BTC 最近一个月开盘路径 MDD 为 `-30.23%`；ETH最近三个月开盘路径 MDD 为 `-40.98%`。近期切片同样没有形成稳定迁移证据。

## 路径解释

- HYPE 来源的优势主要来自少数 20 日大趋势，15 个 campaign 中胜率 `73.33%`；BTC/ETH 的共同窗口胜率仅 `31.25%`、`26.32%`。
- 目标资产仍会在很小浮盈后从 `0.5x` 直接重置到 `3x`。趋势失败后，固定数量仓位令权益缩水、有效杠杆被动升高，放大尾部回撤。
- BTC 共同窗口最大回撤在 `2026-04-08` 首次达到 `-63.88%`，当日开盘有效杠杆约 `4.33x`；ETH 最大回撤在 `2026-07-13` 首次达到 `-62.25%`。
- BTC/ETH 两年 PF 大于 1 并不等于可用：低胜率、复利路径、成本与深回撤共同使风险收益不合格。

## 决策

1. 不把 HYPE 纯收益 observation 直接用于 BTC 或 ETH。
2. 不在本 transfer 家族内继续调 BTC/ETH 参数；否则会把 direct-transfer test 变成揭示后优化。
3. 若用户希望继续，BTC 和 ETH 应分别建立独立日线家族、在搜索前冻结目标资产验证边界，再搜索适合各自波动结构的加仓与退出规则。
4. 来源 HYPE observation 也仍是 `explore / not promoted / not live-ready`；本次迁移失败进一步说明其高收益是资产/样本特异路径，不是可直接泛化的 MA7/MA30 alpha。

机器证据见[汇总 JSON](../artifacts/binance-1d-ma7-ma30-pyramiding-transfer-summary-2026-07-30.json)、[汇总 CSV](../artifacts/binance-1d-ma7-ma30-pyramiding-transfer-summary-2026-07-30.csv)、[逐交易 CSV](../artifacts/binance-1d-ma7-ma30-pyramiding-transfer-trades-2026-07-30.csv)与[逐日路径 CSV](../artifacts/binance-1d-ma7-ma30-pyramiding-transfer-path-2026-07-30.csv)。复现脚本见[research_binance_1d_ma7_ma30_pyramiding_transfer.py](../scripts/research_binance_1d_ma7_ma30_pyramiding_transfer.py)。

复现命令：

```bash
uv run python research/asset-portfolios/1d-ma7-ma30-pyramiding-transfer/scripts/research_binance_1d_ma7_ma30_pyramiding_transfer.py \
  --run-date 2026-07-30
```
