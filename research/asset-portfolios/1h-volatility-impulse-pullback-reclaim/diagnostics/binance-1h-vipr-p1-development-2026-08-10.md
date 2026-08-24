# BIN-1H-VIPR P1 Development 诊断

## 结论

八个预冻结配置全部在 development 硬门失败，locked holdout 按合同保持未揭示。原生 `1h` volatility-normalized breakout 加显式 pullback/reclaim 仍没有跨资产正经济性；本轮不生成 frozen strategy、不读取 HYPE、不允许在同一网格继续调参。

状态：`HARD-GATE-FAILED / explore / not promoted / not live-ready`。

## 数据与防泄漏

- 市场：Binance USD-M perpetual；BTC/ETH/BNB/SOL/TRX。
- 输入：direct `1h` OHLCV 与官方 funding/mark，缺 K、重复、闭合状态、日线重建和输入 SHA 均沿共享数据内核审计。
- Development roots 的 signal timestamp 严格早于 `2024-05-25 UTC`，结果数据严格早于 `2024-06-01 UTC`。
- Locked holdout 为 `[2024-06-01, 2025-05-20) UTC` roots；因无 development 合格配置，脚本没有运行 holdout。
- HYPE rows consumed / files opened 均为 `0`。

## 八配置结果

全部配置都通过样本容量，但其余四项 development 门全灭：主经济性、正资产数、正 `180d` block 与 cluster bootstrap 均失败。

| 配置 | 成交 | 平均每笔 | PF | 胜率 | 正资产 | 正 block |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `N24/I1.0/P0.5` | 3,618 | `−0.0940%` | 0.652 | 31.70% | 0/5 | 0% |
| `N24/I1.0/P1.0` | 3,275 | `−0.0853%` | 0.677 | 32.00% | 0/5 | 0% |
| `N24/I1.5/P0.5` | 3,278 | `−0.0910%` | 0.661 | 31.97% | 0/5 | 0% |
| `N24/I1.5/P1.0` | 3,007 | `−0.0835%` | 0.683 | 31.89% | 0/5 | 0% |
| `N72/I1.0/P0.5` | 1,813 | `−0.0995%` | 0.645 | 31.00% | 0/5 | 0% |
| `N72/I1.0/P1.0` | 1,663 | `−0.0828%` | 0.693 | 32.29% | 0/5 | 0% |
| `N72/I1.5/P0.5` | 1,692 | `−0.0916%` | 0.669 | 31.62% | 0/5 | 0% |
| `N72/I1.5/P1.0` | 1,561 | `−0.0748%` | 0.720 | 32.86% | 0/5 | 0% |

收益为固定 `0.25x`、fee `0.001/fill`、`4bps/fill` adverse slippage 与 actual funding 后结果。最好的配置仍未接近 PF `1.05`，不存在“只差一个阈值”的边缘。

## 失败归因

1. **局部价格确认没有提供正条件优势**：从 MA7 maturity、逐小时 hazard 到原生 breakout/pullback，三条只依赖标的自身路径的机制连续失败。
2. **固定 2R bracket 的命中率不足**：八配置胜率仅 `31.0%–32.9%`，且所有资产、所有 180 日块均为负；不是单一阶段或资产拖累。
3. **增加 pullback 深度只略减亏**：`1.0 ATR` 比 `0.5 ATR` 稍好，但 PF 仍只有 `0.677–0.720`，不足以支持在已揭示 development 中继续加深网格。
4. **Holdout 未被污染**：没有合格 development 配置，因此未产生 selected config、holdout trades 或 holdout summary。

## 决定

- 本轮 `HARD-GATE-FAILED`；同一八配置及其 lookback/impulse/pullback/bracket 邻域停止。
- 不把未揭示 holdout 当作未来可反复试验的救援区；任何新机制仍需新合同。
- 下一轮只研究与局部价格路径独立的信息：open interest、top-trader/global positioning、taker long/short flow、basis/premium 或跨资产相对状态。若这些信息仍无严格 OOF 增量，则应确认“漏趋势识别”在现有样本中不可因果区分，而不是继续制造技术指标。

## 证据

- [P0/P1 预冻结合同](../specs/binance-1h-vipr-p0-p1-contract-2026-08-10.md)
- [数据质量](../artifacts/p1_development_2026-08-10/p0_data_quality.json)
- [Development roots](../artifacts/p1_development_2026-08-10/p1_development_roots.parquet)
- [Development trades](../artifacts/p1_development_2026-08-10/p1_development_trades.parquet)
- [摘要](../artifacts/p1_development_2026-08-10/p1_summary.json)
- [完整报告](../artifacts/p1_development_2026-08-10/p1_report.json)
- [证据 manifest](../artifacts/p1_development_2026-08-10/manifest.json)
- [研究脚本](../scripts/research_binance_1h_vipr_p1.py)
- [回归测试](../../../../tests/test_binance_1h_vipr_p1.py)
