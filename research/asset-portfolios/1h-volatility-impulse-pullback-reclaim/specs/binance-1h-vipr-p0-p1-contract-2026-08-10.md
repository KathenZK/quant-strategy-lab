# BIN-1H-VIPR P0/P1 预冻结合同

## 1. 目标与状态

- Family：`Binance-1H-Volatility-Impulse-Pullback-Reclaim`
- Alias：`BIN-1H-VIPR`
- 状态：`explore / diagnostic-only / not promoted / not live-ready`
- 问题：原生 `1h` volatility-normalized breakout 是否能建立比 daily MA7 cross 更可靠的 root，并通过明确的 pullback/reclaim 降低追涨杀跌成本，在固定 bracket/timeout 下跨资产、跨时间保持正经济性。
- 本合同在查看本机制结果前冻结数据边界、八配置、状态机、成本、development 选择与 locked holdout 门；结果后不得降门、删资产或按方向救参数。

本研究不是 `BIN-1H-PIC` 的 4h impulse + pyramiding campaign，也不是 RHT/LMML 的特征或 threshold 续调；不使用 daily MA7、ML、asset id、CTLS、HYPE label、事后最优入场或动态仓位。

## 2. 数据与双重锁

- Universe：`BTCUSDT / ETHUSDT / BNBUSDT / SOLUSDT / TRXUSDT`。
- 输入：已审计 Binance FAPI direct `1h` 与官方 funding/mark，全部 `ts < 2025-05-31T00:00:00Z`。
- Development roots：signal timestamp `< 2024-05-25T00:00:00Z`；加载与结果计算截断在 `2024-06-01T00:00:00Z` 前，最长 pending + timeout 不得越界。
- Embargo：`[2024-05-25, 2024-06-01)` 不建 development 或 holdout root。
- Locked holdout roots：`[2024-06-01T00:00:00Z, 2025-05-20T00:00:00Z)`；只有 development 至少一个配置合格并按冻结排序锁定唯一配置后，才允许计算一次 holdout 结果。
- HYPE：代码只允许打开固定 15 个五资产文件；basename 含 `hype` 或 symbol 不在白名单时，在读取、散列前失败。输出必须声明 HYPE rows/files 均为零。
- 本合同没有 HYPE transfer；即使 holdout 通过，也须另立只读固定配置的 transfer 合同。

缺 K、重复 K、非闭合 K、非法 OHLC、非 UTC 网格、funding 时间无序或非有限指标均 fail closed，不插值。

## 3. 闭合时序与指标

小时行 `i` 的 `ts` 是开盘时间，root signal timestamp 为 `ts[i]+1h`。所有 root 判定只使用该边界前已闭合数据；entry 在下一小时 `open`。

```text
TR[i] = max(
  high[i]-low[i],
  abs(high[i]-close[i-1]),
  abs(low[i]-close[i-1])
)
ATR24_prior[i] = mean(TR[i-24:i])   # 不含 root bar
```

对 lookback `N`，breakout level 只用 root bar 前 `N` 根：

```text
long_level  = max(high[i-N:i])
short_level = min(low[i-N:i])
```

## 4. Root 与八个冻结配置

Long root 同时满足：

```text
close[i] > long_level
(close[i]-close[i-6]) / ATR24_prior[i] >= impulse_atr
(close[i]-low[i]) / (high[i]-low[i]) >= 0.70
TR[i] / ATR24_prior[i] <= 3.0
```

Short 完全镜像：跌破 `short_level`、六小时位移取反、close location `<=0.30`。零 range 不建 root。

唯一搜索网格：

```text
breakout_lookback in {24, 72}
impulse_atr       in {1.0, 1.5}
pullback_atr      in {0.5, 1.0}
```

共八个配置。其余参数固定，禁止结果后新增中间值、方向参数或资产参数。

## 5. Pending pullback/reclaim 状态机

- 每资产、每配置最多一个 pending root 或一个持仓。
- Flat 且无 pending 时，qualifying root 建立 pending；记录 `side`、breakout level、root ATR 与 root bar extreme。
- Pending 期间同方向新 root 忽略；反方向 qualifying root 取消旧 pending 并在该 bar close 建新 pending。
- 持仓期间所有 root 忽略；退出 bar close 后可建立新 root。
- Pending 只检查 root 后第 `1..48` 根闭合 bar，超过 48 小时取消。
- Invalidation：long close `< level-0.5*root_ATR`；short close `> level+0.5*root_ATR`，立即取消。
- Pullback arm 使用**当前 bar 之前**已知 extreme，避免同一 bar 内 high/low 顺序假设：

```text
long : prior_max_high - low[i]  >= pullback_atr * root_ATR
short: high[i] - prior_min_low  >= pullback_atr * root_ATR
```

