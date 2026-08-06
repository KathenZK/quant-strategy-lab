# HYPE-5M-PBTR V1–V6 历史研究归档

本文承接主账压缩前的长规格与实验叙事。版本身份、当前状态与关键指标以 core ledger 为准；完整参数和逐项结果以 diagnostics、ablations、specs、live-specs 与 artifacts 为准。

## V1–V4：旧 trailing 假设失败

- V1/R05732 在旧 stop-price fill 下极好，但 strict live-realistic PF `0.637`、总收益 `-87.29%`。旧基线不能回退上线。
- V2/V2.1-clean 通过同步微调和参数清理提高旧口径结果；clean 与 V2 基本等价。
- V2.1A 放开 RSI 后交易增多，但 strict PF `0.54`；dry-run ledger 与即时 TP 审计都未修复 crossed/stale stop 成交。
- V2.1B 去 ROC、V2.1C 提高 HTF 或加 ADX14 只是在旧机制内做稳定性观察，不改变 live infeasibility。
- V3 去掉 final HTF，V3.1 提高 min-hold，V3.2 清理入场，V3.3 最小化表达；样本内天文复利来自旧 fill/lockout 假设。
- V3.3 strict live-realistic PF `0.58`，即时 TP 网格最佳 PF `0.615`，不能交接。
- V3.3.1 加 stop-arm retry（第 7 根 arm、穿越重试、第 10 根市价兜底）修复崩溃与审计，但 1m 乐观 PF 仍 `0.580`；五类过滤、退出 overlay、轻量 ML 和 armed 后加仓均无效。
- V4 把旧口径单因子组合成 `EMA9/96 + stop0.25 + trail0.5 + min_hold18`，样本内漂亮但仍依赖不可执行锁仓/stop 成交，禁止进入 dry-run/live。
- 硬结论：一旦 strict fill 证明失败，不能继续在同一 stale-stop/min-hold 假设上优化。

## V5：executable-first 修复

- V5/V5.1/V5.2 放弃旧 trailing 幻觉，改以可执行 bracket、next-open 和 walk-forward 为首要约束。
- broad search、event-quality 与候选消融没有形成可交接生产版本。
- V5 的作用是建立新研究边界，而不是可回退版本。

## V6–V6.2.1：固定 bracket 主线

- V6：EMA21/55 强动量多头回踩恢复，`dir_ret192_bps>=788.123`，入场即 `TP3ATR/SL7ATR`，36 bars timeout。147 笔、PF `1.15`、DD `-11.28%`、OOS PF `1.45`。
- V6.1：`TP2.5ATR/SL7ATR/timeout36`、fixed 3x；总收益 `+408.95%`、PF `1.773`、DD `-25.63%`。收益改善主要含 sizing 风险，不是生产授权。
- V6.2：V6.1 long + short rank2，严格单仓；210 笔、总收益 `+833.71%`、PF `1.771`、DD `-22.38%`、OOS PF `1.439`。short OOS 仅 5 笔。
- V6.2.1：long `htf_spread>=0`，short 不变；219 笔、3x 总收益 `+1022.25%`、PF `1.804`、DD `-22.35%`。short OOS 仍仅 5 笔。
- V6.2.1 的 live 身份只限 tiny-live-pilot 和专用子账户；研究/runtime signal parity 已通过，但真实成交生命周期、保护单、重启与滑点仍阻塞 production sizing。
- 动态 ATR bracket、trailing 触发与 short 扩展均不能跳过低样本和执行审计。

## 关键执行教训

- closed-bar 信号、next-open 成交和 stop-first 顺序必须冻结；crossed stop 不能按陈旧 stop 价成交。
- `min_hold_bars`、stop arm 与 unlock 是高风险状态机，必须逐根审计保护期内与解锁首根。
- 修复订单可审计性不等于修复策略期望；V3.3.1 是典型反例。
- 缺失 parity 产物会阻塞新 promotion，但不能自动改变 runner 授权或服务状态。

## 证据入口

- [V1 strict live audit](../diagnostics/hype-5m-pbtr-v1-strict-live-audit-2026-06-27.md)
- [V2.1A live-realistic audit](../diagnostics/hype-5m-pbtr-v21a-live-realistic-audit-2026-06-24.md)
- [V3.3 retry-arm](../diagnostics/hype-5m-pbtr-v33-retry-arm-2026-06-26.md)
- [V4 live viability](../diagnostics/hype-5m-pbtr-v4-live-viability-audit-2026-06-24.md)
- [V5 executable search](../diagnostics/hype-5m-pbtr-v5-executable-search-2026-06-24.md)
- [V6 executable search](../diagnostics/hype-5m-pbtr-v6-live-executable-search-2026-06-25.md)
- [V6.2.1 live feasibility](../diagnostics/hype-5m-pbtr-v6-2-1-live-feasibility-audit-2026-06-30.md)
- [V6.2.1 full ablation](../ablations/hype-5m-pbtr-v6-2-1-full-parameter-ablation-2026-06-29.md)
- [latest runner tracking](../runner-tracking/hype-5m-pbtr-runner-2026-07-30.md)
