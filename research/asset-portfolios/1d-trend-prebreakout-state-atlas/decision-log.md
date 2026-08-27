# Decision Log

## 2026-08-25 — 将“市场状态”从 MA7 过滤器中独立出来

决定另立 `BIN-1D-TPSA`：MA7/MA30 只作为事件探针，研究对象改为突破前已经形成的完整价格与波动路径；P0–P3 的旧 MA7 结果只保留为失败边界，不继承为候选规则。证据见 [P0 合同](specs/binance-1d-trend-prebreakout-state-atlas-p0-contract-2026-08-25.md)。

## 2026-08-25 — P0R 未找到跨 MA 与跨年份稳定的通用状态

P0 的严格自然日连续块遗漏周末休市资产，按不改变任何分析条件的 [P0R 修复合同](specs/binance-1d-trend-prebreakout-state-atlas-p0r-input-repair-2026-08-25.md) 重跑；最终无做多合格状态，做空描述性候选逐年翻转，ML 排序不稳定，且股票类合约无合格事件，因此决定 `INSUFFICIENT EVIDENCE / not promoted / not live-ready`。证据见 [P0R 报告](diagnostics/binance-1d-trend-prebreakout-state-atlas-p0r-results-2026-08-25.md)。

## 2026-08-25 — P1 路径标签发现 long 状态排序信息

按 [P1 合同](specs/binance-1d-trend-prebreakout-state-atlas-p1-barrier-ml-2026-08-25.md) 将目标改成未来20日先达到顺向 `+2 ATR` 而非先反向 `-1 ATR`；MA7/MA30 long 均在多数逐年测试中保持正排序，状态画像为下跌/回撤后的低波稳定区向上脱离，但不保证第20日收益，故只记 `exploratory signal / new OOS required / not promoted / not live-ready`。证据见 [P1 报告](diagnostics/binance-1d-trend-prebreakout-state-atlas-p1-barrier-ml-2026-08-25.md)。
