# HYPE-15M-Price-Kinematics-Continuation

- Full family name：`HYPE-15M-Price-Kinematics-Continuation`（alias：`HYPE-15M-PKC`）
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual；完整 `15m` 价格轨迹，每小时一个主锚点，未来 `1h/3h/6h/12h` 标签。
- 机制：不使用传统技术指标或交易触发器，只验证过去 `1h/3h/6h` 的价格位移、速度、加速度和路径形状能否预测未来数小时延续。
- 当前状态：`explore / diagnostic-only / not promoted / not live-ready`；尚无策略版本。

## 边界

- 独立于 `HYPE-1H-PKC`：过去窗口、未来标签、采样相位和独立 block 均重新冻结，不继承其统计结论。
- 第一阶段没有入场、仓位、止损、PnL 或 runner；只验证“几小时一阵”的价格路径惯性。

## 入口

- 主账：[hype-15m-pkc-core-ledger.md](hype-15m-pkc-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- 冻结合同：[hype-15m-pkc-initial-research-contract-2026-08-02.md](specs/hype-15m-pkc-initial-research-contract-2026-08-02.md)
- 初始验证：[hype-15m-pkc-initial-research-2026-08-02.md](diagnostics/hype-15m-pkc-initial-research-2026-08-02.md)
- 复现入口：[scripts/README.md](scripts/README.md)
- 产物说明：[artifacts/README.md](artifacts/README.md)
