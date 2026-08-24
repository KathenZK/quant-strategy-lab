# HYPE V4 ATR-Band Trend State Machine 诊断合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究目标

修复登记V4两类结构问题：

1. `reclaim`要求price event与slope同日成立，导致cross先发生、slope后确认时漏单；
2. long trailing forced reversal曾在MA7上方开short，保护退出与趋势方向混为一体。

用户确认：

- 真正反向必须同时越过`MA7±0.75×ATR7`容错边界并满足方向slope；
- 保护退出后允许在cooldown结束时按完整target条件重新入场。

本轮不搜索阈值，不自动登记新版本。

## 冻结变体

### `V4_CONTROL`

登记`HYPE-1D-MA7-Asymmetric-Body-Trend-V4`。

### `BAND_STATE_MACHINE`

日`t`收盘只用已闭合UTC日K定义target：

- long target：`close[t] > SMA7[t] + 0.75×ATR7[t]`，且V4 long slope通过：
  `(SMA7[t]-SMA7[t-1])/ATR7[t] >= 0.02`；
- short target：`close[t] < SMA7[t] - 0.75×ATR7[t]`，且V4 short slope通过：
  `(SMA7[t-2]-SMA7[t])/ATR7[t] >= 0.02`；
- 两者都不要求前一日位于MA7另一侧，不使用reclaim有效期。

状态迁移：

1. flat且cooldown为0：有完整target时于`t+1` open入场；无target保持flat；
2. 当前long：容错带内或仅轻微跌破MA7均继续持有；完整short target出现时于`t+1` open平long并立即反手short；
3. 当前short：容错带内或仅轻微站上MA7均继续持有；完整long target出现时于`t+1` open平short并立即反手long；
4. target同侧不加仓、不调仓；
5. long/short的旧`ma7_hysteresis_exit`、`ma7_slope_exit`与`max_hold`不参与候选状态迁移，避免在相反target确认前提前flat；
6. hard/trailing stop只作保护性平仓，绝不自行决定反手方向；
7. 保护退出后执行long 2日、short 5日cooldown；cooldown结束时必须由当日完整target重新确认才可同方向重入，否则继续flat；
8. target直接反手绕过退出cooldown，平仓和开仓各计一次fill成本。

## 保护与执行

- long：保留V4 `trail_atr=1.5`，无hard stop；
- short：保留V4 `hard_stop_atr=1.5`与`trail_atr=4.0`；
- stop按真实`1h`路径处理：小时open跳空越过保护价按open成交，小时内触发按保护价/下一真实时点处理；
- stop后不使用未知的同小时未来路径；
- 反向target只在下一日open执行，新方向当日保护立即生效；
- 约`1x`固定数量、单仓、无加仓。

## 数据与成本

- Binance USD-M `HYPEUSDT` perpetual；
- accepted `1h`数据聚合UTC日K，真实event-time funding；
- 历史主路径截止`2026-07-30 04:00 UTC`，最新延伸另行审计；
- 手续费`0.001/fill`、基准不利滑点`4 bps/fill`。

## 输出与裁决

- `V4_CONTROL`与`BAND_STATE_MACHINE`的prefit、最后90日flat-start、full；
- `8 bps`、额外延迟一天、零funding、`12h`日界；
- 最近`1d/7d/1m/3m/6m/1y`、90日滚动、24日界相位、最新延伸；
- 逐笔新增/删除/改写、target反手、保护退出、cooldown重入与短周期往返；
- 完整HTML：K线、MA7、上下边界、状态、cooldown、权益及每笔入场—出场连线。

若候选只修复图中个例却在主路径、滚动、压力、延迟或相位上明显降低精度，则保持diagnostic-only，不登记V5。
