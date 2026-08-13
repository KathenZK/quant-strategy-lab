# HYPE-1D-MA7-ABT-V7 Reverse-K RSI Follow-Through 诊断

## 结论

把“反向K+RSI极值”从直接入场改成背景标签，并要求后续同方向 follow-through 后，终于出现了一个 **post-reveal 小候选**：

`FT_long_only_R0p50_A2_P0p25_D1p25_L0p50`

它是 long-only、前10日反向K占比至少50%、tag后2日内推进至少 `0.25 ATR`、距离不超过 `1.25 ATR`、目标杠杆 `0.5x`。结果为 `+728.96%/-17.87%`，相对 V7 的 `+711.04%/-18.40%` 小幅双优，完整压力包通过，裁决 **`POST_REVEAL_CANDIDATE_ONLY`**。

但它没有解决全部三段行情：它主要补到 `2026-04-04/05` 这类多头 follow-through，以及样本末端 `2026-08-04/05`；没有补到 `2025-08-07`，也不处理 `2026-02-06/09/10` 空头。放宽到能补更多目标时，收益和 MDD 又明显恶化。

## 冻结口径

- Control：`CTRL_EXACT_V7`。
- 机制：V7 原生 entry 优先；raw MA7 cross 当天只建立 reverse-rsi tag，不直接入场；后续 `1-4d` 内若仍在 MA7 正确侧、相对 tag 日 close 有足够同方向推进、且距离不过远，才次日 open 入场。
- 网格：`side_scope` 3档 × `reverse_ratio` 2档 × `max_age` 2档 × `min_progress_atr` 3档 × `max_distance_atr` 3档 × `target_leverage` 3档，共324个候选。
- 成本：手续费 `0.001/fill`、基础滑点 `4 bps/fill`、压力滑点 `8 bps/fill`，计真实 Binance funding；风险 replay 为真实 `1h` 顺序。

## Top 结果

| Candidate | 机制 | 全窗收益 | 真实1h MDD | 交易数 | tag/confirm | 裁决 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `CTRL_EXACT_V7` | V7 control | `+711.04%` | `-18.40%` | 20 | 0/0 | `CONTROL` |
| `FT_long_only_R0p50_A2_P0p25_D1p25_L0p50` | long-only、50%、2日、推进0.25ATR、距离1.25ATR、0.5x | `+728.96%` | `-17.87%` | 23 | 10/2 | `POST_REVEAL_CANDIDATE_ONLY` |
| `FT_long_only_R0p60_A2_P0p25_D1p25_L0p50` | 同上，60%反向K | `+728.96%` | `-17.87%` | 23 | 6/2 | `POST_REVEAL_CANDIDATE_ONLY` |
| `FT_long_only_R0p50_A2_P0p25_D1p25_L1p00` | 同上，满仓 | `+783.65%` | `-20.98%` | 23 | 10/2 | `FAIL / higher-return-higher-risk` |
| `FT_long_only_R0p50_A2_P0p50_D1p25_L1p00` | 推进0.50ATR | `+711.04%` | `-18.40%` | 20 | 10/0 | `FAIL` |

冠军压力包：

- `8 bps`：`+715.06%/-18.11%`；
- funding-off：`+731.26%/-18.04%`；
- 额外 `1d lag`：`+284.07%/-26.45%`；
- 8个54日block：`8/8` 正收益，worst block MDD `-16.42%`。

## 触发解释

冠军候选一共建立10个 long tag，但只有2个确认入场：

1. `2026-04-04` 建 tag，`2026-04-05` 确认，`2026-04-06` 以 `0.5x` 入场，`2026-04-20` protective stop 退出，单笔约 `+5.26%`；
2. `2026-08-04` 建 tag，`2026-08-05` 确认，样本末端 terminal flatten，单笔约 `+1.56%`。

它没有补到 `2025-08-07`：该段 tag 成立，但满足推进时距离 MA7 已超过 `1.25 ATR`，被距离上限过滤。若放宽到 `1.50 ATR` 或 `INF`，会补更多，但结果恶化，例如 `FT_long_only_R0p50_A2_P0p25_D1p50_L0p50` 只有 `+569.02%/-21.56%`。

它也没有补 `2026-02-06/09/10`，因为冠军是 long-only。加入 short 或 both 后噪声明显增加，未进入可候选区。

## 裁决

`FT_long_only_R0p50_A2_P0p25_D1p25_L0p50` 是目前这些补漏实验里第一个通过压力包的小候选，但它仍然是已揭示历史上的 post-reveal 结果。它不改 V7，不登记 V8，不生成 HTML，不创建 live spec，不推进 runner。

如果继续推进，只能把它作为 clean prospective observer 假设：观察 long-only reverse-rsi tag 后 `1-2d` 的 follow-through 是否在未来样本继续有正贡献。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v7-reverse-rsi-followthrough-contract-2026-08-11.md)
- [完整机器证据](../artifacts/hype_1d_ma7_abt_v7_reverse_rsi_followthrough_2026-08-11.json)
- [机器证据 SHA256](../artifacts/hype_1d_ma7_abt_v7_reverse_rsi_followthrough_2026-08-11.json.sha256)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v7_reverse_rsi_followthrough.py)
