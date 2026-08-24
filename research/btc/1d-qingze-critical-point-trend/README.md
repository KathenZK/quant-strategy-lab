# BTC-1D-Qingze-Critical-Point-Trend

- Full family name：`BTC-1D-Qingze-Critical-Point-Trend`
- Alias：`BTC-1D-QZ-CPT`
- Market：Binance USD-M `BTCUSDT` perpetual
- Timeframe：UTC `1d`（由可信 `1h` 聚合）
- Mechanism：SMA55/60 过滤方向，放量突破“临界点”后次日开盘试仓，浮盈后正金字塔加码，以宽 ATR 追踪止损退出
- Status：`explore / diagnostic-only / not promoted / not live-ready`

本家族是对用户提供的“青泽顺势 + 临界点突破”叙述所做的可执行化诊断；由于本地持仓量只有 8 天覆盖，当前基线没有把 20 日持仓量高位过滤器伪装为已验证规则。

## 入口

- [主账](btc-1d-qz-cpt-core-ledger.md)
- [决策记录](decision-log.md)
- [基线合同](specs/btc-1d-qz-cpt-baseline-contract-2026-08-07.md)
- [回测诊断](diagnostics/btc-1d-qz-cpt-baseline-2026-08-07.md)
- [参数搜索合同](specs/btc-1d-qz-cpt-parameter-search-contract-2026-08-07.md)
- [参数搜索锁定验证](diagnostics/btc-1d-qz-cpt-parameter-search-validation-2026-08-07.md)
- [产物说明](artifacts/README.md)
- [复现脚本](scripts/research_btc_1d_qingze_critical_point.py)
- [搜索脚本](scripts/search_btc_1d_qingze_parameters.py)
