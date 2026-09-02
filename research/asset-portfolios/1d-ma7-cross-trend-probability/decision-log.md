# Decision Log

## 2026-08-31：四币日K MA7 穿越趋势发生率 SCOUT

决策：用户要求在 BTC/ETH/BNB/SOL 永续日K上统计穿越 MA7 后发生趋势的条件概率，以及斜率、放量、7/30/60/90 日上涨回撤比的分层。另立 diagnostic topic，不继承 TPSA/MA7-RC 的交易规则，不登记版本。

证据：[冻结口径](specs/binance-1d-ma7-cross-trend-probability-contract-2026-08-31.md) · [诊断](diagnostics/binance-1d-ma7-cross-trend-probability-2026-08-31.md)

## 2026-08-31：裸穿越约三成走出趋势段，斜率/放量/30日R过滤几乎不抬升

决策：全历史四币合计 `trend_20` 为 30.8%（多头 34.4%，空头 27.2%）。斜率 0.02、放量 1.5× 及其组合只把合计抬到 31–33%；预指定的 30 日多头 R<1 / 空头 R>1 反而降到 27.7%。保持 `explore / diagnostic-only / not promoted / not live-ready`，不把格子观察升级成过滤器。

证据：[诊断](diagnostics/binance-1d-ma7-cross-trend-probability-2026-08-31.md) · [汇总 JSON](artifacts/binance_1d_ma7_ctp_summary_2026-08-31.json)

## 2026-08-31：全市场缓存日K 仍约三成，方向结构接近 TPSA 而不是四币

决策：同一冻结口径扩到 `data/cache/binance_perp_1d_from_15m`（2020-01-01 至 2026-06-30 完整日）。653 个入选合约、111,918 个可标签穿越，合计 `trend_20` 30.4%（多头 29.3%，空头 31.6%）。斜率 0.02 只到 32.5%；放量 1.5× 降到 28.6%。保持 `explore / diagnostic-only / not promoted / not live-ready`，不另立家族、不搜索新阈值。

证据：[全市场诊断](diagnostics/binance-1d-ma7-cross-trend-probability-all-market-2026-08-31.md) · [汇总 JSON](artifacts/binance_1d_ma7_ctp_all_market_summary_2026-08-31.json)

## 2026-08-31：HYPE 点估计偏高，但不能判定比其它币更容易走出趋势

决策：同一冻结标签下 HYPE `trend_20` 为 36.0%（31/86），全市场 30.4%、同窗口其它币 30.1%。区间重叠，同窗口单侧二项 p=0.14。多头点估计更高但是事后拆分。保持 `explore / diagnostic-only / not promoted / not live-ready`。

证据：[HYPE 对照](diagnostics/binance-1d-ma7-cross-trend-probability-hype-vs-universe-2026-08-31.md) · [对照 JSON](artifacts/binance_1d_ma7_ctp_hype_vs_universe_2026-08-31.json)

## 2026-09-01：P1 MA7 穿越事件模型不稳定，不能当入场打分器

决策：在 CATL P0R donor 的 101,187 条合格 MA7 穿越上训练 LONG/SHORT 入场价值模型。开发期有弱排序但全面过拟合；2025+ 系统 AUC 0.5202，95% CI 穿过 0.50。裁决 `UNSTABLE_MA7_EVENT_SIGNAL`。保持 `explore / diagnostic-only / not promoted / not live-ready`。本轮未读取 HYPE，不是策略。

证据：[合同](specs/binance-1d-ma7-ctp-p1-cross-conditioned-entry-model-contract-2026-09-01.md) · [报告](diagnostics/binance-1d-ma7-ctp-p1-cross-conditioned-entry-model-2026-09-01.md) · [审计](diagnostics/binance-1d-ma7-ctp-p1-modeling-audit-2026-09-01.md) · [主账](binance-1d-ma7-ctp-core-ledger.md)

## 2026-09-01：P1 年度门禁与 HYPE 报告断言修复

