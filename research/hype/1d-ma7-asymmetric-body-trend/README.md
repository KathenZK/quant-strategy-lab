# HYPE-1D-MA7-Asymmetric-Body-Trend

- Alias：`HYPE-1D-MA7-ABT`
- 市场/周期：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`
- 机制：固定 `SMA7` 的非对称日线趋势状态机；先审计原始“前收/开盘/实体”规则，再研究多空独立 reclaim、斜率确认、迟滞退出和 ATR 保护。
- 当前状态：`V1 registered / not promoted / not live-ready`；V1 是 post-reveal 历史观察值。

## 边界

- 本家族是固定 `SMA7`、`1x`、非加仓的非对称多空状态机；不是 `HYPE-1D-Pyramiding-Trend`、`HYPE-1D-Multi-Horizon-EMA-Forecast` 或无订单的 `Binance-1D-MA7-Deviation-Continuation`。
- “MA7 不穿过实体”按字面会让实体完全位于 MA7 下方的空单在次日开盘平仓并可能立即重开；该歧义不静默改写，研究同时保留字面版与方向性反转版。
- 多空分离分支是 materially new diagnostic mechanism，不继承初始规则的失败指标；其盈利候选来自 post-reveal 选择，不能当作 OOS 或 promotion 证据。

## 入口

- [主账](hype-1d-ma7-abt-core-ledger.md)
- [决策记录](decision-log.md)
- [初始研究合同](specs/hype-1d-ma7-abt-initial-contract-2026-08-04.md)
- [初始回测与稳健性报告](diagnostics/hype-1d-ma7-abt-initial-validation-2026-08-04.md)
- [V1 规格](specs/hype-1d-ma7-abt-v1-spec.md)
- [多空分离候选观察规格](specs/hype-1d-ma7-abt-separated-trend-observation-2026-08-04.md)
- [多空分离搜索报告](diagnostics/hype-1d-ma7-abt-separated-trend-search-2026-08-04.md)
- [V1 EMA7 零调参替换诊断](diagnostics/hype-1d-v1-ema7-substitution-2026-08-05.md)
- [V1 3x 杠杆诊断](diagnostics/hype-1d-v1-3x-leverage-2026-08-05.md)
- [初始规则脚本](scripts/research_hype_1d_ma7_asymmetric_body_trend.py) · [多空分离搜索脚本](scripts/search_hype_1d_ma7_separated_trend.py)
- [产物说明](artifacts/README.md)
