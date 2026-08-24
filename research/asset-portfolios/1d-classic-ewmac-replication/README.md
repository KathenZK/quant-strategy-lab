---
research_classification: diagnostic_topic
---

# Multi-Asset-1D-Classic-EWMAC-Replication

- 完整家族名：`Multi-Asset-1D-Classic-EWMAC-Replication`
- 别名：`XA-1D-CLASSIC-EWMAC`
- 市场：传统多资产代理，`1d`。资产类别按经典趋势跟踪论文划分为股票指数、债券、商品、外汇；数据使用 Yahoo Finance ETF/FX 代理。
- 机制：Carver EWMAC 四速连续 forecast（`8/32`、`16/64`、`32/128`、`64/256`，文献 scalar，cap `±20`）+ 单资产波动率归一化 + 等风险组合 + 组合层 `10%` 年化波动目标。
- 防串线：本线用于复现经典趋势文献特征，不含 BTC/ETH/HYPE；不同于 [`XA-1D-EWMAC-UT`](../1d-ewmac-universal-trend/README.md) 的加密 + ETF 小池可交易性研究，也不同于 [`BIN-1D-TSMOM-VT`](../1d-multi-asset-tsmom-vol-target/README.md) 的 Binance 动态大币池。
- 数据口径：公开 ETF/FX 调整后 OHLC 代理，非连续期货总收益、非真实 roll、非融资后 futures excess return。严格复现论文需 Bloomberg/Datastream/GFD/连续期货数据，本仓库当前没有。

## 当前状态

- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 尚无 registered version；本 README 兼任临时主账。
- 当前结论：首轮 `30` 个 ETF/FX 代理复现显示 gross 与 `2bps/边` 台账可复现长期正收益、低相关和 GFC/COVID/2022 压力期分散；但 `10bps/边` ETF 压力成本下 Sharpe 降至 `0.295`，只能记录为公开代理上的部分复现，不登记版本。

## 入口

- 决策日志：[decision-log.md](decision-log.md)
- 复现契约：[xa-1d-classic-ewmac-replication-contract-2026-08-10.md](specs/xa-1d-classic-ewmac-replication-contract-2026-08-10.md)
- 首轮诊断：[xa-1d-classic-ewmac-replication-2026-08-10.md](diagnostics/xa-1d-classic-ewmac-replication-2026-08-10.md)
- 脚本：[run_classic_ewmac_replication.py](scripts/run_classic_ewmac_replication.py)
- 产物：[artifacts/README.md](artifacts/README.md)
