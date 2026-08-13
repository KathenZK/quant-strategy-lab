# BIN-1D-MA7-RSI6-DAPML P0 数据与事件容量审计

## 结论

P0 通过。BTC、ETH、BNB、SOL、TRX 的 direct `1h`、24 小时聚合 UTC 日线、官方 funding 与 `1h` mark 均无质量 blocker；development 共形成 `2,091` 个完整成本后标签事件，足以进入冻结的 pooled P1。

本报告没有训练模型、读取 sealed period 特征或产生策略收益结论。

## 数据范围

| Asset | Development 日线 | Development 起点 | 截止 | Events |
| --- | ---: | --- | --- | ---: |
| BTC | 2,159 | 2019-09-09 | 2025-08-06 | 449 |
| ETH | 2,079 | 2019-11-28 | 2025-08-06 | 458 |
| BNB | 2,004 | 2020-02-11 | 2025-08-06 | 389 |
| SOL | 1,787 | 2020-09-15 | 2025-08-06 | 362 |
| TRX | 2,030 | 2020-01-16 | 2025-08-06 | 433 |

- 市场：Binance USD-M perpetual
- signal：完整 UTC `1d`
- stop path：direct `1h`
- 成本：每 fill fee `0.001`、不利 slippage `4 bps`、官方实际 funding
- sealed：五资产均保留 `2025-08-07` 至 `2026-08-06` 的 365 根日线，P0 模型消费数为 `0`
- 选择用途：本阶段只审计数据和事件容量

## 质量审计

- 五资产 `1h` 均为连续 24/7 网格，duplicate、missing、unexpected interval、open row 和 OHLC mismatch 均为 `0`。
- 日线只接受恰有 24 根完整小时 K 的 UTC 日；合约首个不完整日与抓取当日被明确排除。
- funding timestamp 均在实际 UTC 小时后 `0–0.047s` 内。
- SOL 实际包含 `98` 个 `2h` interval、`3` 个 `4h` interval 和 `6,442` 个 `8h` interval；这是 Binance 历史结算制度变化，不是缺 K。固定 `8h` 假设已在标签生成前撤销。
- funding endpoint 与 `1h` mark overlap 的价格差异已保留在 manifest；所有 resolved mark 为正、无重复、无关键空值，相邻实际 funding 事件不超过 `8h`。

## 事件容量

| Asset | Long | Short | Positive rate | All-cross mean net return |
| --- | ---: | ---: | ---: | ---: |
| BTC | 224 | 225 | 27.62% | −0.348% |
| ETH | 229 | 229 | 27.51% | −0.307% |
| BNB | 195 | 194 | 30.08% | +0.179% |
| SOL | 181 | 181 | 34.81% | +0.321% |
| TRX | 216 | 217 | 29.10% | −0.223% |
| Total | 1,045 | 1,046 | 29.60% | −0.099% |

这些数值只是独立 all-cross 事件标签分布；跨资产同时持仓、总杠杆和组合 MDD 尚未建模，不能解释为可交易组合。

事件 identity：

```text
rows=2091
sha256=c9bdf1d4e32fa85f11b6b2d5e9de3062d05489acef8ddc68497bfd3a65970b83
```

## 决定

冻结 [P1 pooled development 合同](../specs/binance-1d-ma7-rsi6-dapml-p1-pooled-development-contract-2026-08-10.md)，只在 development 内运行 pooled temporal OOS、leave-one-asset + time OOS 和方向对齐消融。BTC 及其他资产的共同 sealed year 继续不揭示。

## 证据

- [P0 数据质量 manifest](../artifacts/p0_data_2026-08-10/p0_data_quality_manifest.json)
- [P0 事件容量 JSON](../artifacts/p0_data_2026-08-10/p0_event_capacity.json)
- [P0 数据与特征合同](../specs/binance-1d-ma7-rsi6-dapml-p0-data-feature-contract-2026-08-10.md)
- [数据同步脚本](../scripts/sync_binance_pooled_p0_data.py)
- [Pooled 事件与模型脚本](../scripts/research_binance_1d_ma7_rsi6_dapml_p1.py)
