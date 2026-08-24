# HYPE-1D-MA7-ABT 多头追踪止损后反手空诊断合同

> 冻结时间：2026-08-06（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究问题

HYPE V1 的 8 笔历史多单中有 7 笔由 trailing/protective stop 退出，而非 MA7 迟滞退出。检验：

**多头 `1.5×ATR7` trailing stop 成交后立即转为空头，并完整沿用 V1 原有空头退出与保护规则，能否提高空头覆盖、组合收益与回撤表现。**

## 冻结变体

- `T0 baseline`：登记的 HYPE V1。
- `T1 trailing-stop-short-reversal`：
  1. 只在当前为多头且触发 `protective_stop` 时反手；V1 多头 `hard_stop_atr=0`，因此历史上的此类事件均来自 trailing stop；
  2. 先按原引擎价格平多，再在**下一根可成交的真实 `1h` open** 建立约 `1x` 空单，避免使用同一小时内未知的先后路径；平多与开空分别计成本；
  3. 若 trailing stop 在小时 open 跳空触发，可在该小时 open 反手；若小时内触发，则最早在下一小时 open 反手；
  4. 反手空跳过原 short entry reclaim / slope / buffer，但建立后完整沿用 V1 short config：
     - `entry + 1.5×ATR7` hard stop，开空即生效；
     - `close > MA7 + 0.25×ATR7` 或 `MA7[t] >= MA7[t-1]` 时下一日 open 退出；
     - `lowest_close + 4.0×ATR7` trailing stop；
     - `max_hold_days=20`、`cooldown_days=5`；
  5. 反手当日剩余小时路径、funding 与可能的同日 short hard stop必须纳入；不得等到下一日才开始计风险；
  6. 其他多空入场、退出、仓位、费用和 funding 不变。

T1 改变逐笔行为，是 materially new diagnostic mechanism；结果不得回写 V1 身份或前瞻观察台账。

## 数据、成本与窗口

- Binance USD-M `HYPEUSDT` perpetual；accepted `1h` raw/normalized 聚合 UTC `1d`，实际 event-time funding。
- 手续费 `0.001/fill`；基准不利滑点 `4 bps/fill`，压力 `8 bps/fill`。
- 主横比使用 V1 冻结历史：`2025-05-31` 至 terminal open `2026-07-30 00:00 UTC`；另报告补数后的最新延伸。
- 报告 prefit、researcher-exposed 后 90 日、full、额外延迟、近期 `1d/7d/1m/3m/6m/1y`；`12h` 相位只作非强制检查项。

## 判定

- `改善`：T1 在 base 与 `8 bps` 均提高全期收益，MDD不恶化超过 5 个百分点，新增反手空合计净 PnL 为正，且后 90 日不恶化；
- `混合`：部分指标改善但压力、回撤、后段或新增空单贡献至少一项失败；
- `失败`：新增反手空合计净 PnL 非正，或 base 组合收益下降。

BTC/ETH 共享参数多头的 `hard_stop_atr=0`、`trail_atr=0`、`max_hold_days=0`，没有 protective/trailing stop 触发，因此本合同不人为新增共享多头退出规则；该路线记为“不适用”，不是通过或失败。
