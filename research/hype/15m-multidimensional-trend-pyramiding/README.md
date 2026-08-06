# HYPE-15M-Multidimensional-Trend-Pyramiding

- Full family name：`HYPE-15M-Multidimensional-Trend-Pyramiding`（别名：`HYPE-15M-MDTP`）
- 市场/周期：Binance HYPEUSDT 永续；`4h` 定方向、`1h` 判阶段、`15m` 执行。
- 机制：多周期波动率标准化收益、Signed Kaufman ER、Donchian、方向量能与 RVOL 等权形成趋势分数，配合波动率目标、盈利后加仓、延伸/jump 限制及慢速退出。
- 当前状态：`V1 explore / not promoted / not live-ready`。

## 边界

- 这是独立于 `HYPE-EMA-Trend-Breakout`（V35）与 `HYPE-15M-Multi-Mechanism-Trend-Following` 的新家族。
- V35 只作为冻结对照；本家族不继承其版本号、参数、历史收益或 grandfathered live 状态。
- 跨币种固定参数迁移中，raw/normalized 对拍未完成的行只属 `explore / untrusted`。

## 入口

- 主账：[hype-15m-mdtp-core-ledger.md](hype-15m-mdtp-core-ledger.md)
- 决策记录：[decision-log.md](decision-log.md)
- V1 规格：[hype-15m-mdtp-v1-spec.md](specs/hype-15m-mdtp-v1-spec.md)
- 初始回测：[hype-15m-mdtp-v1-initial-research-2026-07-31.md](diagnostics/hype-15m-mdtp-v1-initial-research-2026-07-31.md)
- 失败复审：[hype-15m-mdtp-v1-failure-audit-2026-08-02.md](diagnostics/hype-15m-mdtp-v1-failure-audit-2026-08-02.md)
- Campaign successor 初始研究：[hype-15m-mdtp-campaign-successor-initial-research-2026-08-02.md](diagnostics/hype-15m-mdtp-campaign-successor-initial-research-2026-08-02.md)
- 复现入口：[scripts/README.md](scripts/README.md)
