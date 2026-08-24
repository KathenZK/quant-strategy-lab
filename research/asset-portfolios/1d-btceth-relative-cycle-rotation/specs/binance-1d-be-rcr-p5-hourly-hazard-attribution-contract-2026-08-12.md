# BIN-1D-BE-RCR P5 Hourly-Hazard 归因合同（2026-08-12）

## 1. 问题与时序

P4 日频 transition 为 `0/6 PASS`。P5 不改日线 base state，只检验闭合 `1h` 信息能否更早识别日线状态改变前的 squeeze/反转。

- exact controls：P0 growth/risk；只读 development。
- landmarks：UTC `06:00/12:00/18:00` 开盘，当前状态已连续持有至少 6 小时；特征截止前一闭合 `1h`。
- label：从 landmark open 起未来 24 小时内或 base state 改变前的 adverse high/low `<=-8%` 为 danger。
- P5 只做 attribution，不执行退出、不搜索阈值；audit/prospective 继续封存。

## 2. 六个预注册 risk scores

1. `ASSET_OPPOSE6`：selected asset 6h 波动归一化反向动量；
2. `ASSET_OPPOSE24`：selected asset 24h 波动归一化反向动量；
3. `MARKET_OPPOSE6`：BTC/ETH 平均 6h 反向动量；
4. `ROLE_VIOLATION24`：selected 与 other 的 24h 相对角色反转；
5. `VOL_SHOCK6_72`：selected asset `RV6/RV72`；
6. `REL_EXTREME_RISE6`：BTC/ETH 24h 相对 z-score 绝对值六小时增量。

## 3. 固定门槛

每个 feature 必须同时满足：growth/risk AUC 均 `>=0.60`，BTC/ETH AUC 均 `>=0.58`；四个 `anchor×asset` strata 各 `>=200` landmarks、`>=8` dangers、高低 tercile danger-rate edge 均 `>=8pp`；两 anchor danger episodes 各 `>=8`。

若 `0/6 PASS`，关闭 hourly hazard 路线。若有 PASS，才可另立 P6 exact exit/rearm 合同；不得从 tercile 直接构造阈值。
