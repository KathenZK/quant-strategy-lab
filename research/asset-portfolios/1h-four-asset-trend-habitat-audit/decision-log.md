# Decision Log

## 2026-08-03：冻结四资产趋势生态丈量

先比较 HYPE/BTC/ETH/SOL 是否客观产生顺滑、可延迟进入、可容忍半 MFE 回吐的 `3d/7d/14d` 趋势，再单独验证当时可知的 `7d/28d` 方向是否有 admission 价值；共同窗口为横向主证据，不把增加资产视为修复负期望。证据见[初始研究合同](specs/binance-1h-fatha-initial-research-contract-2026-08-03.md)。

## 2026-08-03：增加揭示后 onset-followthrough 诊断

第 1 轮 habitat/admission 聚合已经可见后，另行冻结 `4h/12h/24h` 初始价格位移方向、波动归一化速度和路径效率对剩余 horizon 的延续检验。该扩展直接对应“试单后等待行情验证再加仓”，但由于冻结晚于主结果揭示，只能做机制诊断，不能充当预注册或 promotion 证据。

## 2026-08-03：完成丈量，维持 diagnostic-only

共同窗口显示 HYPE 绝对振幅显著更大，但 scaled amplitude 不领先，`3d` daily efficiency 显著更低，`14d` 强趋势率点估计最低。冻结的 `7d/28d` admission 在 HYPE 双方向、三 horizon 全负；揭示后 onset-followthrough 也未验证初始位移越强、未来越延续。BTC/ETH 出现资产和方向依赖的候选证据，证明跨资产研究有意义，但不支持复制同参数。维持 `diagnostic-only / no version / not promoted / not live-ready`；后续只能从新合同和 prospective OOS 开始。详见[趋势生态丈量报告](diagnostics/binance-1h-fatha-trend-ecology-report-2026-08-03.md)。
