# HYPE-1D-MA7-ABT-V7 四机制组合参数搜索诊断合同

> 冻结时间：2026-08-11（首次组合搜索运行前）。状态：`post-reveal exploratory search / diagnostic-only / not promoted / not live-ready`。

## 研究问题

在四机制逐项 ablation 全部失败后，继续回答一个更窄的问题：这些机制是否存在某种固定组合/邻域参数，使得全窗收益和真实 `1h` MDD 同时不弱于 V7，并且完整压力包不暴露明显噪声。

本轮是已揭示历史上的组合搜索，只能生成未来 clean prospective 观察假设；不得直接修改 V7、登记 V8、生成 HTML、创建 live spec 或推进 runner。

## Control

- `CTRL_EXACT_V7`：V7 原参数，short cooldown `3d`，OAPP/PEHC 不变。
- 成本与数据：Binance USD-M `HYPEUSDT` perpetual，UTC `1d`，真实 `1h` replay；手续费 `0.001/fill`，基础滑点 `4 bps/fill`，压力滑点 `8 bps/fill`，计真实 Binance funding。

## 固定组合网格

### Pending Reclaim

- `P0`：关闭。
- `P_BOTH_D3_A075`：pending 最多 `3d`，允许 slope/buffer 同时后成熟，距离上限 `0.75 ATR7`。
- `P_BOTH_D3_A100`：同上，距离上限 `1.00 ATR7`。
- `P_BOTH_D3_A150`：同上，距离上限 `1.50 ATR7`。
- `P_SLOPE_D3_A100`：只允许 slope 后成熟，距离上限 `1.00 ATR7`。
- `P_BUFFER_D3_A100`：只允许 buffer 后成熟，距离上限 `1.00 ATR7`。

### Short RSI Take-Profit

- `R20x2`：V7 原始 `RSI6<20 × 2d`。
- `R20x1`：`RSI6<20 × 1d`。
- `R25x1`：`RSI6<25 × 1d`。
- `R25x2`：`RSI6<25 × 2d`。
- `R30x1`：`RSI6<30 × 1d`。

### Cooldown

- `CG`：V7 原始全局 cooldown。
- `CD`：方向性 cooldown，退出 long 只阻挡后续 long，退出 short 只阻挡后续 short。

### Overbought Exhaustion Short

- `O0`：关闭。
- `O70_3of5_D010`：最近5日内至少3日 `RSI6>=70`，当日 close 低于 `MA7 - 0.10 ATR7` 且低于前一日 close，flat 状态允许次日 open 开空。
- `O70_4of6_D025`：最近6日内至少4日 `RSI6>=70`，距离阈值 `0.25 ATR7`。
- `O75_3of5_D010`：最近5日内至少3日 `RSI6>=75`，距离阈值 `0.10 ATR7`。

固定全网格：`6 × 5 × 2 × 4 = 240` 个候选，包含 `CTRL_EXACT_V7`。

## 两阶段运行

1. Stage A：240个候选全窗基础运行，只记录全窗收益、真实 `1h` MDD、交易数、触发计数、相对 V7 差异。
2. Stage B：对 Stage A 中所有全窗双优候选，以及按收益排序的前20个非control候选，运行完整压力包：`8 bps`、funding-off、额外 `1d` signal lag、8个54日 cold-flat block、最近 `1d/7d/1m/3m/6m/1y`。

## 裁决纪律

- `SEARCH_HIT`：全窗收益高于 V7、真实 `1h` MDD 不差于 V7、`8 bps`为正、`1d lag`为正、8个block全部正收益。
- `POST_REVEAL_CANDIDATE_ONLY`：满足 `SEARCH_HIT` 也只能作为未来观察假设，不改 V7。
- 交易数明显上升、MDD扩大、block失败、lag失败、或组合依赖过多新增 episode/overbought 触发，裁决为 `FAIL / noise-releasing` 或 `FAIL / overfit-risk`。
