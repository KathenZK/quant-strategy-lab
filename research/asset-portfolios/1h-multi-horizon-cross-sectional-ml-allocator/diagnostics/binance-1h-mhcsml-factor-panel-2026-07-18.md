# BIN-1H-MHCSML 因子与标签面板审计（2026-07-18）

## 结论

- 因子/标签门禁：`PASS`。
- 面板范围：`2020-01-31 00:00 <= ts <= 2026-06-30 23:00 UTC`，共 `6,961,195` 行、`654` 个实际满足 PIT 条件的历史合约。
- 模型候选特征共 `241` 个：182 个单币连续因子、48 个横截面排名因子、11 个流动性/市场状态上下文特征。
- 标签覆盖 `4/8/12/24/48h` 的 long/short 净收益、funding、MAE/MFE、10%/20% squeeze/crash；所有期限均通过线性收益恒等式和路径有效性检查。
- 面板中 prospective OOS 行数为 `0`，本轮没有读取 `2026-07-19` 起的标签或绩效。

## 因子构成

基础库在原 142 个趋势、动量、反转、波动率、量价、order-flow、funding、mark-premium 和生命周期因子上新增 40 个尾部特征：

- 上行半波动率、收益峰度；
- 过去窗口极端单小时上涨/下跌；
- 3% 上下跳跃次数；
- 最大 K 线振幅；
- taker imbalance 波动；
- 实际 funding event 累计；
- mark premium 历史最大/最小值。

横截面层对 48 个关键因子按每小时 PIT universe 排名，并加入 BTC 相对收益、市场宽度、波动率中位数/离散度、收益离散度和正 funding 占比。

特征覆盖率中位数为 `100%`，无穷值为 `0`，所有横截面 rank 位于 `[0,1]`。低于 95% 覆盖率的 8 个特征中，6 个是仅在突破事件发生时非空的 Donchian strength；模型矩阵将其结构性空值解释为“未发生事件”并填 `0`。另外两个短窗口 funding z-score 保留缺失，让模型按历史可用性处理。

## 标签定义与审计

K0 收盘后计算因子，K1 open 入场，在 `K(h+1)` open 退出：

```text
gross_h = exit_open / entry_open - 1
long_net_h = gross_h - 0.0028 - funding_sum_h
short_net_h = -gross_h - 0.0028 + funding_sum_h
```

所有有效标签满足：

```text
long_net_h + short_net_h = -2 * 0.0028
```

五个期限最大浮点误差均为 `1.16e-15`。有效路径没有空标签，无效路径没有残留 long/short 标签；MAE 全部 `<=0`，MFE 全部 `>=0`。

| 期限 | 有效标签行 | 因停牌/样本尾部失效行 |
| --- | ---: | ---: |
| 4h | `6,960,395` | `800` |
| 8h | `6,959,755` | `1,440` |
| 12h | `6,959,115` | `2,080` |
| 24h | `6,957,185` | `4,010` |
| 48h | `6,953,321` | `7,874` |

任何 entry-to-exit 路径与 nontradable interval 相交时，`label_path_valid=false`，收益和尾部标签均为空；不使用前值填充，也不把停牌前后价格直接当作可执行持有期收益。

## 泄漏与结构检查

- `(ts, symbol)` 重复键：`0`；空键：`0`；最大 liquidity rank：`150`。
- 单币因子未来扰动测试：修改未来 80 根 K 线不会改变此前任何一个 182 因子值。
- 标签时序测试：验证 K0/K1/K(h+1)、正确 short 公式、funding 符号、停牌 fail-closed 和 MAE/MFE 截断。
- `2026Q2` 在面板中标记为 reused holdout；可做诊断，但不能承担未来 V1 的独立 OOS。

## 证据

- 面板构建：[build_multihorizon_factor_panel.py](../scripts/build_multihorizon_factor_panel.py)
- 面板审计：[audit_multihorizon_factor_panel.py](../scripts/audit_multihorizon_factor_panel.py)
- 因子未来泄漏测试：[test_multi_asset_tail_1h_factors.py](../../../../tests/test_multi_asset_tail_1h_factors.py)
- 标签时序测试：[test_multihorizon_labels.py](../../../../tests/test_multihorizon_labels.py)
- 本地审计 artifact：`artifacts/factor_panel_audit_2026-07-18.json`、`artifacts/factor_coverage_2026-07-18.csv`
- 本地数据 manifest：`artifacts/multihorizon_factor_dataset/factor_dataset_manifest.json`

本报告只证明数据、因子和标签可进入模型研究，不证明 LightGBM 或 allocator 有盈利能力。
