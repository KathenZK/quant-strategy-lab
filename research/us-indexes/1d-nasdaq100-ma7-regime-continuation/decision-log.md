# Decision Log

## 2026-08-24 — 冻结独立的 historical Nasdaq-100 P0

建立 `NDX100-1D-MA7-RC-P0`，只做与 Binance P0 可比的条件事件诊断；禁止回填当前成分、股票结果调阈值或将 MA7 当 regime。[冻结合同](specs/ndx100-1d-ma7-regime-continuation-p0-contract-2026-08-24.md)

## 2026-08-24 — 成分重建可用于管线，但价格结果继续 fail closed

revision-pinned 变更索引、行级来源分层、官方公司行动修正和 ticker lineage 已产出；因 Massive key 缺失，价格、FIGI、事件统计及 cross-market 表全部保持未生成。[来源说明](specs/ndx100-membership-reconstruction-sources-2026-08-24.md) · [阻塞报告](diagnostics/ndx100-1d-ma7-regime-continuation-blocker-2026-08-24.md)

后续 key 实测修正：credential 有效，但只有最近两年日线，P0 blocker 从“缺 key”更新为“历史 entitlement 不足”；P0 结果仍未运行。

## 2026-08-24 — 用户授权 Yahoo 当前成分 Y0，不覆盖 historical P0

用户明确允许在 historical membership / Massive 受阻时改用 Yahoo 日线并回填当前成分。建立独立 `NDX100-1D-MA7-RC-Y0`：terminal snapshot `102` 条证券，Yahoo 请求全部成功，MA7 `77,066` 个事件。ER 未单调改善、三变量 surface 跨时期弱、与 Binance Slope 方向不一致；记录为 survivorship-biased 快速诊断，不调参、不替代 P0、不 promotion。[Y0 诊断](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y0-2026-08-24.md)

## 2026-08-25 — 纳入历史退出成分，但 Y1 在覆盖门槛处 fail closed

用户要求重新尝试 Yahoo 历史退出成分。`NDX100-1D-MA7-RC-Y1` 请求全部 `252` 个历史 ticker，没有发生整批限流；`152` 个末端已退出 ticker 中 `95` 个至少取得部分直接或唯一同实体 lineage 覆盖。然而完整 PIT membership 仅覆盖 `348,462 / 429,268 = 81.18%`，仍缺 `80,806` 个 member stock-days，低于事前冻结 `99.5%` 门槛。保留已取得数据和映射，但不运行 MA7/regime 结果，不用部分样本修改 Y0 或跨市场结论。[Y1 覆盖审计](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-historical-y1-coverage-2026-08-25.md)

## 2026-08-25 — Crypto P2 ATR 路径迁移到股票 Y2，稳定优化未复现

读取股票结果前，原样冻结 Crypto P2 的 `ATR20[t-1]/ATR20[t-11]-1`、60 期因果分位、burst `1.2x`、MA slope aligned，以及 long Q5+burst / short Q1+burst 两个外部格。Y2 的 long 外部格 20D 为 `+3.68%`，但相对其余 long MA7 只多 `+0.52pp / t=0.45`，10D 与 40D 均不改善；short 外部格为 `-2.39% / t=-5.56`，与 Crypto 的正空头 expectancy 方向相反。股票 ATR-path 五档最大分离也弱于旧 RV252。因此裁决为外部假设未形成稳定可迁移优化，不根据股票结果继续挑格。[Y2 结果](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y2-atr-path-2026-08-25.md)

## 2026-08-25 — Y3 把问题改回突破前价格路径，识别出“受创后的修复”机制

Y3 不再把 market state 等同于 ER/Slope/RV，也不使用个股横截面相对强弱或 ML。所有特征严格截至 `t-1`，逐项统计大跌修复、深回撤筑底、均线层级、离 MA30 距离、区间/波动、强涨回落、市场宽度和 QQQ 阶段，共 `11` 个连续维度、`23` 个具名结构、`110,154` 个 MA7/MA30 事件。

通过 20D 正方向、正增量、最小样本和全状态 BH-FDR10 门槛的状态全部属于向上修复：MA7 深回撤修复 `+8.53%`、相对其余同向突破 `+5.93pp`；MA7 仍在 MA30 下方的早期修复 `+7.06% / +4.32pp`；MA30 深回撤修复、早期修复、空头排列强反弹和小样本暴跌反转也通过。差异在 10–40D 而非 1–5D 展开，且去掉绝对 gap >1% 后仍为正。低波横盘底座、牛市浅回踩均显著弱于其余多头突破；强上涨后横盘/回落的所有空头候选仍为负方向收益，不能称为空头延续信号。

裁决：股票样本中的主要候选机制不是平滑趋势延续，而是“先受创、后修复、再跨均线”的数周级反转/修复延续。由于 Y3 使用当前成分回填且具名状态来自全样本机制筛查，只登记为 hypothesis generation；下一步必须冻结少量机制，在独立/point-in-time 数据上验证，不能直接变成策略。[Y3 结果](diagnostics/ndx100-1d-ma7-regime-continuation-yahoo-current-y3-structure-atlas-2026-08-25.md)
