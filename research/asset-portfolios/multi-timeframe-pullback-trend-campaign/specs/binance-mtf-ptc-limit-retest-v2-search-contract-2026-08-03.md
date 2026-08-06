# BIN-MTF-PTC Limit Retest V2 搜索合同

Regime Campaign V1 证明 BTC 高周期共识有增量，但当前 restart 后 next-open market entry 的成本与追价仍可能侵蚀优势；ETH/HYPE 的 base edge 更薄。V2 只改变 restart 后的成交方式，不改 continuation model、方向先验、layer、stop、退出或风险参数。

## 冻结父版本

- BTC：`weekly_monthly_consensus + 3 layers + no half-reduce`；
- ETH：`none + probe-only`；
- HYPE：`none + probe-only`；
- 使用 V1 相同 development expanding folds；原 validation 只能作 revealed diagnostic；locked evaluation 不运行。

## 成交候选

1. `market`：原 next 15m open adverse fill；
2. `limit25_1h`：restart 后在 restart close 至结构 stop 距离的 25% 回踩处挂限价，最多 1h；
3. `limit50_1h`：同上，回踩 50%，最多 1h；
4. `limit25_4h`：25% 回踩，最多 4h；
5. `limit50_4h`：50% 回踩，最多 4h。

限价从原 market entry timestamp 开始生效。Long 若 open 已低于限价按 open 成交，否则 low 触价按 limit 成交；Short 镜像。限价成交不得差于 limit，仍按 taker fee 10bps；未成交即到期取消，不追单。若成交 bar 同时触 stop，stop 优先；盘中触价成交的同 bar 不使用可能发生在成交前的 favorable extreme 授予 MFE，只允许 close 确认进展。

失败的 restart/limit plan 必须保持 pending 至真实到期，禁止预知未成交后提前释放下一信号。反方向强 continuation candidate 可因果取消 pending plan。

## 选择

每资产仅 5 个候选。主排名仍为 development folds 合并 net log growth，并要求风险违规为 0、MDD <=20%、BTC/ETH 至少 2/3 fold 为正、交易数 >=30、PF >1。唯一胜出方式随后补跑 8bps exit stress 和 revealed diagnostic validation；若 stress/diagnostic 为负、交易过少或 tail concentration 未改善，不取得 locked evaluation 资格。
