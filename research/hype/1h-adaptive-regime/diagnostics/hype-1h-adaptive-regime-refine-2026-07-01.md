# HYPE-1H-Adaptive-Regime Pareto 邻域精调 - 2026-07-01

## 结论

第二轮仍没有出现 locked hard-gate 命中，结论保持 `NO-GO / not promoted`。

- 输入 seed：`205`；生成 unique neighbors：`180000`；可交易评估：`171730`；prefit eligible：`129669`。
- prefit hard-shape observations：`0`；locked target pass：`0/460`。
- seed 与邻域排序只使用第一轮 prefit CSV 的 train/validation 字段；第二轮 finalists 冻结后才读取 locked holdout。

## 最佳冻结结果

- id：`ENS__HYPE_1H_AR_N026857__HYPE_1H_AR_N090440`；style：`di_cross+stoch_reversal`。
- full：annual `9.73x`，return `795.75%`，DD `-19.64%`，win `78.26%`，trades `69`。
- locked holdout：annual `5.22x`，return `43.05%`，DD `-19.64%`，win `75.00%`，trades `16`。
- target pass：`False`。

## 时间切片

| Window | Annual | Return | DD | Win | Trades | PF |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `train` | `12.52x` | `281.63%` | `-16.93%` | `84.21%` | `38` | `7.019` |
| `validation` | `9.82x` | `64.08%` | `-11.35%` | `66.67%` | `15` | `8.027` |
| `locked_holdout` | `5.22x` | `43.05%` | `-19.64%` | `75.00%` | `16` | `4.342` |
| `full` | `9.73x` | `795.75%` | `-19.64%` | `78.26%` | `69` | `6.486` |
| `last_30d` | `45.16x` | `36.75%` | `-16.37%` | `88.89%` | `9` | `5.970` |
| `last_60d` | `6.64x` | `36.49%` | `-19.64%` | `73.33%` | `15` | `3.914` |
| `last_90d` | `4.16x` | `42.11%` | `-19.64%` | `70.59%` | `17` | `4.101` |
| `rolling_block_01` | `5.53x` | `15.08%` | `-10.55%` | `100.00%` | `4` | `inf` |
| `rolling_block_02` | `0.81x` | `-1.70%` | `-9.71%` | `50.00%` | `2` | `0.707` |
| `rolling_block_03` | `18.61x` | `27.14%` | `-10.81%` | `100.00%` | `5` | `inf` |
| `rolling_block_04` | `116.43x` | `47.81%` | `-14.90%` | `90.00%` | `10` | `8.425` |
| `rolling_block_05` | `44.57x` | `36.60%` | `-7.42%` | `100.00%` | `7` | `inf` |
| `rolling_block_06` | `14.25x` | `24.39%` | `-16.93%` | `57.14%` | `7` | `3.390` |
| `rolling_block_07` | `39.77x` | `35.33%` | `-12.90%` | `62.50%` | `8` | `6.370` |
| `rolling_block_08` | `1.21x` | `1.61%` | `-9.82%` | `60.00%` | `5` | `1.507` |
| `rolling_block_09` | `16.78x` | `26.07%` | `-11.35%` | `80.00%` | `5` | `37.193` |
| `rolling_block_10` | `2.50x` | `7.83%` | `-4.80%` | `100.00%` | `2` | `inf` |
| `rolling_block_11` | `1.26x` | `1.94%` | `-19.64%` | `55.56%` | `9` | `1.234` |
| `rolling_block_12` | `80.77x` | `30.15%` | `-4.55%` | `100.00%` | `5` | `inf` |

## 状态

`NO-GO / not promoted`；不得标记 candidate、paper-live、dry-run、handoff 或 live。
