# Multi-Asset-1D-EWMAC-Universal-Trend

- 完整家族名：`Multi-Asset-1D-EWMAC-Universal-Trend`
- 别名：`XA-1D-EWMAC-UT`
- 市场：跨市场小资产池，`1d`。主判定盘 Binance USDT 永续 BTC/ETH（HYPE 样本短仅报告）；验证盘 Yahoo 日线 ETF（QQQ/SPY/SOXX/GLD/SLV/SOYB）。
- 机制：Carver 式 EWMAC 四速集成（8/32、16/64、32/128、64/256，文献冻结 scalar），单资产 20% 年化波动目标连续仓位 + 仓位缓冲带，全资产共用同一套参数、零逐资产调参。
- 防串线：与 [`BIN-1D-TSMOM-VT`](../1d-multi-asset-tsmom-vol-target/README.md)（30 大币池、符号投票、组合层 vol target）不同——本线是小池、连续预测、单资产独立判定；与已冻结的 MA7 单资产线（binary 触发）机制不同源。
- 数据口径：加密从已审计 15m 归一化湖重采样 UTC 日线（跨源去重，日收盘两源零差异已验证）+ 逐日 as-of 资金费；TradFi 用 Yahoo adjclose 调整后 OHLC，0 成本主口径 + 10 bps/边敏感度。橡胶无可靠免费数据源，声明为 blocker。

## 当前状态

- 状态：`explore / not promoted / not live-ready`（**研究线已关闭**，2026-08-06）
- 尚未注册版本；本 README 兼任临时主账。四轮契约全部判死：P1 单资产通用门禁未过；P2 组合级分散被证实但 MDD −41.5%/换手 26.5× 未过；P3 扩池 18 资产修复 2022、MDD 改善到 −34.4% 但换手恶化到 34.9×；P4 降波动 12%+宽缓冲带使 MDD −24.0% 首次过关，但压力台账 Sharpe 0.48（0 成本 0.66）与换手 21.8× 未过，E2 按裁决规则禁跑。遗产：EWMAC 趋势因子毛 Sharpe 0.6–0.7 跨 18 资产稳定存在、与 SPY 相关性 0.01、50/50 组合优于全仓 SPY；死结为日频再平衡 × TradFi 10bps/边执行面不经济。后续只允许换执行面或换机制另立家族。

## 入口

- 决策日志：[decision-log.md](decision-log.md)
- P1 合同/诊断：[xa-1d-ewmac-ut-universal-trend-contract-2026-08-05.md](specs/xa-1d-ewmac-ut-universal-trend-contract-2026-08-05.md) / [xa-1d-ewmac-ut-universal-trend-2026-08-05.md](diagnostics/xa-1d-ewmac-ut-universal-trend-2026-08-05.md)
- P2 合同/诊断：[xa-1d-ewmac-ut-portfolio-contract-2026-08-06.md](specs/xa-1d-ewmac-ut-portfolio-contract-2026-08-06.md) / [xa-1d-ewmac-ut-portfolio-2026-08-06.md](diagnostics/xa-1d-ewmac-ut-portfolio-2026-08-06.md)
- P3 合同/诊断：[xa-1d-ewmac-ut-p3-breadth-scale-contract-2026-08-06.md](specs/xa-1d-ewmac-ut-p3-breadth-scale-contract-2026-08-06.md) / [xa-1d-ewmac-ut-p3-breadth-scale-2026-08-06.md](diagnostics/xa-1d-ewmac-ut-p3-breadth-scale-2026-08-06.md)
- P4 合同/诊断：[xa-1d-ewmac-ut-p4-gate-recalibration-contract-2026-08-06.md](specs/xa-1d-ewmac-ut-p4-gate-recalibration-contract-2026-08-06.md) / [xa-1d-ewmac-ut-p4-gate-recalibration-2026-08-06.md](diagnostics/xa-1d-ewmac-ut-p4-gate-recalibration-2026-08-06.md)
- 脚本：[scripts/run_ewmac_universal_trend.py](scripts/run_ewmac_universal_trend.py)、[scripts/run_ewmac_portfolio.py](scripts/run_ewmac_portfolio.py)；产物：[artifacts/README.md](artifacts/README.md)
