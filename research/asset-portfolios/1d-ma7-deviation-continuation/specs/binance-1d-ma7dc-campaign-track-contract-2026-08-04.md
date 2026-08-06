# Binance 1D MA7 Campaign 持仓轨道验证合同

## 1. 要回答的问题

本合同验证截图所表达的视觉命题：一段趋势已经形成后，日线 SMA7 是否能较早与趋势对齐、在趋势内部持续持有、减少错误退出，并在趋势结束后保留至少一半最大浮盈。

它不再回答“每个 MA7 向上/向下的日锚能否重新预测未来 7–14 日”，也不把结果解释为可上线策略。

## 2. 数据与研究角色

- HYPEUSDT 为主样本；BTCUSDT、ETHUSDT 只作参照，不参与 HYPE 参数选择。
- 使用标准 Binance USD-M 数据湖、raw/normalized parity 和完整 UTC 日 K。
- 所有历史均已被研究者查看；ex-post swing 只用于定义视觉上的完整趋势和评分，不允许作为真实入场信号。
- MA7 入场对齐和退出信号只使用当时闭合日 K，成交统一使用信号后下一日 open。

## 3. 独立趋势基准

趋势段不使用 MA7 定义，采用 close-based ATR ZigZag：

- Primary reversal threshold：`2.0 × ATR7`；
- 固定敏感性：`1.5 × ATR7`、`3.0 × ATR7`；
- 只有发生反向阈值确认的摆动才算 completed swing，末端未确认摆动排除；
- 主观察范围：持续 `3–14d`；同时报告所有 `>=3d` 的延长趋势。

ZigZag 的未来确认只服务 ex-post 评分，不进入 MA7 tracker 的信号时间。

## 4. MA7 持仓轨道

### 对齐与进入

在一个 ex-post swing 内，首次同时满足以下条件时视为 MA7 与该趋势对齐：

```text
sign(MA7_t - MA7_t-1) == swing_side
sign(Close_t - MA7_t) == swing_side
```

信号后下一完整日 open 才能成交；若到 swing end 前都没有可执行 entry，则该 swing 为 missed。

### 退出模式

- `cross1`（primary）：首次日收盘落到 MA7 反趋势一侧，下一日 open 退出；
- `cross2`（robustness）：连续两日日收盘位于 MA7 反趋势一侧，下一日 open 退出；
- `cross1_reentry / cross2_reentry`（supplementary）：退出后若同一个 ex-post swing 尚未结束，MA7 再次与原方向对齐，则仍按下一日 open 重新进入；逐次收费并累计 funding。该对照补足用户实际会重新试单的行为，但不改变 primary 门禁；
- 最长只允许在 swing end 后继续等待 30 日；仍无退出则标记 censored，不用未来无限延长美化捕获。

### 成本

- fee：每次成交名义 `0.001`；
- adverse slippage：每次成交 `4 bps`；
- funding：使用 entry 与 exit 之间实际历史 funding rate，按方向扣减；
- 本阶段只按单个 swing 计算 normalized path return，不把重叠 swing 收益复利成账户净值。

## 5. 固定指标

- `admission_rate`：completed swing 中 MA7 能在结束前形成可执行对齐的比例；
- `timely_admission_rate`：在 swing 前半段且不晚于 3 日完成对齐的比例；
- `alignment_share`：swing 内 MA7 方向与价格位置同时对齐的日数比例；
- `full_swing_capture`：成本后 tracker 收益 / 整个 ex-post swing 对数幅度；
- `mfe_retention`：退出时毛收益 / 持仓期间最大顺向浮盈；
- `premature_exit_rate`：MA7 在 ex-post swing end 前发出退出并成交的比例；
- `round_trips / reentries`：为追回同一趋势需要经历的往返与重新进入次数；
- `net_positive_rate`、中位净收益、入场延迟、退出相对 swing end 的延迟；
- 多空、时长桶和三个 ATR reversal threshold 分开输出。

## 6. 截图命题门禁

HYPE、`2 ATR`、`3–14d`、`cross1` 为唯一 primary。至少 `12` 个 completed swings，并满足以下五项中的四项，才写 `visual tracking supported`：

1. admission rate `>=70%`；
2. timely admission rate `>=60%`；
3. median full-swing capture `>=50%`；
4. median MFE retention `>=50%`；
5. premature exit rate `<=30%` 且 median net return `>0`。

若样本不足或只满足两到三项，写 `partial`；零到一项写 `not supported`。这是截图命题的诊断标签，不是策略主状态。

## 7. 停止边界

- 不搜索 MA5–MA30；
- 不根据结果改变 ZigZag threshold、时长桶或 cross1/cross2 定义；
- 不把 ex-post swing start 当成可交易入场；
- 即使 visual tracking 通过，也必须另行验证真实趋势发现、风险、账户回测和 prospective OOS。
