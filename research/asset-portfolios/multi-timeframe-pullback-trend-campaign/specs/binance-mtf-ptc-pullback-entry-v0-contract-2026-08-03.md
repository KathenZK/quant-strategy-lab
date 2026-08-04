# BIN-MTF-PTC Pullback Entry Diagnostic V0（2026-08-03）

## 目的

只在 validation 比较同一批强 continuation candidates 的即时追价与冻结回调入场，不运行 locked historical evaluation，不选择最终参数。

## 候选

- 24h onset continuation meter；
- 72h label 模型；
- development 拟合；development 预测概率 80% 分位作为强候选门槛；
- validation 事件只用于入场诊断。

## 回调与 restart

- 最浅 `0.5×ATR1h(24)`；最深 impulse leg 50%；最多等待24h；1h close 穿 origin 失效；
- 新高/新低发生的同一 1h bar 不利用未知 intrabar 顺序立即 armed；
- armed 后至少两个 closed 15m 不再创新低/高，随后 close 突破此前4根极值且位于顺势半区；
- next 15m open adverse fill。

## 公平比较

- immediate：candidate close 后下一15m open；
- pullback：上述 restart 后 next open；
- 对 pullback 真正成交的相同 candidates 比较未来72h `+1R before -0.5R`、MFE、MAE、terminal progress 和成交价格改善；
- 未回调/失效/无 restart 单独报告，不把未成交机会算胜单。

