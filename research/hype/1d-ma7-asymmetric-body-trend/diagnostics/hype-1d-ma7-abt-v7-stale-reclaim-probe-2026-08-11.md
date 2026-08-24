# HYPE-1D-MA7-ABT-V7 Stale Reclaim Maturity Probe 诊断

## 结论

针对 `2025-08-07`、`2026-02-09/10`、`2026-04-07` 这类“第一天不成熟、后面趋势成熟”的漏判，跑了144个 `stale reclaim maturity probe` 候选。结果：**没有一个候选全窗双优，裁决 `FAIL / noise-releasing / diagnostic-only`**。

这说明问题确实存在，但用“过期 reclaim 后补票”的方式修，会带出更多同型噪声。即使用 `0.25x` 轻仓 probe，收益仍明显低于 V7，真实 `1h` MDD 也更差。

## 搜索口径

- Control：`CTRL_EXACT_V7`，即已登记 V7。
- 网格：`side_scope` 3档 × `min_age` 2档 × `max_age` 2档 × `max_distance_atr` 4档 × `probe_leverage` 3档，共144个候选。
- 机制：raw reclaim 当天 V7 未入场，后续 `1-4d` 内若 slope 与 buffer 成熟、仍在 MA7 正确侧、距离不过远，则次日 open 入场；stale 入场可按 `1.0/0.5/0.25` 目标杠杆执行。
- 成本：手续费 `0.001/fill`、基础滑点 `4 bps/fill`、压力滑点 `8 bps/fill`，计真实 Binance funding；风险 replay 为真实 `1h` 顺序。

## Top 结果

| Candidate | 机制 | 全窗收益 | 真实1h MDD | 交易数 | stale confirm | 裁决 |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `CTRL_EXACT_V7` | V7 control | `+711.04%` | `-18.40%` | 20 | 0 | `CONTROL` |
| `S_long_only_MIN2_MAX3_D1p25_L0p25` | long-only、age 2-3、距离<=1.25ATR、0.25x | `+572.40%` | `-20.90%` | 26 | 5 | `FAIL / noise-releasing` |
| `S_long_only_MIN2_MAX3_D1p25_L0p50` | 同上，0.50x | `+520.92%` | `-21.95%` | 26 | 5 | `FAIL / noise-releasing` |
| `S_long_only_MIN2_MAX4_D1p25_L0p25` | long-only、age 2-4、0.25x | `+457.15%` | `-20.90%` | 28 | 7 | `FAIL / noise-releasing` |
| `S_long_only_MIN2_MAX3_D1p50_L0p25` | long-only、距离<=1.50ATR、0.25x | `+455.39%` | `-20.90%` | 28 | 7 | `FAIL / noise-releasing` |

最高候选仍比 V7 少 `-138.64pp`，MDD 多 `-2.50pp`，交易数从20增到26。完整压力包下 `8 bps` 为 `+560.98%/-21.11%`，额外 `1d lag` 为 `+155.39%/-26.45%`，8个block全正，但不双优，裁决仍失败。

## 三段行情复盘

| 目标 | raw cross 起点 | 需要的机制宽度 | 结果 |
| --- | --- | --- | --- |
| `2025-08-07` 多头 | `2025-08-07` raw long reclaim，slope `0.003 < 0.02` | 至少允许 age 2、距离约 `1.38 ATR` 才能补到 `2025-08-09` | 能补，但同时引入更多 long 噪声，top候选未补到，宽候选表现差 |
| `2026-02-09/10` 空头 | `2026-02-06` raw short breakdown，buffer/slope都未成熟 | 需要 short、max_age 4，`2026-02-10` 才成熟 | short-only 或 both 候选收益/MDD显著恶化 |
| `2026-04-07` 多头 | `2026-04-04` raw long reclaim，buffer/slope都未成熟 | age 3、距离约 `1.17 ATR` | top long-only候选补到了这笔，但不足以抵消其他补票噪声 |

能覆盖三段的宽候选更差：`S_both_MIN1_MAX4_D1p50_L0p25` 为 `+161.13%/-37.12%`、35笔、stale confirm 23次；满仓版为 `+90.31%/-56.07%`。这说明三段目标行情和大量坏样本在同一个简单规则簇里，不能只靠 age/distance/probe 杠杆分开。

## 解释

这个实验确认了用户的直觉：V7 确实不会识别 stale reclaim 成熟行情。但同时也确认，**直接给 stale reclaim 补票不是解决方案**。只要规则允许 `1-4d` 后成熟补票，它会捕捉到 `2026-04-07` 这类好样本，也会捕捉到更多后续 recross、protective stop 或低质量 continuation。

下一步若继续研究，不能再用 MA7 reclaim 自身做唯一触发，需要额外信息区分质量，例如更高周期结构、成交量/波动压缩突破、趋势段效率、或更严格的在线回撤预算。否则会重复这次结果：补到肉眼痛点，但收益链条被噪声吃掉。

## 证据

- [冻结合同](../specs/hype-1d-ma7-abt-v7-stale-reclaim-probe-contract-2026-08-11.md)
- [完整机器证据](../artifacts/hype_1d_ma7_abt_v7_stale_reclaim_probe_2026-08-11.json)
- [机器证据 SHA256](../artifacts/hype_1d_ma7_abt_v7_stale_reclaim_probe_2026-08-11.json.sha256)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v7_stale_reclaim_probe.py)
