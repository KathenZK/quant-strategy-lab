# Decision Log — Multi-Asset-1D-EWMAC-Universal-Trend

## 2026-08-06 P4 门禁重校准契约冻结 + 跑数判定：MDD 首次过关但 Sharpe/换手仍不过，家族在"日线 EWMAC + ETF 池"构造空间判死

- 决策：经用户确认（"再投入一轮：P4 门禁重校准契约"）冻结 P4 契约：目标波动 `20%→12%`、缓冲带 `0.10→0.20`（均为先验声明值，直击 P2/P3 绑定失败项 G2/G4，该两条门槛不变）；**门禁偏离记录**——G1 主窗 Sharpe 由 0.7 放宽至 0.6，理由为 12% 波动分散器画像下行业长期净 Sharpe 基准约 0.5，0.7 对应 20% 波动独立增长画像，偏离已在契约第 1 节声明。结果：G2 MDD −24.0% 与 G3 首次通过、G5 全正，但 G1 压力台账 Sharpe 0.48（0 成本口径 0.66，TradFi 10bps/边 × 21.8× 换手烧掉约 0.18）与 G4 换手 21.8× 未过；E1 挂非 G4 门禁，按契约 E2（三慢速）禁跑未跑。家族在"日线 EWMAC + ETF 池"构造空间内判死，研究线关闭；后续只允许换执行面（低成本期货/永续通道或周频再平衡执行契约）或换机制另立家族。附带回答用户"跑不赢标普"：策略与 SPY 相关性 0.01，50/50 组合 Sharpe 0.82 / MDD −25.2% 优于全仓 SPY 的 0.67 / −55.2%，但按自设门禁仍不可登记。家族保持 `explore / not promoted / not live-ready`。
- 证据：[P4 契约](specs/xa-1d-ewmac-ut-p4-gate-recalibration-contract-2026-08-06.md)、[P4 诊断](diagnostics/xa-1d-ewmac-ut-p4-gate-recalibration-2026-08-06.md)、[汇总 JSON](artifacts/xa_1d_ewmac_pf4_summary_2026-08-06.json)

## 2026-08-06 P3 扩池+scale 死区契约冻结 + 跑数判定：2022 修复、MDD 改善但仍超标，换手恶化，构造判死（5 条门禁过 1 条）

- 决策：经用户确认冻结 P3 契约（池扩到 18 资产 8 宏观集群：新增 TLT/IEF/USO/UNG/DBC/DBA/UUP/FXE/EEM；应用 scale 加 10% 死区；其余构造与门禁与 P2 完全一致），当日跑数。结果：扩池按设计生效（2022 由 P2 的 −9.3% 修复为 +13.7%，利率/外汇/商品腿对冲美股腿；MDD −41.5%→−34.4%），死区把 scale 变更从 365 次/年降到 122 次/年，但 18 个子系统 forecast 层日频漂移 + 平均杠杆升至 2.29 使总换手反升 26.5×→34.9×，加密时代 Sharpe 被 TradFi 成本稀释至 0.72。G1/G2/G3/G4 未过、仅 G5（LOO 18 次全正）通过，本构造按契约判死，禁止同历史调整池/死区/缓冲带/波动目标/杠杆上限重跑。可继承结论：(a) 广度救单集群熊市、救不了 2023 式跨集群趋势危机，MDD 门槛须靠降目标波动；(b) 换手主因在 forecast 层而非 scale 层。若立 P4 属门禁重校准（降目标波动 + 信号/缓冲层降换手），需新契约并记录偏离理由，待用户决定。家族保持 `explore / not promoted / not live-ready`。
- 证据：[P3 契约](specs/xa-1d-ewmac-ut-p3-breadth-scale-contract-2026-08-06.md)、[P3 诊断](diagnostics/xa-1d-ewmac-ut-p3-breadth-scale-2026-08-06.md)、[汇总 JSON](artifacts/xa_1d_ewmac_pf3_summary_2026-08-06.json)

## 2026-08-06 P2 组合级契约冻结 + 跑数判定：分散被证实但构造判死（5 条门禁过 1 条）

- 决策：经用户确认冻结 P2 组合级契约（9 资产零剔除、等风险 1/N、组合层 20% 波动目标、杠杆上限 3.0、缓冲带、压力成本台账判门禁），当日跑数。结果：分散论点被证实（子系统相关性 0.127、加密时代 Sharpe 0.905 vs 单资产最好 0.49、LOO 9 次全正=G5 过），但 G1 主窗 Sharpe 0.488、G2/G3 MDD −41.5%、G4 换手 26.5× 均未过，本构造按合同判死，禁止同历史调整构造参数重跑。死因：资产类别广度不足（3 集群撑不住 2021–2023 趋势冬天）+ 组合 scale 日频重估扰动全部仓位（成本拖累 2.69%/年）。合法下一步=扩池（债券/利率/能源/商品 ETF）与 scale 降扰的新契约。家族保持 `explore / not promoted / not live-ready`。
- 证据：[P2 契约](specs/xa-1d-ewmac-ut-portfolio-contract-2026-08-06.md)、[P2 诊断](diagnostics/xa-1d-ewmac-ut-portfolio-2026-08-06.md)、[汇总 JSON](artifacts/xa_1d_ewmac_pf_summary_2026-08-06.json)

## 2026-08-05 首轮跑数判定：单资产通用门禁未过，路线按合同判死；组合级聚合列为合法下一步

- 决策：按冻结合同判定——加密主门禁 BTC（Sharpe 0.493）与 ETH（0.432）双双卡在 G2 ≥ 0.5，其余三条全过；TradFi 验证 2/6 通过（QQQ/SPY 过；SOXX/SLV Sharpe 与 MDD 不足、GLD MDD −45.8% 超标、SOYB 全期为负），触发大面积失败条款。"同一参数单资产通用"主张判死，禁止同历史调参重跑；但信号质量为质变级证据（8/9 标的净收益为正、换手成本可养、Sharpe 区间与 CTA 文献一致，加密腿资金费拖累 ~4.8%/年为最大隐性成本）。下一步合法路径为组合级波动率平价聚合契约，需另立预注册、不继承本轮择优。家族保持 `explore / not promoted / not live-ready`。
- 证据：[首轮诊断](diagnostics/xa-1d-ewmac-ut-universal-trend-2026-08-05.md)、[汇总 JSON](artifacts/xa_1d_ewmac_ut_summary_2026-08-05.json)

## 2026-08-05 家族立项 + 合同冻结（跑数前预注册）

- 决策：用户明确研究目标为"BTC/ETH/HYPE 大币种 + 借 Binance TradFi 永续交易美股/商品"的小池趋势策略，不测山寨币池（TSMOM P1 同日暂停，见 [`BIN-1D-TSMOM-VT` 决策日志](../1d-multi-asset-tsmom-vol-target/decision-log.md)）。MA7 作为触发信号已由既有证据判死（7 天尺度换手成本不可养、跨资产迁移全败），本家族改用 Carver 文献冻结的 EWMAC 四速集成 + 20% 波动目标 + 缓冲带，一套参数零逐资产调参，先判 BTC/ETH 主门禁，再在 QQQ/SPY/SOXX/GLD/SLV/SOYB 验证；橡胶无可靠免费数据源列为 blocker。合同在跑数前冻结。
- 证据：[冻结合同](specs/xa-1d-ewmac-ut-universal-trend-contract-2026-08-05.md)