决策：不修改 P1 冻结合同、样本、特征、模型或 terminal 预测，只修复审计实现。年度函数现在保存所有年度分段，最终门禁同时检查 LONG/SHORT head 与合并系统；据此确认合并系统 2026 年 AUC `0.4753`，`system_year_ok=false`。原 HYPE 报告测试中的永真 `or True` 已移除，改为核验报告明确声明输入、OOF、历史测试均为 0 行且未读取/预测/揭示 HYPE。修复后完整重跑，裁决仍为 `UNSTABLE_MA7_EVENT_SIGNAL`。

证据：[报告](diagnostics/binance-1d-ma7-ctp-p1-cross-conditioned-entry-model-2026-09-01.md) · [审计](diagnostics/binance-1d-ma7-ctp-p1-modeling-audit-2026-09-01.md) · [测试](../../../tests/test_binance_1d_ma7_ctp_p1_cross_conditioned_entry_model.py)

## 2026-09-01：P2 pooled 极简模型稳定，但路径增量未被证明

决策：P2 只用 2025 年前真实 MA7 穿越事件和 F0/F1 字段，训练单一 pooled 方向对齐模型。锁定 `F1_LOGIT`，D1-D3 验证 AUC 为 `0.5945/0.5598/0.5715`，OOF block-bootstrap AUC CI 为 `[0.5394, 0.5936]`，但 F1 相对 F0 paired AUC 差 CI 为 `[-0.0050, 0.0453]`。裁决 `SIGNAL_EXPLAINED_BY_MA7_CORE`，保持 `explore / diagnostic-only / not promoted / not live-ready`；无新 OOS、无 2025+ 预测、未读取 HYPE。

证据：[合同](specs/binance-1d-ma7-ctp-p2-pooled-minimal-stability-contract-2026-09-01.md) · [报告](diagnostics/binance-1d-ma7-ctp-p2-pooled-minimal-stability-2026-09-01.md) · [审计](diagnostics/binance-1d-ma7-ctp-p2-modeling-audit-2026-09-01.md) · [汇总 JSON](artifacts/binance_1d_ma7_ctp_p2_summary.json)

## 2026-09-01：P2 概率校准审计修复

决策：不修改 P2 样本、标签、特征、候选、模型选择或 HYPE/2025+ 隔离，只修复 Platt 方法名被 `raw` 覆盖的问题，并改为 D2 仅用已完成的 D1 OOF 标签、D3 仅用已完成的 D1-D2 OOF 标签做前向交叉校准。原始 OOF AUC 与十分位排序不变；D2-D3 Brier `0.2200→0.2183`、LogLoss `0.6356→0.6292`，最终模型卡冻结 `platt`，仍无新 OOS、not live-ready。

证据：[报告](diagnostics/binance-1d-ma7-ctp-p2-pooled-minimal-stability-2026-09-01.md) · [审计](diagnostics/binance-1d-ma7-ctp-p2-modeling-audit-2026-09-01.md) · [汇总 JSON](artifacts/binance_1d_ma7_ctp_p2_summary.json) · [测试](../../../tests/test_binance_1d_ma7_ctp_p2_pooled_minimal_stability.py)

## 2026-09-01：P3 独立上下文块审计在训练前数据门禁停止

决策：P3 合同与 feature spec 已在读标签前冻结，并确认原始 pre-2025 MA7 事件为 `54,137`、HYPE 为 `0`；加载严格样本后发现 `52,563` 行全部为 `feature_known_at == entry_ts`，不满足合同要求的 `feature_known_at < entry_ts`，裁决 `DATA_BLOCK_NOT_READY` 并停止训练。未生成 OOF、增量比较、模型卡或 2025+ 预测，状态保持 `explore / diagnostic-only / not promoted / not live-ready`。

证据：[合同](specs/binance-1d-ma7-ctp-p3-context-feature-block-audit-contract-2026-09-01.md) · [报告](diagnostics/binance-1d-ma7-ctp-p3-context-feature-block-audit-2026-09-01.md) · [审计](diagnostics/binance-1d-ma7-ctp-p3-modeling-audit-2026-09-01.md) · [汇总 JSON](artifacts/binance_1d_ma7_ctp_p3_summary.json)
