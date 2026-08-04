# HYPE-1H-Price-Kinematic-Trend-Survival-Control

- Full family name：`HYPE-1H-Price-Kinematic-Trend-Survival-Control`（alias：`HYPE-1H-PKTSC`）
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual；完整 `1h` 价格轨迹，每 `4h` 更新，目标 campaign `3–14d`。
- 机制：以纯价格运动学的 causal walk-forward 模型估计延续概率，再以固定风险数量、离散加减仓和半 MFE 保护追踪趋势。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；尚无策略版本。

## 边界

- 独立于 `HYPE-1H-PKC`、`HYPE-1D-PKC`、`HYPE-15M-SDS` 与 `HYPE-15M-MDTP`；不使用 EMA、MA、Donchian、ATR、ADX、成交量或其他传统指标。
- 历史价格已被相邻研究查看，本轮历史只称 causal walk-forward 证据；`2026-08-02` 起 prospective OOS 保持未读取。

## 入口

- 主账：[hype-1h-pktsc-core-ledger.md](hype-1h-pktsc-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 冻结合同：[hype-1h-pktsc-initial-research-contract-2026-08-03.md](specs/hype-1h-pktsc-initial-research-contract-2026-08-03.md)
- 初始验证：[hype-1h-pktsc-initial-research-2026-08-03.md](diagnostics/hype-1h-pktsc-initial-research-2026-08-03.md)
- 复现入口：[scripts/README.md](scripts/README.md)
- 产物说明：[artifacts/README.md](artifacts/README.md)
