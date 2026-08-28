# HYPE-1D-MA7-MLT P0：365 日训练 / 后段验证结果

> 日期：2026-08-27。裁决：`ML_NO_EDGE`。状态：`diagnostic-only / not promoted / not live-ready`。验证揭示后未重选模型、阈值、特征、持有期或规则参数；未修改 V7.1 或 runner。

## 先看结论

这轮机器学习没有比“不断搜 MA 参数”做得更好，而且验证失败幅度很大。

- 训练内 ML champion 看起来最强：`+204.34%`、PF `2.741`，四折 `3/4` 盈利；但锁定 81 日验证为 `-38.64%`、MDD `-52.87%`、PF `0.285`。
- 同样只在训练集选择的 4,320 组 MA 规则 champion，验证为 `-2.64%`、MDD `-30.80%`、PF `1.019`；也没有形成可靠 alpha，但显著少亏。
- 同期按同成本/funding 的买入持有为 `+0.62%`、MDD `-30.53%`。
- exact V7.1 在相同起止时间描述性为 `+28.19%`、真实 `1h` 顺序 MDD `-8.52%`、3 笔全胜；但 V7.1 的规则开发曾看过这段历史，且它有 OAPP/PEHC/RSI/保护状态机，不能冒充本轮 clean OOS 或等机制公平对照。

大白话：**ML 把前 365 日学得比参数搜索更漂亮，但学到的是会随 regime 翻转的历史关系；进入后 81 日，它比简单规则更自信、更高频地做错。**

## 冻结设计

- 数据：Binance USD-M `HYPEUSDT` perpetual trusted `1h`，每个 UTC 日必须有 24 根显式 closed 小时 K 才聚合为 `1d`；小时和日线质量均 `0 blocker`。
- 完整日线：`2025-05-31` 至 `2026-08-19`，446 日；terminal open 为 `2026-08-20`。
- 训练：最前 365 日，至 `2026-05-30`；所有标签在验证首日 open 前完整结束。
- 验证：`2026-05-31` 至 `2026-08-20` open，共 81 个持有日收益区间。
- 共同执行：日收盘信号、下一 UTC open 成交、固定 `1x`、单仓、不加仓；单边手续费 `10 bps` + 滑点 `4 bps`，另计实际 funding。
- 共同退出：固定 `3/7/14d`；P0 不含盘中 stop，因此只能诊断预测能力，不能讨论 live-ready。
- [冻结合同](../specs/hype-1d-ma7-mlt-p0-365d-train-validation-contract-2026-08-27.md)

## 训练内唯一候选

| 路线 | 冻结 champion | 四折收益 | 拼接收益 | MDD | PF | 笔数 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| ML | `LGBM_B / H7 / edge>0` | `-25.58% / +58.17% / +58.64% / +62.97%` | `+204.34%` | `-43.01%` | `2.741` | 30 |
| MA 参数搜索 | `MA7 / slope1>0 / gap>0.5ATR / H14 / long-only` | `-19.29% / +21.27% / +25.41% / +44.26%` | `+77.07%` | `-19.88%` | `4.116` | 8 |

ML 在训练内已经有两个预警：第一折明显亏损，最大回撤达到 `43.01%`；最终选择的 edge 为严格 `>0`，几乎没有置信度缓冲。P0 合同要求无论候选是否稳健都锁定一个 diagnostic champion 揭示验证，因此不能在看到失败后改成另一模型或提高阈值。

## 锁定验证结果

| 路线 | 净收益 | MDD | PF | 胜率 | 笔数 | Long / Short | 暴露日 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ML | `-38.64%` | `-52.87%` | `0.285` | `33.33%` | 12 | `8 / 4` | 79 |
| train-only MA 参数搜索 | `-2.64%` | `-30.80%` | `1.019` | `25.00%` | 4 | `4 / 0` | 56 |
| 买入持有 | `+0.62%` | `-30.53%` | 描述性 | 1 | 1 | `1 / 0` | 81 |
| exact V7.1（污染参考） | `+28.19%` | `-8.52%` | 无亏损笔 | `100%` | 3 | `2 / 1` | 非同机制 |

