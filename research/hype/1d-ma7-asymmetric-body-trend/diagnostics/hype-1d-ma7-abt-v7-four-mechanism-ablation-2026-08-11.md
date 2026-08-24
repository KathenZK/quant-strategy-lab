# HYPE-1D-MA7-ABT-V7 四机制逐项消融诊断

## 结论

四个机制在 V7 上逐项 ablation 后，没有一个补出更好的 V7。裁决为 **`FAIL / diagnostic-only / not promoted / not live-ready`**。

最核心的发现是：用户指出的漏单确实存在，但 V7 当前的 fresh reclaim、全局 cooldown 与 PEHC 单向交接也在过滤大量噪声。把这些口子打开后，新增交易多数不能支付机会成本。

## 冻结口径

- Control：`CTRL_EXACT_V7`，即已登记 V7，short cooldown `3d`。
- 市场：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`；风险回放使用真实 `1h`。
- 数据：`2025-05-31` 至 `2026-08-05 UTC`，432 个完整日。
- 成本：手续费 `0.001/fill`、不利滑点 `4 bps/fill`，压力为 `8 bps/fill`，计真实 Binance funding。
- 本轮固定四个机制，不做参数搜索；组合臂只观察交互项，不作为 champion。

## 主结果

| Arm | 机制 | 全窗收益 | 真实1h MDD | 交易数 | 相对V7 | 裁决 |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `CTRL_EXACT_V7` | V7 control | `+711.04%` | `-18.40%` | 20 | - | `CONTROL` |
| `M1_PENDING_RECLAIM_MATURITY` | raw cross 后等待 slope/buffer 成熟 | `+106.61%` | `-52.30%` | 34 | 收益 `-604.42pp`，MDD 多 `33.91pp` | `FAIL / noise-releasing` |
| `M2_SHORT_RSI_RELAXED_TP` | 空头 RSI 止盈改为 `RSI6<25 × 1d` | `+496.98%` | `-18.40%` | 20 | 收益 `-214.06pp`，MDD 基本不变 | `FAIL` |
| `M3_OVERBOUGHT_EXHAUSTION_SHORT` | 超买衰竭后 flat-only 开空 | `+465.29%` | `-24.01%` | 27 | 收益 `-245.75pp`，MDD 多 `5.61pp` | `FAIL / noise-releasing` |
| `M4_POST_EXIT_COOLDOWN_OVERRIDE` | 全局 cooldown 改方向性 cooldown | `+495.48%` | `-24.01%` | 25 | 收益 `-215.55pp`，MDD 多 `5.61pp` | `FAIL` |
| `COMBO_ALL_FOUR` | 四项同时启用 | `+159.98%` | `-45.33%` | 44 | 收益 `-551.06pp`，MDD 多 `26.93pp` | `FAIL / noise-releasing` |

## 压力与触发

| Arm | `8 bps` | `1d lag` | Block 正收益 | 关键触发 |
| --- | ---: | ---: | ---: | --- |
| `CTRL_EXACT_V7` | `+698.75% / -18.53%` | `+267.61% / -26.45%` | `8/8` | 原生信号20次、PEHC接受5次 |
| `M1_PENDING_RECLAIM_MATURITY` | `+101.10% / -52.82%` | `+65.69% / -45.97%` | `7/8` | raw cross arm 41次、confirm 23次，交易增至34笔 |
| `M2_SHORT_RSI_RELAXED_TP` | `+487.81% / -18.53%` | `+289.42% / -20.04%` | `8/8` | short RSI退出由3次增至5次，但收益下降 |
| `M3_OVERBOUGHT_EXHAUSTION_SHORT` | `+453.47% / -24.19%` | `+202.06% / -22.53%` | `8/8` | overbought short 3次，交易增至27笔 |
| `M4_POST_EXIT_COOLDOWN_OVERRIDE` | `+484.00% / -24.19%` | `+216.15% / -22.53%` | `8/8` | cooldown阻挡从6次降至1次，交易增至25笔 |
| `COMBO_ALL_FOUR` | `+151.00% / -46.12%` | `+93.63% / -47.16%` | `6/8` | episode confirm 18次、overbought short 3次、交易增至44笔 |

## 机制解释

`M1_PENDING_RECLAIM_MATURITY` 直接验证了“不要只认 fresh reclaim，等 slope 成熟后补开”的想法。它确实补到很多用户肉眼看到的后成熟机会，但把交易数从20笔拉到34笔，PF 从 `17.51` 降到 `1.35`，MDD 扩到 `-52.30%`。这是典型放噪声，不是补漏。

`M2_SHORT_RSI_RELAXED_TP` 解决了“9月25日 RSI6 单日严重超卖但不止盈”的问题，但提前止盈会切断后续空头收益。它不扩大回撤，但收益从 `+711.04%` 降到 `+496.98%`，说明 V7 的 `RSI6<20 × 2d` 虽保守，却保留了关键空头利润。

`M3_OVERBOUGHT_EXHAUSTION_SHORT` 验证了“RSI6 连续超买、涨不动、跌破 MA7 后开空”。它触发3次，但收益下降、MDD 扩大到 `-24.01%`。仅靠超买衰竭会太早或太频繁地把趋势多头切成空头噪声。

`M4_POST_EXIT_COOLDOWN_OVERRIDE` 验证了“平仓后允许反方向机会接上”。方向性 cooldown 确实减少了阻挡，并新增5笔交易，但收益下降、MDD 扩大。说明全局 cooldown 在 V7 里不是纯粹拖后腿，它也在挡坏的 post-exit 追单。

组合臂最差：四个口子同时打开后，交易数到44笔，MDD 到 `-45.33%`，8个 block 只有6个正收益。组合结果确认这些机制之间会互相放大 churn。

## 后续方案

这四项不应写入 V7。若继续研究，不能再从同一432日里继续调这些阈值；更合理的是把失败结果当作边界条件：

- 保留 V7 当前 fresh reclaim 与 cooldown 作为主身份。
- 若要继续补漏，只能另立更强约束的候选，例如“pending reclaim 必须同时满足趋势段质量、机会成本和最大 MAE 预算”，而不是只等 slope 成熟。
- `RSI6>70` 可继续作为解释面板，不应直接作为交易触发。
- exit 后交接需要比“方向性 cooldown”更严格的收益/风险过滤，否则会释放 churn。

## 证据

- [首次运行前冻结合同](../specs/hype-1d-ma7-abt-v7-four-mechanism-ablation-contract-2026-08-11.md)
- [完整机器证据](../artifacts/hype_1d_ma7_abt_v7_four_mechanism_ablation_2026-08-11.json)
- [机器证据 SHA256](../artifacts/hype_1d_ma7_abt_v7_four_mechanism_ablation_2026-08-11.json.sha256)
- [审计脚本](../scripts/audit_hype_1d_ma7_abt_v7_four_mechanism_ablation.py)
