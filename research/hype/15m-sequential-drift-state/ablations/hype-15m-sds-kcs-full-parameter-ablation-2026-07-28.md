# HYPE-15M-SDS KCS 全参数消融

## 结论

对 Kalman + CUSUM + 结构确认最不差失败参考完成 one-parameter-at-a-time 全参数消融。每次只替换一个参数，其他信号、成本、数据和执行合同保持冻结。

- active 参数：21 个，其中信号/状态 18 个，执行风险 3 个；
- 单参数变体：85 个；
- 满足 train `>=30`、validation `>=10` 笔：73 个；
- train 正收益：8 个；
- validation 正收益：0 个；
- train/validation 同时正收益：0 个；
- 合格候选：0 个；
- reused OOS 读取：否。

全消融没有发现可以单独修复策略的参数。保持 `NO-GO / not registered / not promoted / not live-ready`。

## 冻结失败参考

| 窗口 | Return | MaxDD | Trades | Win rate |
| --- | ---: | ---: | ---: | ---: |
| Train | -10.02% | -28.47% | 47 | 34.04% |
| Validation | -5.93% | -9.12% | 10 | 20.00% |
| Prefit | -15.36% | -28.47% | 57 | 31.58% |

机器合同和完整参数范围见 [full ablation contract](../artifacts/hype_15m_sds_kcs_full_ablation_contract.json)。

## 最容易误读的“最佳行”

总排名第一是 `leverage=0.5`：

| 参数 | Train | Validation | Prefit | MaxDD | Trades |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline 1x | -10.02% | -5.93% | -15.36% | -28.47% | 57 |
| leverage 0.5x | -4.71% | -2.99% | -7.56% | -15.30% | 57 |

57 笔成交路径逐项相同，只是把盈亏机械缩小，不是信号改善。提高到 `1.5x/2x/3x` 分别把 prefit 亏损放大到 `-23.19%/-30.91%/-45.48%`。

## 真正改变信号的领先变体

| 单参数变体 | Train | Validation | Prefit | MaxDD | Trades | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `kalman_slope_vol_entry=0.40` | +5.11% | -8.27% | -3.58% | -14.29% | 45 | 入场更严，train 改善但 validation 更差 |
| `kalman_slope_vol_exit=-0.10` | +10.48% | -10.35% | -0.95% | -30.48% | 53 | 更晚退出适配 train，跨段翻转 |
| `cusum_entry=7` | -2.25% | -7.08% | -9.17% | -25.85% | 48 | 稳定减少噪声，但仍负 |
| `kalman_slope_z_entry=2` | -6.86% | -7.01% | -13.38% | -23.45% | 53 | 小幅降回撤，无正期望 |
| `volatility_span=72` | -8.82% | -5.93% | -14.22% | -28.66% | 57 | 仅轻微变化 |
| `structure_window=128` | -8.82% | -5.93% | -14.23% | -28.71% | 56 | 仅少一笔交易 |
| `exit_window=24` | -10.05% | -5.40% | -14.91% | -28.30% | 57 | 改善极小 |

两条最接近零的信号变体恰好表现为 train 正、validation 明显负，不能组合为新候选。

## 低样本伪改善

| 变体 | Train | Validation | Prefit | MaxDD | Train/Val Trades | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `cusum_entry=10` | +13.26% | -5.66% | +6.85% | -11.16% | 22 / 9 | validation 不足10笔且为负 |
| `efficiency_window=96` | +8.52% | -0.54% | +7.93% | -16.04% | 17 / 2 | 样本严重不足 |
| `efficiency_window=128` | +11.30% | -1.58% | +9.54% | -6.88% | 9 / 1 | 基本不可判断 |

这些行证明过滤越严，历史表面越容易变漂亮，但 validation 始终没有转正。不能把少数幸运交易当成参数突破。

## 21 个参数的消融判断

