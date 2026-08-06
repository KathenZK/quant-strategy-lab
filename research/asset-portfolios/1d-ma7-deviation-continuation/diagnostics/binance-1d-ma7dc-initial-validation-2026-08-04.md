# Binance 1D MA7 延续与偏离初始验证

## 结论

**日线 MA7 比上一轮复杂价格运动学更接近一个清晰、可解释的趋势量尺，但它不是 HYPE/BTC/ETH 三币通用规律。**

- `BTC long`：四项预声明门禁通过两项，证据为 `partial`。MA7 向上具有成本后延续和相对无条件上涨漂移的增量；MA7 斜率强度对未来 14 日有稳定正排序。它是唯一值得进入第二阶段的方向。
- `ETH long`：只通过 restart 增量一项，证据为 `not supported`。全样本平均终值好看，但 7 日四块只有两块成本后为正，斜率 IC 的 bootstrap 区间跨零；不能把长期上涨漂移和少数趋势段当成稳定 MA7 alpha。
- `HYPE long/short`：四项门禁均未通过。MA7 方向、斜率、偏离形状和 restart 都没有稳定延续证据；HYPE“看起来趋势明显”仍未转化为可预测的日线延续。
- 三资产 short 均未通过；MA7 不能按多空对称规则使用。

本轮没有订单或策略收益，只有重叠日锚的未来路径诊断。家族保持 `explore / not promoted / not live-ready`，不登记版本、不写 live spec。

## 1. 数据与时序

数据来自 Binance USD-M 标准数据湖，15m normalized 与 raw parity 全部通过；先聚合完整 1h，再聚合完整 UTC 日。日线索引是上一完整 UTC 日结束后最早可知的午夜。

| 资产 | 完整日 K | 可见起点 | 可见终点 | 日线缺口 | OHLC 违规 | 质量结论 |
| --- | ---: | --- | --- | ---: | ---: | --- |
| HYPE | 429 | 2025-06-01 | 2026-08-03 | 0 | 0 | accepted |
| BTC | 2,520 | 2019-09-10 | 2026-08-03 | 0 | 0 | accepted |
| ETH | 2,440 | 2019-11-29 | 2026-08-03 | 0 | 0 | accepted |

所有状态只使用当时已闭合的最近 7 根日 K。未来 `1d/3d/7d/14d` high、low、close 只生成标签；不足完整 horizon 的尾部保持 unknown。

证据：[数据质量 JSON](../artifacts/binance_1d_ma7dc_data_quality_2026-08-04.json)。

## 2. 固定定义

```text
MA7 = 最近 7 根完整日收盘的 SMA
direction = sign(MA7_t - MA7_t-1)
slope_strength = abs(MA7_t - MA7_t-1) / ATR7
signed_deviation = direction × (Close - MA7) / ATR7
deviation_velocity = direction × change((Close - MA7) / ATR7)
```

`restart` 要求 MA7 方向连续两日一致、价格仍在顺趋势一侧、前一日偏离收缩而当日重新扩大。默认往返空间门槛为 `2 × (0.1% fee + 4 bps slippage) = 0.28%`；它只用于未来空间诊断，不代表真实成交回测。

完整口径见[冻结合同](../specs/binance-1d-ma7dc-initial-validation-contract-2026-08-04.md)。

## 3. 预声明门禁结果

下表的 `7d/14d net` 是每个日锚未来顺趋势对数终值减去 0.28% 门槛后的平均值；日锚相互重叠，不能解释为策略收益率。

| 资产/方向 | 方向延续 | 斜率增量 | 中等偏离优于两端 | restart 增量 | 7d net | 14d net | 相对无条件同向增量 7d / 14d | 证据 |
| --- | --- | --- | --- | --- | ---: | ---: | ---: | --- |
| HYPE long | FAIL | FAIL | FAIL | FAIL | -0.90% | -1.14% | -1.16% / -2.13% | not supported |
| HYPE short | FAIL | FAIL | FAIL | FAIL | -1.92% | -3.66% | -1.11% / -2.11% | not supported |
| BTC long | PASS | PASS | FAIL | FAIL | +0.43% | +1.21% | +0.20% / +0.40% | **partial** |
| BTC short | FAIL | FAIL | FAIL | FAIL | -0.57% | -0.92% | +0.22% / +0.44% | not supported |
| ETH long | FAIL | FAIL | FAIL | PASS | +0.77% | +1.96% | +0.31% / +0.74% | not supported |
| ETH short | FAIL | FAIL | FAIL | FAIL | -0.67% | -0.97% | +0.34% / +0.81% | not supported |

BTC/ETH short 虽然相对“无条件一直做空”略有改善，但绝对成本后终值仍为负，因此没有可交易含义。

证据：[门禁 CSV](../artifacts/binance_1d_ma7dc_gate_summary_2026-08-04.csv) · [beta 基准 CSV](../artifacts/binance_1d_ma7dc_baseline_metrics_2026-08-04.csv)。

## 4. MA7 斜率是否有效

### BTC long

- 7 日 slope-strength IC `0.0796`，14 日 IC `0.1124`；
- 7 日 bootstrap 95% CI `[-0.0203, 0.1693]`，仍跨零；
- 14 日 CI `[0.0224, 0.1974]`，下界为正；
- 14 日四个连续时间块 IC 全为正。

这是本轮最清楚的结果：**BTC 日线 MA7 向上时，斜率越强，未来 14 日继续上涨的排序越明显。**效应不大，但比复杂 continuation score 更直接、更稳定。

### ETH long

7 日/14 日 IC 为 `0.0588/0.0784`，但 CI 分别为 `[-0.0406,0.1564]`、`[-0.0145,0.1693]`，均跨零；只有方向提示，没有稳健增量授权。

