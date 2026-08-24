# HYPE-4H-MA7-Close-Reversal

- Alias：`HYPE-4H-MA7-CR`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `4h`
- 机制：`4h` 收盘在 `SMA7` 上方则下一期开盘持多，在下方则下一期开盘持空；信号翻转时直接反手。
- 防串线：这是始终持仓的单均线 close-regime flip，不是 `HYPE-4H-MA7-ABT` 的回踩/reclaim 参数搜索，也不是日线 V1。
- 当前状态：`explore / not promoted / not live-ready`；零参数基准全期 `-90.01%`，gross 仍 `-52.34%`，不登记版本。

入口：

- [家族主账](hype-4h-ma7-cr-core-ledger.md)
- [决策记录](decision-log.md)
- [冻结合同](specs/hype-4h-ma7-close-reversal-contract-2026-08-06.md)
- [基准诊断](diagnostics/hype-4h-ma7-close-reversal-baseline-2026-08-06.md)
- [复现脚本](scripts/research_hype_4h_ma7_close_reversal.py)
- [机器证据](artifacts/README.md)