| 参数 | 观察到的最好单变量表现 | 判断 |
| --- | --- | --- |
| `volatility_span` | `72`，prefit -14.22% | 活跃但弱敏感 |
| `kalman_process_ratio` | 所有变体都比 baseline 差 | baseline 附近已较好 |
| `kalman_measurement_multiplier` | 所有变体都更差 | baseline `4` 有效 |
| `kalman_slope_vol_entry` | `0.40`，prefit -3.58% | 有效旋钮，但跨段失败；`0.01–0.20` 路径等价 |
| `kalman_slope_z_entry` | `2`，prefit -13.38% | 有小幅过滤价值 |
| `kalman_slope_vol_exit` | `-0.10`，prefit -0.95% | 最敏感退出旋钮，但 train/validation 反向 |
| `cusum_allowance` | 变体均不通过；`0.50` 低样本接近零 | 提高会过度稀疏 |
| `cusum_entry` | `7` 为有效样本最不差；`10` 低样本表面转正 | 更严有帮助，但没有验证稳定性 |
| `structure_window` | `16–96` 路径完全相同，`128` 只少一笔 | 窗口在常用区间基本 dormant |
| `exit_window` | `24–64` validation 略改善 | 活跃但影响很小 |
| `efficiency_window` | `96/128` 表面转正但只剩19/10笔 | 极敏感，容易制造低样本假象 |
| `efficiency_min` | 放宽全部显著恶化 | baseline `0.30` 是关键降噪 |
| `arm_timeout_bars` | 所有变体比 baseline 差 | baseline `8` 有效 |
| `exit_confirm_bars` | 所有变体比 baseline 差 | baseline `2` 有效 |
| `require_cusum` | 关闭后 prefit -28.70% | CUSUM 必须保留 |
| `require_kalman` | 关闭后 prefit -17.22% | Kalman 有边际价值 |
| `require_structure` | 关闭后 prefit -27.76% | 结构确认必须保留 |
| `require_efficiency` | 关闭后 prefit -83.20% | 最重要的降噪模块 |
| `stop_atr` | 所有替代值均比 baseline `4ATR` 差 | 风险参数活跃但不产生 alpha |
| `max_hold_bars` | `96–1536` 成交和权益路径完全相同 | 全范围 dormant；保留只作为安全上限 |
| `leverage` | 成交路径完全相同，收益线性缩放 | 仅 sizing，不是信号参数 |

## Path-equal 审计

共有 16 个变体与 baseline 的逐笔路径完全相同：

- `kalman_slope_vol_entry=0.01/0.025/0.10/0.20`
- `structure_window=16/32/48/96`
- `max_hold_bars=96/192/768/1536`
- `leverage=0.5/1.5/2/3`：成交相同，权益因 sizing 不同

其中只有 `max_hold_bars` 的所有变体连权益也完全相同，属于确定的 dormant safety slot。`structure_window` 参数值大部分 path-equal，但 `require_structure=false` 会显著恶化，说明结构模块有效，只是常用窗口长度没有实际区分力。

## 为什么不能把各参数最好值组合

one-at-a-time 消融回答的是“从同一个 baseline 出发，单独改这个参数发生什么”，不是组合搜索。把以下值事后拼起来：

```text
slope entry 0.40
slope exit -0.10
CUSUM 7或10
efficiency window 96/128
```

会直接使用已经观察过的 train/validation 结果进行二次拟合。尤其这些值的改善来自不同交易子集，并且共同特征是 validation 为负或样本不足，不能授权组合调优。

## 决定

- 全参数消融没有改变 KCS 的 NO-GO。
- 不组合“最好值”，不读取 reused OOS，不登记版本。
- 参数层面已经解释清楚：更严格过滤可以降低交易数和历史亏损，但无法建立跨段正期望。
- 若继续，应改变信息源而不是继续扩大 OHLCV 参数范围。

## 证据

- [全量消融 CSV](../artifacts/hype_15m_sds_kcs_full_ablation.csv)
- [参数汇总 CSV](../artifacts/hype_15m_sds_kcs_full_ablation_parameter_summary.csv)
- [消融汇总 JSON](../artifacts/hype_15m_sds_kcs_full_ablation_summary.json)
- [消融脚本](../scripts/research_hype_15m_sds_kcs_full_ablation.py)
