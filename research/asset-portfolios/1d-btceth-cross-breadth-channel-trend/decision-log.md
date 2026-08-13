# BIN-1D-BE-CBCT Decision Log

## 2026-08-12 — P0 家族与合同冻结

- RCR、LRMR、CILL 分别证伪方向轮动风险修复、pair mean-reversion 与小时 lead–lag。
- 现有 Turtle 仅固定 20/10 same-close 单资产一年诊断；无 cross breadth、next-open 与真实小时 stop。
- 冻结独立 cross-breadth channel trend family，共 `2,808` 个配置；结果前不修改。

## 2026-08-12 — P0 HARD-GATE-FAILED；仅保留 profit-protection 单机制入口

- `2,808/2,808` 完成，base hard-target pass `0`；growth `13.2404x/-48.00%`，risk `1.6607x/-27.88%`。
- growth 纯价格毛值 `22.1427x`，实际 funding 后 `14.1579x`，净 `13.2404x`；成本重要，但无法修复约 `48%` 的路径回撤。
- 关闭 P0 参数扩张；audit/prospective 保持 sealed，无版本、无 handoff。
- 按 HYPE 的方法级顺序，下一步只冻结并检验已有浮盈后的单一 profit-protection 臂；未过 soft-continue 即关闭 family。
- 证据：[P0 裁决](diagnostics/binance-1d-be-cbct-p0-search-2026-08-12.md)。

## 2026-08-12 — P1 profit-protection 单机制冻结

- Exact control 固定为 P0 growth frontier，不重新选择 P0 参数。
- 只测试 entry-ATR 归一化的 MFE activation、fraction giveback 与日线确认，共 `18` 配置；不加入 handoff/re-entry/RSI。
- soft-continue 固定为 `>=10x`、log-growth retention `>=85%`、MDD `<=35%`且改善至少`10pp`、容量/集中度/压力/延迟同时通过。
- `0` 个通过即关闭 family；结果前不修改。[冻结合同](specs/binance-1d-be-cbct-p1-profit-protection-contract-2026-08-12.md)

## 2026-08-12 — P1 HARD-GATE-FAILED；research line closed

- `18/18` 完成、18 unique paths；soft-base/soft-continue/hard-target均为`0`。
- Growth `1ATR/35%/2d` 为 `21.2707x/-37.20%`，证明浮盈保护有增量但风险仍严重超标；risk `1ATR/20%/1d` 仅 `4.4107x/-34.20%`。
- 剩余回撤来自跨交易慢周期状态错配，不是单笔回吐；按冻结规则不加入 handoff/re-entry/RSI，不读取 audit/prospective，关闭 CBCT。[P1 裁决](diagnostics/binance-1d-be-cbct-p1-profit-protection-2026-08-12.md)
