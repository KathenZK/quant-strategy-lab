# HYPE-1D-MA7-ABT-V7.1 Dry-run Observer Start

## 结论

用户于 2026-08-13 授权启动 dry-run observer。live 仍禁用。

- Instance：`hype-1d-ma7-abt-v7-1-dry-run`
- Mode：`dry_run`
- Lock：`enabled_allowed=true`，`approval_level=dry_run`，`parity_status=PASS`
- TOML：`configs/dryrun.toml` `enabled=true`
- Service：`quant-runner-dryrun`（与组内其他 dry-run 策略同进程）
- State dir：`/home/admin/quant-runner/state/hype-1d-ma7-abt-v7-1-dry-run`

## 启动语义

新 state 从 flat 开始。不得根据当时行情重建研究回放中 2026-08-09 仍持有的多头。下一笔自然入场只接受未消费的合格日线 reclaim / PEHC / forced-reversal。

## 观察门

- 至少 90 天，或至少 5 笔闭合交易；
- 期间不改参数；
- 再抽取 runner DB/订单/日志做开平仓对账。

## 非目标

- 不 promotion；
- 不启用 live；
- 不视为 live-ready。
