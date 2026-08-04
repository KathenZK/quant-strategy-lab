# Decision Log

## 2026-08-03：创建独立 Goal 研究家族

用户明确创建目标任务：研究 BTC/ETH/HYPE 上可实盘执行的趋势策略，核心是识别可能趋势、持续度量延续性、回调后入场/滚仓并尽量获取完整趋势；周期和资产参数不强制相同，必要时允许传统技术指标。收益目标是完整成本后净值年化尽量达到 `20×`，最大回撤硬约束 `20%`。

本家族独立于 PIC V2。4h/1h/15m 回调状态机作为首个 anchor，时间周期可以在预冻结开发/验证流程中比较；任何优化不得使用锁定评估或 prospective 结果。Goal 不自动登记版本或授权 runner。

## 2026-08-03：数据与 continuation meter

BTC/ETH/HYPE closed 15m/funding 刷新至统一 cutoff，数据 blocker 为 0。24h continuation meter 在 ETH 三个 horizon 有稳定排序，BTC 弱、HYPE calibration 失败；因此资产从一开始按不同证据处理。

## 2026-08-03：回调、Campaign 与因果修正

固定回调/restart 未改善大多数入场；development-inner 60 组合仅得到低收益正偏 Probe。完整 lot Campaign 的默认 half-MFE reduction 伤害 BTC，ETH/HYPE 不合格。回测补齐逐 15m liquidation MDD、bar 内不利回撤、真实 quantity/3x、funding、stop 优先级和失败 plan pending；因果修正后全部搜索重跑。

## 2026-08-03：Regime V1、Limit V2 与风险边界

BTC 的 7d/28d 方向共识 + 3 layers + no-half-reduce 在 2021/2022/2023 development folds 全正，revealed diagnostic validation base/stress 为 `+11.30%/+9.33%`，但 annual multiple 仅 `1.074x/1.061x`，top-3 毛利润集中度 `96.0%`。ETH 限价在 development 改善但 validation `-10.03%`，判过拟合；HYPE 失败。

风险缩放显示 2x 为最高合规档位，validation annual multiple `1.134x`、bar 内 MDD `-17.05%`；3x bar 内 MDD `-23.03%` 超硬约束。不得继续靠风险放大。

## 2026-08-03：最终决定

`HARD-GATE-FAILED / no registered candidate / not promoted / not live-ready`。Historical locked evaluation 保持未运行；无资产取得组合资格；不创建 prospective、不交接 runner、不实现 live/dry-run。完整结论见 [最终报告](diagnostics/binance-mtf-ptc-goal-final-report-2026-08-03.md)。
