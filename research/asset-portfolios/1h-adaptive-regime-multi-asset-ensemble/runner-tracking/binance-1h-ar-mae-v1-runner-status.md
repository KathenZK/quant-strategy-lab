# BIN-1H-AR-MAE-V1 Runner Tracking

- Date：2026-07-09（同日更新：replay 对拍完成）
- Runner repo：`quant-runner`
- Kind：`six_asset_ensemble`
- Strategy id：`BIN-1H-AR-MAE-V1`
- Mode：`dry_run` only
- Live-ready：`NO`

## Wiring

- Strategy module：`crates/quant-runner/src/runner/strategies/six_asset_ensemble/`
- Runtime：`crates/quant-runner/src/runner/trading/runner/six_asset_ensemble.rs`
- Dry-run instance：`configs/dryrun.toml` → `six-asset-ensemble-dry-run`
- State dir：`/home/admin/quant-runner/state/six-asset-ensemble-dry-run`
- TOML symbol placeholder：`BTC/USDT:USDT`（实际交易合约由 sleeve 决定）

## Runtime semantics

- 六资产并行拉 `1h` 闭合 K + funding 过滤特征。
- 账户级单仓：持仓期间忽略其他资产/腿信号。
- 同小时冲突按冻结 `TIE_PRIORITY`（HYPE > TRX > BTC > ETH > BNB > SOL）。
- 名义：`dry_run_notional_usdt × leg.fixed_leverage`。
- Live 启动校验直接拒绝。

## Status

- `smoke-test`：通过（本地 2026-07-09）。
- 持续 dry-run：已可接入 `quant-runner-dryrun.service`（需部署含本 kind 的 release 二进制）。
- `replay-dry-run`：尚未接线。
- 研究回测完整 funding PnL / 冻结交易路径对拍：尚未完成；当前 dry-run 是联合状态机近似，不是 lab diagnostic backtest 的逐笔复现。

## Decision gate

保持 lab 结论：`registered diagnostic / NO-GO / not promoted / not live-ready`。
dry-run 仅用于观察 runtime 信号与持仓生命周期，不改变 promotion 状态。
