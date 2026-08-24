# BIN-1D-BE-RCR P6 Funding/Crowding 归因合同（2026-08-12）

## 1. 最后 omitted-state 检查

Price-only 的 P4/P5 均为 `0/6 PASS`。P6 只在 P5 完全相同的 `5,778` 个小时 landmarks/labels 上加入真实 Binance funding 状态；不改 label、不增加 price feature、不执行退出。

- 冻结 landmark 文件 SHA256：`1a5e509a7690e7fc6d7953f2a281d508be6c2d33a12dc4980a73011121566891`。
- funding 使用 P0 冻结 BTC/ETH funding/mark parquet 与原 hashes；特征严格早于 landmark open。
- 只读 development，audit/prospective 封存。

## 2. 六个预注册 risk scores

先计算每资产过去 24h funding-rate sum `fund24`，再以过去 168h 的 `fund24` 均值/样本标准差形成 `z24`：

1. `POSITION_CROWD24 = side × selected fund24`；
2. `POSITION_CROWD7Z = side × selected z24`；
3. `MARKET_CROWD7Z = side × mean(BTC z24,ETH z24)`；
4. `RELATIVE_CROWD_ROLE7Z = side × (selected z24-other z24)`；
5. `FUNDING_ACCEL24 = side × (selected fund24-selected fund24[t-24]) / trailing168h std(delta24)`；
6. `CROSS_CROWD_ABS7Z = max(abs(BTC z24),abs(ETH z24))`。

数值越大预期 danger 风险越高。通过门槛完全沿用 P5：两个 anchor AUC `>=0.60`、两个资产 AUC `>=0.58`、四 strata 各 `>=200` landmarks/`>=8` dangers、最弱 tercile edge `>=8pp`，两 anchor danger episodes 各 `>=8`。

若 `0/6 PASS`，关闭 `BIN-1D-BE-RCR` family 的继续调研；不得扩 funding threshold 或组合 price features。若有 PASS，才可冻结 exact economic-conversion 合同。
