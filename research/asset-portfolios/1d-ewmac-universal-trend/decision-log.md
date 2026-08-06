# Decision Log — Multi-Asset-1D-EWMAC-Universal-Trend

## 2026-08-05 首轮跑数判定：单资产通用门禁未过，路线按合同判死；组合级聚合列为合法下一步

- 决策：按冻结合同判定——加密主门禁 BTC（Sharpe 0.493）与 ETH（0.432）双双卡在 G2 ≥ 0.5，其余三条全过；TradFi 验证 2/6 通过（QQQ/SPY 过；SOXX/SLV Sharpe 与 MDD 不足、GLD MDD −45.8% 超标、SOYB 全期为负），触发大面积失败条款。"同一参数单资产通用"主张判死，禁止同历史调参重跑；但信号质量为质变级证据（8/9 标的净收益为正、换手成本可养、Sharpe 区间与 CTA 文献一致，加密腿资金费拖累 ~4.8%/年为最大隐性成本）。下一步合法路径为组合级波动率平价聚合契约，需另立预注册、不继承本轮择优。家族保持 `explore / not promoted / not live-ready`。
- 证据：[首轮诊断](diagnostics/xa-1d-ewmac-ut-universal-trend-2026-08-05.md)、[汇总 JSON](artifacts/xa_1d_ewmac_ut_summary_2026-08-05.json)

## 2026-08-05 家族立项 + 合同冻结（跑数前预注册）

- 决策：用户明确研究目标为"BTC/ETH/HYPE 大币种 + 借 Binance TradFi 永续交易美股/商品"的小池趋势策略，不测山寨币池（TSMOM P1 同日暂停，见 [`BIN-1D-TSMOM-VT` 决策日志](../1d-multi-asset-tsmom-vol-target/decision-log.md)）。MA7 作为触发信号已由既有证据判死（7 天尺度换手成本不可养、跨资产迁移全败），本家族改用 Carver 文献冻结的 EWMAC 四速集成 + 20% 波动目标 + 缓冲带，一套参数零逐资产调参，先判 BTC/ETH 主门禁，再在 QQQ/SPY/SOXX/GLD/SLV/SOYB 验证；橡胶无可靠免费数据源列为 blocker。合同在跑数前冻结。
- 证据：[冻结合同](specs/xa-1d-ewmac-ut-universal-trend-contract-2026-08-05.md)
