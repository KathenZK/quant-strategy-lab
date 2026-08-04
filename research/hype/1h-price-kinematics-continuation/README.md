# HYPE-1H-Price-Kinematics-Continuation

- Full family name：`HYPE-1H-Price-Kinematics-Continuation`（alias：`HYPE-1H-PKC`）
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual；完整 `1h` 价格轨迹，固定 `4h` 观察锚点，未来 `3d/7d/14d` 标签。
- 机制：不使用传统技术指标或交易触发器，只验证历史价格位移、速度、加速度、路径一致性、脉冲集中度和粗糙度能否预测未来趋势延续。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；尚无策略版本。

## 边界

- 这是价格运动学统计研究，不是 breakout、均线、通道、回归/Kalman 状态机或交易策略。
- 第一阶段不产生入场、仓位、止损、收益回测或 runner 规格；任何统计关系必须先通过冻结的历史 Validation，未来 prospective OOS 仍只允许揭示一次。

## 入口

- 主账：[hype-1h-pkc-core-ledger.md](hype-1h-pkc-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 冻结合同：[hype-1h-pkc-initial-research-contract-2026-08-02.md](specs/hype-1h-pkc-initial-research-contract-2026-08-02.md)
- 初始验证：[hype-1h-pkc-initial-research-2026-08-02.md](diagnostics/hype-1h-pkc-initial-research-2026-08-02.md)
- 复现入口：[scripts/README.md](scripts/README.md)
- 产物说明：[artifacts/README.md](artifacts/README.md)
