# Binance-MTF-Pullback-Trend-Campaign

- Full family：`Binance-MTF-Pullback-Trend-Campaign`（alias：`BIN-MTF-PTC`）。
- 资产：BTCUSDT、ETHUSDT、HYPEUSDT perpetual，分资产研究与参数治理；只用合格资产装配组合。
- 核心：因果识别趋势候选，持续度量趋势延续/失效概率，等待回调后以 15m 或其他已冻结执行周期试仓和分层加仓，尽量保留 3–14d 右尾。
- 目标：完整成本后尽量达到净值年化 `20×`，最大回撤硬约束 `20%`；目标不得覆盖实盘可执行、数据、时序、风险和 OOS 门禁。
- 当前状态：`explore / not promoted / not live-ready`；本轮决定 `HARD-GATE-FAILED`，Goal 研究已完成，未产生 registered version、live spec 或 runner。

## 边界

- 本家族独立于 V35TB、HYPE-15M-MDTP 和 BIN-1H-PIC V0–V2，不继承其版本或绩效。
- 4h/1h/15m 是首个锚定结构，不是永久强制周期；周期选择必须在开发/验证区完成，锁定评估与 prospective 不得救参。
- 技术指标可以作为价格/波动/路径测量工具；任何指标必须证明增量和稳定性，不能靠堆叠替代明确状态机。
- 历史全样本已多次揭示，只能提供筛错和稳健性证据；最终 promotion 仍需新的 prospective OOS。

## 入口

- [主账](binance-mtf-ptc-core-ledger.md)
- [决策记录](decision-log.md)
- [Goal 合同](specs/binance-mtf-ptc-goal-contract-2026-08-03.md)
- [最终研究报告](diagnostics/binance-mtf-ptc-goal-final-report-2026-08-03.md)
- [Goal 完成矩阵](diagnostics/binance-mtf-ptc-goal-completion-matrix-2026-08-03.md)
- [BTC 历史前沿复现规格](specs/binance-mtf-ptc-btc-frontier-reproduction-spec-2026-08-03.md)
- [Runner 能力差距](runner-tracking/binance-mtf-ptc-runner-gap-2026-08-03.md)
- [脚本](scripts/README.md)
- [产物](artifacts/README.md)
