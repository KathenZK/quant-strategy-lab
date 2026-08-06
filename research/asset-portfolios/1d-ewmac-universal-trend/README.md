# Multi-Asset-1D-EWMAC-Universal-Trend

- 完整家族名：`Multi-Asset-1D-EWMAC-Universal-Trend`
- 别名：`XA-1D-EWMAC-UT`
- 市场：跨市场小资产池，`1d`。主判定盘 Binance USDT 永续 BTC/ETH（HYPE 样本短仅报告）；验证盘 Yahoo 日线 ETF（QQQ/SPY/SOXX/GLD/SLV/SOYB）。
- 机制：Carver 式 EWMAC 四速集成（8/32、16/64、32/128、64/256，文献冻结 scalar），单资产 20% 年化波动目标连续仓位 + 仓位缓冲带，全资产共用同一套参数、零逐资产调参。
- 防串线：与 [`BIN-1D-TSMOM-VT`](../1d-multi-asset-tsmom-vol-target/README.md)（30 大币池、符号投票、组合层 vol target）不同——本线是小池、连续预测、单资产独立判定；与已冻结的 MA7 单资产线（binary 触发）机制不同源。
- 数据口径：加密从已审计 15m 归一化湖重采样 UTC 日线（跨源去重，日收盘两源零差异已验证）+ 逐日 as-of 资金费；TradFi 用 Yahoo adjclose 调整后 OHLC，0 成本主口径 + 10 bps/边敏感度。橡胶无可靠免费数据源，声明为 blocker。

## 当前状态

- 状态：`explore / not promoted / not live-ready`
- 尚未注册版本；身份与裁决见 [binance-1d-ewmac-ut-core-ledger.md](binance-1d-ewmac-ut-core-ledger.md)。2026-08-05 合同冻结后跑数结论：9 标的 8 个净收益为正、换手成本可养（3.5–11×/年）、单资产 Sharpe 0.25–0.49 与文献一致，但预注册门禁未过——BTC 0.493/ETH 0.432 卡 G2（≥0.5），TradFi 仅 QQQ/SPY 全过（2/6）。单资产通用主张按合同判死；合法下一步是组合级聚合契约（另立预注册）。

## 入口

- 主账：[binance-1d-ewmac-ut-core-ledger.md](binance-1d-ewmac-ut-core-ledger.md)
- 决策日志：[decision-log.md](decision-log.md)
- 冻结合同：[xa-1d-ewmac-ut-universal-trend-contract-2026-08-05.md](specs/xa-1d-ewmac-ut-universal-trend-contract-2026-08-05.md)
- 诊断：[xa-1d-ewmac-ut-universal-trend-2026-08-05.md](diagnostics/xa-1d-ewmac-ut-universal-trend-2026-08-05.md)
- 脚本：[scripts/run_ewmac_universal_trend.py](scripts/run_ewmac_universal_trend.py)；产物：[artifacts/README.md](artifacts/README.md)