### HYPE long

7 日/14 日 IC 为 `-0.0590/-0.1166`，方向与“斜率越强越延续”相反。当前 HYPE 日线历史不支持该假设。

证据：[feature metrics](../artifacts/binance_1d_ma7dc_feature_metrics_2026-08-04.csv)。

## 5. 偏离形状：原假设被否定

预声明假设是“中等偏离最健康，最高偏离开始衰竭”。结果没有成立：

- BTC long 的最高偏离 `Q5` 在 7 日/14 日均最好，成本后平均终值 `+1.52%/+3.05%`；
- ETH long 的 `Q5` 同样最好，为 `+1.95%/+3.38%`；
- HYPE long 7 日最好的是 `Q4 +1.02%`，到 14 日变成 `-0.64%`，没有延续。

这意味着在 BTC/ETH 的历史多头阶段，**远离 MA7 更像趋势强度，而不是自动意味着阶段顶部**。但是这个结果不能直接变成追高规则：

1. BTC long 的 `Q5` 7 日成本后终值在四块分别为 `+3.73%/+0.57%/+1.65%/-0.22%`，最近块已经转负；
2. ETH long 分别为 `+2.70%/+3.38%/+1.74%/+0.06%`，最近块几乎降到零；
3. BTC/ETH 的 signed-deviation IC 虽为正，但 bootstrap CI 仍跨零；
4. 当前历史已经揭示，`Q5` 是新发现，不是预声明通过项，不能用同一历史继续挑阈值并宣称 OOS 成立。

因此，原“中间高、两边低”的理论失败；替代观察是“BTC/ETH long 偏离越大越可能仍处于强趋势”，但它正在近期衰减，只能作为下一轮假设。

证据：[偏离 quintile](../artifacts/binance_1d_ma7dc_deviation_quintiles_2026-08-04.csv) · [四块审计](../artifacts/binance_1d_ma7dc_block_metrics_2026-08-04.csv)。

## 6. 回调后 restart 是否更好

| 资产 long | 7d restart / expansion net | 14d restart / expansion net | 判断 |
| --- | ---: | ---: | --- |
| HYPE | -3.69% / -1.28% | -2.33% / -3.20% | restart 失败 |
| BTC | +1.21% / +0.89% | +2.38% / +2.47% | 7 日改善、14 日不改善 |
| ETH | +1.63% / +0.52% | +2.50% / +1.89% | 平均终值改善 |

ETH restart 通过了预声明增量门，但 first-passage 成功率反而只有约 `27.6%`，低于 expansion 的约 `34.7%–35.2%`。它更像少数大赢家拉高平均值，而不是“回调重启提高胜率”。BTC 也没有同时通过两个 horizon。

因此不能把“回调后重新扩张”写成三币通用入场规律；它最多是 ETH long 的正偏候选状态。

证据：[state metrics](../artifacts/binance_1d_ma7dc_state_metrics_2026-08-04.csv)。

## 7. 近期与稳定性

以最后一个具备完整 7 日标签的 `2026-07-27 UTC` 为锚，所有 MA7 方向合并后的未来 7 日成本后平均值：

| 资产 | 最近 1m | 最近 3m | 最近 6m | 最近 1y |
| --- | ---: | ---: | ---: | ---: |
| HYPE | +1.98% | -0.96% | -0.74% | -1.63% |
| BTC | -1.15% | +0.61% | +1.24% | +0.23% |
| ETH | -0.97% | +0.62% | +0.80% | -0.71% |

这些仍是重叠未来路径，不是可累加 PnL。它们说明近期一个月三资产均没有稳定的全方向 MA7 优势，不能根据全历史均值直接上线。

证据：[近期切片](../artifacts/binance_1d_ma7dc_recent_slices_2026-08-04.csv)。

## 8. 回答研究问题

### 日线 MA7 能不能更有效地度量趋势？

**可以，但只得到局部答案：BTC 多头的 MA7 方向与斜率是当前最可信的简单趋势量尺；ETH 多头只有弱证据；HYPE 与全部空头没有验证。**

### 偏离越大是否越危险？

当前 BTC/ETH 历史恰好相反：最高偏离档后续收益最好。可是最近块显著衰减，所以不能立即据此追高。

### 回调重启是否是更好的入场？

不是通用规律。ETH long 的平均终值改善，但胜率没有改善；BTC 不跨两个 horizon；HYPE 失败。

### 是否已经能形成策略？

不能。本轮没有验证入场成交、持仓、退出和仓位风险；所有历史均是 researcher-exposed diagnostic。当前只有 `BTC long` 取得进入第二阶段的资格。

## 9. 下一步边界

若继续，建议只建立一个窄实验：`BTC long-only SMA7 slope/deviation campaign`。

- 主状态只使用日线 MA7 向上、斜率强度和 signed deviation；
- `ETH long` 作为外部控制，HYPE/short 不参与参数选择；
- 固定比较“直接小 probe”与“等 1h 回调、15m restart”两条执行臂，不再搜索 MA 长度；
- 不把 `Q5` 阈值在当前已揭示历史上继续精调；先用 expanding rank 固定定义，再建立新的 prospective OOS；
- 只有真实 next-open/next-15m 成交、默认成本、逐时止损和风险账本通过后，才讨论加仓。

## 10. 复现

```bash
cd /Users/ZK/OpenCode/quant-strategy-lab
.venv/bin/python research/asset-portfolios/1d-ma7-deviation-continuation/scripts/research_binance_1d_ma7dc.py
.venv/bin/pytest -q tests/test_binance_1d_ma7dc.py
```

当前同一家族测试结果：`12 passed`。
