# Binance-1D-MA7-Deviation-Continuation

- Full family：`Binance-1D-MA7-Deviation-Continuation`（alias：`BIN-1D-MA7DC`）。
- 市场/周期：Binance USD-M perpetual；HYPEUSDT、BTCUSDT、ETHUSDT；完整 UTC `1d`。
- 机制：固定 `SMA7`，独立验证均线斜率、价格相对均线的 ATR 归一化偏离、偏离收缩/扩张与回调后重新扩张，能否排序未来 `1d/3d/7d/14d` 延续、MFE、MAE 与 first-passage。
- 当前状态：`explore / not promoted / not live-ready`；本阶段仅做 diagnostic，不产生订单、版本或 runner。

## 边界

- 独立于 `HYPE-1D-Pyramiding-Trend` 的 MA7/MA30 交叉/reclaim 搜索，也不是旧参数向 BTC/ETH 的直迁。
- `SMA7` 长度冻结，不搜索 MA 长度；BTC、ETH、HYPE 分开判断，不要求同一结果或同一未来交易参数。
- 历史均已被研究者查看，只能作为 diagnostic evidence；若形成候选，仍需新的 prospective OOS。

## 入口

- [主账](binance-1d-ma7dc-core-ledger.md)
- [决策记录](decision-log.md)
- [冻结验证合同](specs/binance-1d-ma7dc-initial-validation-contract-2026-08-04.md)
- [初始验证报告](diagnostics/binance-1d-ma7dc-initial-validation-2026-08-04.md)
- [Campaign 持仓轨道合同](specs/binance-1d-ma7dc-campaign-track-contract-2026-08-04.md)
- [截图与 Campaign 持仓轨道验证报告](diagnostics/binance-1d-ma7dc-campaign-tracking-2026-08-04.md)
- [MA7 容忍带与半 MFE 合同](specs/binance-1d-ma7dc-tolerance-exit-contract-2026-08-04.md)
- [MA7 容忍带与半 MFE 验证报告](diagnostics/binance-1d-ma7dc-tolerance-exit-2026-08-04.md)
- [研究脚本](scripts/research_binance_1d_ma7dc.py)
- [Campaign 审计脚本](scripts/audit_binance_1d_ma7dc_campaign_tracking.py)
- [容忍带退出审计脚本](scripts/audit_binance_1d_ma7dc_tolerance_exit.py)
- [产物说明](artifacts/README.md)
