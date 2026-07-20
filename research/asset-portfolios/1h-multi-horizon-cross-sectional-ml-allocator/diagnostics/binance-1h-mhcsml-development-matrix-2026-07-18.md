# BIN-1H-MHCSML 历史开发矩阵隔离审计（2026-07-18）

## 结论

- 门禁：`PASS`。
- 模型矩阵只读取 `year_month < 2026-04` 的面板物理分区，未读取 2026Q2 reused holdout 或 prospective OOS 的标签与绩效。
- 矩阵共 `1,186,612` 行、`605` 个历史合约；范围为 `2020-01-31 00:00 <= ts <= 2026-03-31 20:00 UTC`。
- `ts >= 2026-04-01` 行数、非 4h 基准决策时点和 `(ts,symbol)` 重复键均为 `0`。
- 4h 基准网格可严格下采样为 `4/8/12/24h` 决策频率，不需要复制小时级全面板。

## 特征集合

| 集合 | 数量 | 用途 |
| --- | ---: | --- |
| `compact` | 86 | 第一阶段期限、模型与 allocator 粗筛 |
| `stable_full` | 235 | 覆盖率至少 80% 的完整稳定特征 |
| `full_plus_sparse` | 241 | 全量特征；6 个稀疏 Donchian 事件按“未发生”填 0 |
| `tail_stable` | 80 | 尾部、波动、跳跃、funding、premium 和 squeeze 风险消融 |

矩阵保留五个期限的 `path_valid`、long/short 净收益、funding、gross return、相对收益、long/short MAE/MFE 和 10%/20% crash/squeeze 标签。浮点列统一下转为 `float32`，键和布尔路径标志保持原语义。

## Walk-forward 契约

- Outer OOF：从 `2023H1` 到 `2026Q1` 共 7 个连续时间 fold。
- 每个 outer fold 训练截止到验证开始前 48 小时，避免最长 48h 标签跨界。
- 每个训练集尾部再保留 120 天 inner validation，并在 fit 与 inner 之间再次 purge 48h；用于 early stopping，不随机切分。
- 收益模型分别直接学习 long net 和 short net；风险模型分别学习 long/short MAE 的 80% 条件分位数，以及 long crash / short squeeze 事件概率。
- 所有模型预测只落在从未参与该模型拟合的 outer validation fold，allocator 只能读取这些 OOF 预测。

## 重叠持仓口径

持有期可以长于决策频率，因此每次决策作为独立 futures sleeve：

```text
sleeve_exposure = gross_exposure * min(1, decision_frequency / horizon)
```

每个 sleeve 在自己的退出时点结算 PnL，搜索脚本显式跟踪同时开放的 sleeve，要求最大计划 gross 不超过配置 gross exposure。空仓决策保留为 0 收益观察，不能从 Sharpe 或月份统计中删除。

## 证据

- 构建脚本：[prepare_development_model_matrix.py](../scripts/prepare_development_model_matrix.py)
- Walk-forward：[train_development_walk_forward.py](../scripts/train_development_walk_forward.py)
- Allocator：[search_development_allocator.py](../scripts/search_development_allocator.py)
- 重叠/空仓/同币双向测试：[test_mhcsml_allocator.py](../../../../tests/test_mhcsml_allocator.py)
- 本地 manifest：`artifacts/development_model_matrix_manifest.json`

本报告只确认历史开发隔离与验证结构，不代表模型或组合已经通过收益门槛，也不登记 `V1`。
