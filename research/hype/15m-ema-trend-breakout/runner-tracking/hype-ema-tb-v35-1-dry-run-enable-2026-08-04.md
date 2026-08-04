# HYPE-EMA-TB-V35.1 dry-run 启用记录（2026-08-04）

## 结论

按用户明确指令，`hype-ema-tb-v35-1-dry-run` 在 quant-runner `configs/dryrun.toml` 启用，manifest 同步为 `dry-run / approval_level=dry_run / enabled_allowed=true`。实例只做模拟撮合（`dry_run_notional_usdt=10`），无资金风险；`LiveCapability::DryRunOnly` 与 manifest 无 live 条目双重保证 live 不可达。

## 变更内容

- Lab manifest（main 分支提交）：`hype-ema-tb-v35-1-dry-run` 升级授权；同提交移除 `bin-15m-as6s-v5-joint-np-dry-run` 条目（V5 策略代码退役，引擎随 V6 需求迁移进 V6 模块）。
- Runner `configs/active-strategy.lock.json`：由 `scripts/governance/sync_manifest_lock.py` 从 lab main 重新生成。
- Runner `configs/dryrun.toml`：`hype-ema-tb-v35-1-dry-run` `enabled = true`；删除 `bin-15m-as6s-v5-joint-np-dry-run` 实例块。
- 校验：`validate_manifest_lock.py` 与 `check_live_enabled_gate.py` 全部通过。

## 运行参数（启用时）

| 项 | 值 |
| --- | --- |
| instance | `hype-ema-tb-v35-1-dry-run` |
| kind | `hype_ema_tb`（`HYPE-EMA-TB-V35.1`） |
| symbol / timeframe | `HYPE/USDT:USDT` / `15m` |
| warmup_bars | 2500 |
| dry_run_notional_usdt | 10.0 |
| bar 出场 / 价格源 | Bracket / Trade（dry-run 用 K 线 OHLC） |
| funding | replay 未计；dry-run 模拟引擎按 funding 事件记账 |

## 证据与缺口

- 逐笔 parity：2026-07-20 评审确认 Python 冻结与 Rust replay 交易路径零偏差（[评审文档](../diagnostics/hype-ema-tb-v35-1-dry-run-promotion-review-2026-07-20.md)）。规范 parity JSON 不在干净 Git checkout，**重新提交 Git 跟踪的对拍证据是后续状态变更的硬前提**。
- 2026-07-20 评审的研究门禁 0/2/3/4/5 保持未完成，live 继续封锁。
- 启用后第一批 dry-run 周期数据（注册、心跳、信号/开平仓事件）随例行对齐检查回写本目录。

## 跟进项

1. 重新生成并 Git 提交 V35.1 规范 parity 证据（runner replay + Python 冻结 + `check_hype_ema_tb_v35_1_runner_parity.py`）。
2. 部署到阿里云并重启 `quant-runner-dryrun` 后实例才实际开始运行；部署按 `deploy-artifact` 规则走 GitHub Actions 产物。
3. dry-run 运行满一周后与 V35 研究路径做开平仓对账，结果回写本目录。
