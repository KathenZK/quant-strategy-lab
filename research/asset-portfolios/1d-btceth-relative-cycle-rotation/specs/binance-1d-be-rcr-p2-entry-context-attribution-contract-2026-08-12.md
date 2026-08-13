# BIN-1D-BE-RCR P2 Entry-Context 归因合同（2026-08-12）

## 1. 目的与证据边界

P1 exact ablation 显示 growth 的 ETH sleeves 贡献最深尾部、risk 的 short sleeve 无保护价值。P2 只在 P0 两条冻结 controls 的原始 trades 上检验：入场前已知的短周期反转、波动冲击与跨资产分歧，能否稳定识别尾部交易。

P2 是 attribution，不准删交易、搜索 threshold、改参数或产生版本；只读 development，audit/prospective 保持封存。

## 2. 冻结样本与标签

- 样本：growth control `74` 笔与 risk control `43` 笔原始交易；exact replay 必须对齐 P0。
- 标签：分别在每个 anchor 内，`trade_log_growth` 处于最差 `20%`（含分位点）为 `tail=1`；不使用未来日内路径作特征。
- 特征时间：entry open 的前一完整 UTC 日收盘及更早。

## 3. 六个预注册 risk scores

数值越大均表示预期尾部风险越高：

1. `FAST_OPPOSE5`：`-side × selected_asset z-momentum(5,28)`；
2. `FAST_OPPOSE10`：`-side × selected_asset z-momentum(10,28)`；
3. `MARKET_OPPOSE5`：`-side × mean(BTC,ETH z-momentum(5,28))`；
4. `RELATIVE_EXTREME20`：`abs(BTC z-momentum(20,28)-ETH z-momentum(20,28))`；
5. `VOL_SHOCK7_28`：selected asset `RV7/RV28`；
6. `CROSS_DISAGREE5`：BTC 与 ETH 5 日动量符号不一致为 1，否则 0。

## 4. 固定判定

每个 feature 计算 growth/risk anchor AUC、BTC/ETH pooled AUC，以及 `anchor×asset` 四 strata 的高风险 tercile tail rate 减低风险 tercile tail rate。feature 只有同时满足才 PASS：

- 两 anchor AUC 均 `>=0.62`；
- BTC 与 ETH AUC 均 `>=0.58`；
- 四 strata 样本均 `>=15`，且 tail-rate edge 均 `>=8pp`。

若 `0/6` PASS：停止 P2，不建立 entry gate，不扩大 feature/threshold；研究线仍 `HARD-GATE-FAILED / explore / not promoted / not live-ready`。若有 PASS，也只能另立 P3 冻结 exact gate 合同，不能依据本轮 tercile 直接交易。
