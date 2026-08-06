# Decision Log

## 2026-08-03：冻结纯价格延续预测与动态控制双门禁

把“未来是否延续”和“动态加减仓是否优于同路径固定仓位”拆成两个独立门禁；历史采用严格 causal walk-forward，不把已经查看过的历史伪装成新 OOS。证据见[冻结合同](specs/hype-1h-pktsc-initial-research-contract-2026-08-03.md)。

## 2026-08-03：延续预测与动态控制均未验证

纯价格逐日 causal walk-forward 概率未优于基准，动态仓位在同 campaign 下差于固定种子仓且零成本仍亏；不创建版本、不调已揭示历史、不触碰 prospective OOS。证据见[初始双门禁验证](diagnostics/hype-1h-pktsc-initial-research-2026-08-03.md)。
