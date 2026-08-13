# HYPE-4H-MA7-Asymmetric-Body-Trend

- Alias：`HYPE-4H-MA7-ABT`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `4h`
- 机制：固定 `SMA7/ATR7` 的斜率趋势、reclaim / pullback / breakout 入场、迟滞退出与保护状态机；覆盖日线 V1 直迁和原生 4H 参数搜索。
- 当前状态：`explore / not promoted / not live-ready`；直迁失败；原生搜索 locked 绝对收益为正，但超额、延迟与相位门槛失败。

## 边界

- 这是独立 4H 家族，不是 `HYPE-1D-MA7-Asymmetric-Body-Trend-V1` 的新版本。
- 不与 `HYPE-4H-Bollinger-Keltner-Squeeze-Breakout`、`HYPE-6H-RS4-Regime-Switch` 或其他 HYPE 趋势家族共享版本号。
- 当前结果是已揭示历史的 direct-transfer diagnostic，不是 OOS。

## 入口

- [主账](hype-4h-ma7-abt-core-ledger.md)
- [决策记录](decision-log.md)
- [迁移合同](specs/hype-4h-ma7-source-v1-transfer-contract-2026-08-05.md)
- [迁移诊断](diagnostics/hype-4h-ma7-source-v1-transfer-2026-08-05.md)
- [原生搜索合同](specs/hype-4h-ma7-native-trend-search-contract-2026-08-06.md)
- [原生搜索诊断](diagnostics/hype-4h-ma7-native-trend-search-2026-08-06.md)
- [直迁脚本](scripts/research_hype_4h_ma7_v1_transfer.py) · [原生搜索脚本](scripts/search_hype_4h_ma7_native_trend.py)
- [机器证据](artifacts/README.md)
