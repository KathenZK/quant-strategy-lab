# HYPE-1D-Price-Kinematics-Continuation

- Full family name：`HYPE-1D-Price-Kinematics-Continuation`（alias：`HYPE-1D-PKC`）
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual；完整 UTC `1d` 价格轨迹，未来 `3d/7d/14d` 标签。
- 机制：不使用传统技术指标或交易触发器，只验证日线价格位移、速度、加速度、路径一致性、脉冲集中度和粗糙度能否预测趋势延续。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；尚无策略版本。

## 边界

- 独立于 `HYPE-1H-PKC`、`HYPE-15M-PKC`、日线 EMA、breakout 和滚仓策略；不继承其他周期的参数或结论。
- 第一阶段没有订单、仓位、止损、收益回测或 runner 规格；HYPE 日线历史长度不足会作为证据门禁而不是用重叠标签掩盖。

## 入口

- 主账：[hype-1d-pkc-core-ledger.md](hype-1d-pkc-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 冻结合同：[hype-1d-pkc-initial-research-contract-2026-08-03.md](specs/hype-1d-pkc-initial-research-contract-2026-08-03.md)
- 初始验证：[hype-1d-pkc-initial-research-2026-08-03.md](diagnostics/hype-1d-pkc-initial-research-2026-08-03.md)
- 复现入口：[scripts/README.md](scripts/README.md)
- 产物说明：[artifacts/README.md](artifacts/README.md)
