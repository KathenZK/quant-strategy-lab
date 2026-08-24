# Binance 1D MA7 P2-I Entry-Shape 归因合同

## 1. 研究问题

P2-H 证明单纯延迟等待方向确认存在稳定的风险/机会冲突：弱确认来不及拒绝 tail，强确认删除超过一半有效机会。P2-I 回到 original daily signal 之前最后一根完整 UTC 日线，检验 candle shape 与 directional path efficiency 是否能在不延迟执行的情况下识别 entry quality。

这是当前 MA7 substrate 的最后一轮新增 entry-information 归因。若无特征通过，停止继续扩充同一 MA7 entry substrate，下一步必须新建独立机制家族，而不是 P2-J 式继续添加指标。

## 2. 冻结样本与标签

- 输入沿用 [P2-G entry dataset](../artifacts/binance_1d_ma7_p2g_entry_information_2026-08-12_entries.csv)；
- `17,821` raw actual trades、pair-weighted 与 unique-entry 双口径、strata 展开规则不变；
- 主标签仍为 actual holding entry 后 `48h EARLY_TAIL<=-8%`；
- feature timestamp 固定为 entry 前最后完整 UTC 日线；entry 当日 open/hourly path 均不可用于 feature；
- ATR 使用截至该日的 `ATR7`，所有 rolling path 只读当日及以前 close。

## 3. 固定特征

令 `s=+1` 为 long、`-1` 为 short，`O/H/L/C` 为最后完整日：

1. `BODY_ATR = s×(C-O)/ATR7`：方向一致实体强度；
2. `BODY_SHARE = s×(C-O)/(H-L)`：方向一致实体占整根 range 的比例；
3. `CLV = s×(2×(C-L)/(H-L)-1)`：方向化 close location；
4. `ER7 = s×(C_t-C_{t-7}) / sum(abs(diff(C)), 7d)`：方向化七日效率；
5. `RANGE_ATR = (H-L)/ATR7`：无方向的异常日内扩张；
6. `ADVERSE_WICK_ATR`：long 为 `(min(O,C)-L)/ATR7`，short 为 `(H-max(O,C))/ATR7`。

range、ATR或七日路径分母为零时记 missing；不填零。不得加入 gap、当日 open、RSI、volume、funding、慢均线或结果后新增 feature。

## 4. 固定分析门

完全沿用 P2-G 的 rank-biserial/AUC 框架：

1. BTC、ETH overall effect 方向一致；
2. pair-weighted 与 unique-entry effect 同号；
3. 每资产至少两个 strata 的双口径保守 `abs(effect)>=0.15`；
4. 每资产 unique valid entries `>=30`；
5. 四个 asset×weighting AUC 的最弱 `abs(AUC-0.5)>=0.08`；
6. calendar leave-one-year-out 双资产双口径最弱方向一致率 `>=70%`。

同时披露 asset×side×stratum 与 feature quintile tail rates。若 `BODY_SHARE` 与 `CLV` 同时通过，只保留最弱 AUC edge 更大的一个；其它多个通过时按 missing 最少、最弱 AUC edge 最大选择唯一 feature。

## 5. 后续与停止规则

通过归因只允许另立一个 expanding/rolling quantile entry-gate PnL合同，且必须包含 exact P2-E control、shared BTC/ETH rule、`1x`、ordered `1h` MDD、development各 `>=20x/MDD<=20%`、stress/delay/calendar/rolling。

若 passing feature 为 `0`：

- 当前 V1→P2-I 的 MA7 substrate 扩展正式停止；
- 不组合多个 FAIL shape、不过滤有利年份、不改 EARLY_TAIL threshold；
- family 保持 V1 `registered / not promoted / not live-ready`；P2 campaign 记 `HARD-GATE-FAILED`，研究主状态仍为 `explore`，不进入 dry-run/live；
- 下一步若继续寻找目标，只能新建身份独立、机制实质不同且拥有新 prospective OOS 的策略家族。

P2-I 本身不得登记 V2、不得打开 audit/prospective。