- Arm 后必须再等至少一根完整 bar。Reclaim：

```text
long : close[i] >= level and close[i] > close[i-1]
short: close[i] <= level and close[i] < close[i-1]
```

- Reclaim 在 bar close 确认，entry schedule 为下一小时 `open`。不存在该 open 时 fail closed。
- 同一 close 先处理旧 pending 的 invalidation/arm/reclaim；若未产生 entry，再处理新 root。

## 6. 固定执行、bracket 与成本

- 固定 isolated leverage `0.25x`；无加仓、减仓、移动 stop 或 cooldown。
- Entry reference 为 scheduled hour open；entry fill 应用 adverse slippage。
- Bracket 以 root ATR 冻结：

```text
stop   = entry_reference - side * 1.0 * root_ATR
target = entry_reference + side * 2.0 * root_ATR
timeout = entry_ts + 120h
```

- Entry bar 起 bracket 生效。若 open 已越过 stop，stop reference 取更差的 open；target gap 仍保守按 target reference。若同一 bar 同时命中 stop/target，固定 `stop first`。
- Timeout 在 `entry_ts+120h` 的 open 退出；缺该 open 则该 root 不进入可评估集合。
- Funding 严格使用 `entry_ts < funding.ts < exit_ts` 的官方 rate/mark。
- Fee 固定 `0.001/fill`。主结果 adverse slippage `4bps/fill`；预生成 `8bps`、`12bps`、funding-off 与 entry lag `+1h`。
- Return 采用与共享 kernel 一致的 fill-notional fee 和 funding 公式；报告逐笔与按时间复合结果。

## 7. 立即入场对照

对 reclaim 策略每一笔实际成交的 root，另算同 root `signal timestamp` 下一小时 open 立即入场，使用相同 root ATR、bracket、timeout、费用、滑点和 funding。该对照只作配对机制审计，不参与参数选择。

## 8. Development 选择

八配置全部在 development 段运行。每个配置必须同时满足：

1. 总成交 `>=120`，每资产 `>=10`，long/short 各 `>=30`；
2. 主 `4bps` mean `>0`、PF `>=1.05`；
3. 至少 `4/5` 资产 mean `>0`；
4. 按 entry timestamp 的绝对 UTC `180d` block，正 mean block 比例 `>=60%`；
5. `asset × 180d` cluster bootstrap 10,000 次，`P(mean>0)>=0.80`。

合格配置按以下冻结顺序选唯一项：

1. 最大化五资产最小 mean；
2. 最大化正 180d block 比例；
3. 最大化总 mean；
4. 最大化 PF；
5. 最后按 `lookback` 大、`impulse_atr` 大、`pullback_atr` 大排序。

若无配置合格，development 直接 `HARD-GATE-FAILED`，holdout 保持未揭示；不得挑单资产、单方向或降低样本门救援。

## 9. Locked holdout 硬门

锁定配置一次性运行 holdout，以下全部满足才算 P1 通过：

1. 总成交 `>=40`，每资产 `>=5`，long/short 各 `>=10`；
2. 主 `4bps` mean `>0`、PF `>=1.15`；
3. 至少 `4/5` 资产 mean `>0`；
4. 绝对 UTC `90d` block 至少 `3/4` 为正；
5. `asset × 90d` cluster bootstrap 10,000 次，`P(mean>0)>=0.90`；
6. 相对同 root 立即入场：paired mean delta `>0` 且 cluster bootstrap `P(Δ>0)>=0.80`；
7. 至少 `3/5` 资产相对立即入场同时提高复合收益并降低事件序列 MDD；
8. `8bps` mean `>0`、PF `>=1.05`；
9. lag `+1h` 可执行率 `>=90%`、mean `>0`、PF `>=1.05`。

`12bps`、funding-off、per-side、per-asset、per-90d-block 与 recent `1d/7d/1m/3m/6m/1y` 强制报告但不单独新增门。Recent slices 锚定 holdout 数据终点，只作审计。

## 10. 证据与失败转向

必须保留：

- 数据质量与输入 SHA256；
- 八配置 development trades/metrics、合格列表与唯一选择；
- 若 development 合格：locked holdout trades、immediate pairs、equity/事件序列、bootstrap、压力与 recent slices；
- 摘要/完整 JSON、manifest/SHA256、中文 diagnostic、decision log 与索引更新；
- 研究脚本和状态机/成本/锁边界回归测试。

任一 development 或 holdout 硬门失败都不生成 frozen strategy、HYPE score 或 transfer。后续不得继续微调同一八配置；只能根据失败归因更换一个明确的结构假设，并在结果前冻结新合同。
