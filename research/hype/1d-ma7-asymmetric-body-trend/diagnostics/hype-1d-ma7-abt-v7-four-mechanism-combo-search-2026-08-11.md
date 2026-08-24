# HYPE-1D-MA7-ABT-V7 四机制组合参数搜索诊断

## 结论

240个固定组合搜索后，只有一类候选在已揭示全窗上双优：**不启用 pending reclaim、不改 cooldown、不依赖 overbought 入场，只把 short RSI 止盈从 `RSI6<20 × 2d` 放宽到 `RSI6<25 × 2d`**。

该候选为 `POST_REVEAL_CANDIDATE_ONLY`：全窗从 V7 的 `+711.04%/-18.40%` 小幅变成 `+715.71%/-18.40%`，交易数仍为20笔，8个block全部正收益。但增益只有 `+4.67pp`，且来自已揭示历史中的一笔空头提前止盈，不构成 V7 改版依据。

## 搜索口径

- 网格：pending reclaim `6`档 × short RSI `5`档 × cooldown `2`档 × overbought exhaustion `4`档，共240个候选。
- Stage A：全部候选跑全窗基础回放。
- Stage B：所有全窗双优候选 + 收益前20个非control 候选跑完整压力包。
- Control：`P0__R20x2__CG__O0`，即 exact V7。
- 成本：手续费 `0.001/fill`、基础滑点 `4 bps/fill`、压力滑点 `8 bps/fill`，计真实 Binance funding。

## Top 结果

| Candidate | 机制差异 | 全窗收益 | 真实1h MDD | 交易数 | 压力裁决 |
| --- | --- | ---: | ---: | ---: | --- |
| `P0__R25x2__CG__O0` | short RSI `20×2 -> 25×2` | `+715.71%` | `-18.40%` | 20 | `POST_REVEAL_CANDIDATE_ONLY` |
| `P0__R25x2__CG__O70_3of5_D010` | 同上；overbought 信号被阻挡/无实际新增交易 | `+715.71%` | `-18.40%` | 20 | `POST_REVEAL_CANDIDATE_ONLY` |
| `P0__R25x2__CG__O70_4of6_D025` | 同上 | `+715.71%` | `-18.40%` | 20 | `POST_REVEAL_CANDIDATE_ONLY` |
| `P0__R25x2__CG__O75_3of5_D010` | 同上 | `+715.71%` | `-18.40%` | 20 | `POST_REVEAL_CANDIDATE_ONLY` |
| `P0__R20x2__CG__O0` | V7 control | `+711.04%` | `-18.40%` | 20 | `CONTROL` |

四个 top overbought 版本等价，不是因为 overbought 有效，而是因为实际路径没有新增成交；真正贡献只有 `R25x2`。

## 压力结果

`P0__R25x2__CG__O0`：

- 全窗：`+715.71% / -18.40%`，20笔，short RSI exit 4次。
- `8 bps`：`+703.35%`，仍为正。
- 额外 `1d lag`：`+276.83%`，仍为正。
- 8个54日block：`8/8`正收益。
- 相对 V7：收益 `+4.67pp`，真实 `1h` MDD 基本不变，交易数不变。

逐笔差异只有一处：2025-09-20 开空的第7笔交易，V7 在 `2025-10-01` 以 `ma7_slope_exit` 平仓，单笔约 `+17.59%`；`R25x2` 在 `2025-09-24` 因 `short_rsi_take_profit` 平仓，单笔约 `+18.28%`，同时少承受后续 funding/持仓拖累。其余交易结构不变。

## 失败组合

pending reclaim 相关候选仍不行。进入压力包的 `P_BUFFER_D3_A100` 系列只新增1笔 episode confirm，但收益大幅低于 V7，MDD 从 `-18.40%` 扩到 `-22.31%`，说明“等 buffer 后成熟”仍然是在放噪声。

方向性 cooldown 和 overbought exhaustion 没有在 top 区域形成有效新增收益。overbought 触发在部分候选里出现，但多数只是被 cooldown 阻挡或不改变成交路径；一旦配合更宽入口，收益和 MDD 都恶化。

## 裁决

- `R25x2` 是唯一值得记录的 post-reveal 小候选，但只能作为未来 clean prospective observer 假设。
- 不修改 V7；不登记 V8；不生成 HTML；不创建 live spec；不推进 runner。
- 如果继续，应把 `short_rsi_threshold=25, days=2` 作为单独观察点，不能把 pending/cooldown/overbought 组合打包带入。

## 证据

- [组合搜索合同](../specs/hype-1d-ma7-abt-v7-four-mechanism-combo-search-contract-2026-08-11.md)
- [完整机器证据](../artifacts/hype_1d_ma7_abt_v7_four_mechanism_combo_search_2026-08-11.json)
- [机器证据 SHA256](../artifacts/hype_1d_ma7_abt_v7_four_mechanism_combo_search_2026-08-11.json.sha256)
- [组合搜索脚本](../scripts/audit_hype_1d_ma7_abt_v7_four_mechanism_combo_search.py)