ML 相对 train-only 规则少 `36.00pp`，相对买持少 `39.26pp`；MDD 比规则恶化 `22.08pp`。满足预注册 `ML_NO_EDGE`：净收益为负且 PF `<1`。

成本不是失败主因：ML 的累计成本约为初始权益 `3.11%`，funding 净支出约 `0.52%`；即使粗略忽略二者，也无法解释 `-38.64%` 的亏损。

## ML 是怎么错的

验证 81 个决策日里，模型给出 50 个 long、26 个 short、仅 5 个 flat，最终暴露 79 日。它没有学出有效的“什么时候不要交易”。

逐笔路径显示两个关键方向错误：

1. `2026-07-07` 后连续维持/重开 long，在 `70.609 → 63.444 → 62.448 → 56.086 → 53.999` 的下跌段产生多次损失；四笔主要 long 亏损约 `-10.48% / -1.93% / -10.46% / -4.13%`。
2. `2026-08-11` 后模型转为 short，却遇到上涨，最后两笔 short 为 `-7.72%` 和 terminal mark `-18.29%`。即使最后一笔尚未走满 7 日而视为 censored，前面成熟交易整体仍为负，不能把失败归因于单一末端截断。

这不是“预测准确率稍低”，而是趋势 regime 翻转时方向和暴露同时失效。模型在训练段捕捉到的 K 线/MA/波动关系没有迁移到验证段。

## 与 V7.1 应怎样理解

V7.1 描述性结果明显更好，但不能得出“手工规则天然优于机器学习”的普遍结论：

- V7.1 的开发看过验证历史，存在 post-reveal 优势；本轮 ML 没看过。
- V7.1 不是固定 7/14 日退出；它用 long OAPP、short RSI、PEHC handoff、cooldown 和真实 1h 保护，机制更完整。
- V7.1 在该段只做 3 笔，ML 做 12 笔；V7.1 的优势主要来自选择性与持仓/退出链，而不是简单预测更多交易。

本轮能成立的严格结论只有：**用单一 HYPE 的 365 日训练一个端到端日线 LightGBM，再以固定 7 日持仓交易，远不如 V7.1，也没有胜过同训练集的简单 MA 参数搜索。**

## 决策

- P0：`ML_NO_EDGE / diagnostic-only / not promoted / not live-ready`。
- 不在已揭示 81 日验证上提高 edge、改标签、换模型、删掉 short 或挑另一个候选。
- 不登记 V1，不生成 live spec，不修改 V7.1，不授权 runner。
- 若以后继续，不能把这 81 日再当 OOS；必须使用未来新增数据，或另建多资产 pooled 训练合同并保留 HYPE 独立封存测试。

## 证据

- [机器摘要](../artifacts/hype_1d_ma7_mlt_p0_365d_train_validation_2026-08-27_summary.json)
- [ML 72 候选](../artifacts/hype_1d_ma7_mlt_p0_365d_train_validation_2026-08-27_ml_candidates.csv)
- [规则 4,320 候选](../artifacts/hype_1d_ma7_mlt_p0_365d_train_validation_2026-08-27_rule_candidates.csv)
- [验证预测](../artifacts/hype_1d_ma7_mlt_p0_365d_train_validation_2026-08-27_validation_predictions.csv)
- [验证逐笔](../artifacts/hype_1d_ma7_mlt_p0_365d_train_validation_2026-08-27_validation_trades.csv)
- [验证路径](../artifacts/hype_1d_ma7_mlt_p0_365d_train_validation_2026-08-27_validation_path.csv)
- [可拖动完整交易路径](../artifacts/hype_1d_ma7_mlt_p0_365d_train_validation_2026-08-27_trade_paths.html)
- [V7.1 描述性参考](../artifacts/hype_1d_ma7_mlt_p0_365d_train_validation_2026-08-27_v7_1_descriptive_reference.json)
- [研究脚本](../scripts/run_hype_1d_ma7_mlt_p0.py)

