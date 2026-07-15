# BIN-15M-AS6S V6 消融与微调完成审计（2026-07-15）

结论：`PASS`。冻结 V6 的 15 条腿全部可以追溯到完整消融、clean-surface
分类、局部微调和最终账户级替换审计；未来 OOS 未读取，冻结参数未修改。

## 15 条腿覆盖

| 来源 | 腿数 | 消融证据 |
| --- | ---: | --- |
| 15m frontier | 8 | 138 次组件变体执行，覆盖每腿 baseline、过滤、方向、止盈、止损诊断和持仓上限；结构本体与灾难风控不做无意义零交易删除 |
| HYPE Clean-RSI | 1 | 10 次组件变体执行，另标记 RSI crossing 本体、固定风险条件和 4 个精确 no-op |
| 旧 1h asset-specific | 6 | 每腿 34 个参数组，共 204 组、381 次执行变体 |
| 合计 | 15 | 与 V6 冻结 `selected_sleeves` 集合完全一致 |

这里的“全参数”口径是每个字段必须被分类为：可删除 no-op、保留 active、允许
微调或机制/灾难风控固定字段。不会通过删除机制窗口制造零交易来伪装消融，也
不会删除最长持仓、灾难止损和 K+1 执行合同。

## 清理与微调

- clean surface 覆盖 `15/15` 条腿。
- 字段实例共删除 `242` 个 no-op，保留 `213` 个 active，其中 `169` 个进入局部
  微调接口。删除字段与保留字段无交集，所有微调字段均属于保留字段。
- 8 条 frontier 腿生成 `2400` 个候选。
- HYPE Clean-RSI 生成 `500` 个候选。
- 6 条旧 1h 腿生成 `1800` 个候选。
- 合计 `4700` 个局部候选；选择只使用 `<2026-07-14T09:00:00Z` 数据。

冻结 JSON 为保持跨机制统一 schema，仍可能保存已关闭字段的占位值；这些字段
已经从 active/tunable 参数表面删除，不参与 V6 调参。Runner 严格逐笔对拍证明
兼容占位值不会改变冻结路径。

## 最终账户级审计

| 路线 | 整腿删除 | 每腿稳健配置替换 | scale 邻域 | 路由邻域 | 可删除腿 |
| --- | ---: | ---: | ---: | ---: | --- |
| `nonpreemptive` | 15 | 134 | 7 | 不适用 | 无 |
| `strong_breakout_preemptive` | 15 | 134 | 7 | 7 | 无 |

两条路线的逐腿删除都按完整 mark-price 保护和联合账户时序重路由，不是把单腿
收益简单相加。最终审计还逐腿替换其余稳健配置，因此能区分“这条腿不可删”与
“只有某一个精确参数点可用”。

## 可复现检查

运行：

```bash
uv run python research/asset-portfolios/15m-asset-specific-six-strategy-selector/scripts/audit_binance_as6s_v6_ablation_microtune_completion.py
```

脚本只读取冻结点以前已经保留的消融与微调 artifact，不加载未来窗口行情。
机器可读结果：
[`binance_as6s_v6_ablation_microtune_completion_audit_2026-07-15.json`](../artifacts/binance_as6s_v6_ablation_microtune_completion_audit_2026-07-15.json)。
来源证据：

- [frontier 全消融](../ablations/binance-as6s-v5-frontier-full-ablation-2026-07-15.md)
- [Clean-RSI 全消融](../ablations/binance-as6s-v5-clean-rsi-full-ablation-2026-07-15.md)
- [旧 1h 精确全参数消融](../ablations/binance-as6s-v5-legacy-exact-full-ablation-2026-07-15.md)
- [V6 clean surface](../ablations/binance-as6s-v6-clean-surface-2026-07-15.md)
- [最终账户审计](binance-as6s-v6-mark-clean-rsi-joint-candidate-audit-2026-07-15.md)
