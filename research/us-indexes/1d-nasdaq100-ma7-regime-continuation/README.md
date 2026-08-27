# Nasdaq100-1D-MA7-Regime-Continuation

- Alias：`NDX100-1D-MA7-RC`
- 市场/周期：historical Nasdaq-100 point-in-time constituents，XNAS regular session `1d`
- 机制：以 MA7/MA30 严格收盘跨越为事件，研究突破前截至 `t-1` 的价格路径、回撤/反弹、均线层级、波动/区间、市场宽度和 QQQ 阶段，检验后续 1–40 个交易日延续。
- 当前状态：historical point-in-time P0 仍为 `BLOCKED_DATA_ACCESS`；Yahoo 历史成分 Y1 覆盖仅 `81.18%`。Yahoo 当前成分 Y3 已完成可解释结构图谱：股票多头最强的是深回撤后的早期修复/空头趋势反转，优势主要在 10–40D 展开；低波底座、牛市浅回踩和所有具名空头延续假设均未得到正方向支持。Y3 仍为 survivorship-biased 全样本假设生成，整体保持 `explore / diagnostic-only / not promoted / not live-ready`。

## 边界

- 本家族是条件事件研究，不是可执行策略，也不继承 Binance 家族的收益结论。
- MA7 只定义事件，不进入 regime；禁止根据股票结果搜索阈值。
- 价格只接受 Massive（原 Polygon）冻结接口；缺 key 时不得静默换 Yahoo、Stooq 或其他提供商。
- 经用户显式授权建立的 Yahoo 当前成分 `Y0` 是独立 survivorship-biased observation，不覆盖、替代或解除上述 P0 约束。
- 经用户显式授权建立的 Yahoo 历史成分 `Y1` 复用冻结 PIT membership；覆盖低于预注册 `99.5%` 时 fail closed，不允许用部分退市样本形成结论。
- `Y2` 将 Crypto P2 的 ATR 路径和两个方向格作为外部固定假设迁移到 Y0；不得根据股票结果更换 quintile、burst 阈值或 horizon。
- `Y3` 是突破前结构图谱：不用 ML、不用个股横截面相对强弱；所有状态严格截至 `t-1`，具名阈值只用于机制筛查，并以全状态 BH-FDR 和分年增量检验约束数据窥探。
- Nasdaq-100 是 100 家非金融公司，不保证每天恰好 100 条证券；多重合资格 share classes 可同时入选。

## 入口

- [主账](ndx100-1d-ma7-rc-core-ledger.md)
- [决策记录](decision-log.md)
- [冻结合同](specs/ndx100-1d-ma7-regime-continuation-p0-contract-2026-08-24.md)
- [成分来源与重建说明](specs/ndx100-membership-reconstruction-sources-2026-08-24.md)
- [数据阻塞报告](diagnostics/ndx100-1d-ma7-regime-continuation-blocker-2026-08-24.md)
- [Yahoo 当前成分 Y0 合同](specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y0-contract-2026-08-24.md) · [Y0 诊断](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y0-2026-08-24.md)
- [Yahoo 历史成分 Y1 合同](specs/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1-contract-2026-08-25.md) · [Y1 覆盖审计](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1-coverage-2026-08-25.md)
- [Crypto ATR 路径迁移 Y2 合同](specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path-contract-2026-08-25.md) · [Y2 结果](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path-2026-08-25.md)
- [突破前结构图谱 Y3 合同](specs/ndx100-1d-ma7-regime-continuation-yahoo-current-y3-structure-atlas-contract-2026-08-25.md) · [Y3 结果](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y3-structure-atlas-2026-08-25.md)
- [复现脚本](scripts/reconstruct_ndx100_membership.py) · [研究脚本](scripts/research_ndx100_1d_ma7_regime_continuation.py)
- [Yahoo 下载脚本](scripts/fetch_yahoo_current_ndx100_daily.py) · [Y0 研究脚本](scripts/research_ndx100_current_yahoo_1d_ma7_regime_continuation.py)
- [Yahoo 历史下载脚本](scripts/fetch_yahoo_historical_ndx100_daily.py) · [Y1 覆盖审计脚本](scripts/audit_yahoo_historical_ndx100_coverage.py)
- [Y2 ATR 路径迁移脚本](scripts/analyze_ndx100_yahoo_current_y2_atr_path.py)
- [Y3 突破前结构图谱脚本](scripts/analyze_ndx100_yahoo_current_y3_structure_atlas.py)
- [机器证据](artifacts/README.md)
