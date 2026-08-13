# HYPE V4 Finite Reclaim Pending 局部修复合同

> 冻结时间：2026-08-07（首次运行前）。状态：`explore / diagnostic-only / not promoted / not live-ready`。

## 研究目标

只修复登记V4中“reclaim发生当日slope尚未确认，次日确认时事件已失效”的局部漏单，不再重写完整状态机。

本轮明确保留：

- V4自然long/short的reclaim、entry buffer、方向slope阈值；
- V4全部迟滞、slope、max-hold与hard/trailing退出；
- V4 `MA_ONLY` trailing反手过滤；
- long 2日、short 5日cooldown；
- 保护退出后不得仅因价格仍在旧趋势一侧自动重入；
- 多空独立评估，最后才检查组合路径。

## 有限等待定义

日`t`出现某侧fresh reclaim price event：

1. 当日close满足该侧V4 `entry_buffer_atr`；
2. 前一日close满足该侧V4 `pullback_touch_atr`；
3. 若V4原方向slope当日已通过，行为与V4完全相同；
4. 若slope未通过，只把该事件pending固定`N=1`或`N=2`个后续完整UTC日；
5. pending期内仍要求当前close满足原V4 entry buffer、原confirm-days与原slope；确认后次日open入场；
6. close回到MA7反侧立即失效；超过`N`日立即失效；
7. 新fresh reclaim可开始一个新pending，但旧事件不能无限续期；
8. cooldown期间不建立pending；持仓期间不更新pending；旧pending不得穿越保护退出后的cooldown。

`N=1`表示fresh event后的下一个完整日仍可确认；`N=2`表示最多等待两个完整日。它不是persistent regime，也不是ATR-band状态机。

## 逐步变体

### Step 0：控制

- `V4_CONTROL`：登记V4逐笔锚点。

### Step 1：只修short

- `SHORT_PENDING_1D`
- `SHORT_PENDING_2D`

long完全保持V4。重点核对2025-06-17 fresh short reclaim能否在slope确认后入场，以及是否引入新的低质量short。

### Step 2：只修long

- `LONG_PENDING_1D`
- `LONG_PENDING_2D`

short完全保持V4。逐笔检查新增long是否解决真实漏单，还是只增加止损。

### Step 3：最后组合

- `BOTH_PENDING_1D`
- `BOTH_PENDING_2D`
- `LONG1_SHORT2`
- `LONG2_SHORT1`

组合只用于暴露仓位占用、cooldown与路径相互作用，不能把单侧历史赢家直接视为独立验证。

## 数据、执行与输出

- Binance USD-M `HYPEUSDT` perpetual；
- accepted真实`1h`聚合UTC日K，历史主路径截止`2026-07-30 04:00 UTC`；
- 约`1x`固定数量、手续费`0.001/fill`、不利滑点`4 bps/fill`、真实funding；
- 输出prefit、最后90日flat-start、full、`8 bps`、额外延迟一天、零funding、`12h`、最近切片、90日滚动、24相位与最新延伸；
- 每一步输出pending arm/confirm/expire/invalidate事件、相对V4逐笔变化、保护退出与cooldown路径。

## 裁决

候选先满足行为目标，再看是否保留V4精度：

1. 目标漏单必须由有限pending补上，不能靠持续regime或强制反手；
2. MDD不得比V4恶化超过5个百分点；
3. 额外延迟、`12h`与相位中位不得转负；
4. 有效相位正收益数量不得低于`18/23`；
5. 若多个候选通过，优先等待更短、逐笔变化更少者；净收益只作次级排序；
6. 全部结果均为post-reveal诊断，不自动登记V5或推进promotion。
