# V6 Mark 联合状态 Runner 对拍记录（2026-07-15）

策略状态：`dry-run / not live-ready`。Runner 状态：
`implementation parity PASS / failure injection PASS / dry-run authorized`。

`quant-runner` 已分别实现 V6 的不抢占与强突破抢占路线。实现只翻译冻结的
15 条资产专属腿、mark-price 保护退出和联合账户状态机，没有重新搜索或修改
任何参数，也没有读取锁定未来 OOS。两个配置实例已获持续 `dry-run` 授权。

## 实现边界

- 不抢占 kind：`asset_specific_six_selector_v6_mark_joint_np`。
- 强突破抢占 kind：`asset_specific_six_selector_v6_mark_joint_preemptive`。
- 实现目录：[`asset_specific_six_selector_v6_mark_joint_state/`](../../../../../quant-runner/crates/quant-runner/src/runner/strategies/asset_specific_six_selector_v6_mark_joint_state/mod.rs)。
- 禁用配置：[`configs/dryrun.toml`](../../../../../quant-runner/configs/dryrun.toml)。
- 两条路线都使用账户 scale `0.75`，最大有效 allocation `2.25`，低于用户的
  `3x` 上限。
- 信号只读取闭合 `15m/1h` K；入场依赖缺失时 fail closed；已有持仓仍允许
  mark 保护、退出和重启恢复。

## 严格逐笔对拍

| 路线 | 信号检查 | 退出腿 | 全候选 | 冻结路由 | Runner 路由 | 结果 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `nonpreemptive` | 45 | 15 | 1486 | 634 | 634 | `PASS` |
| `strong_breakout_preemptive` | 45 | 15 | 1298 | 568 | 568 | `PASS` |

对拍覆盖 `sleeve / symbol / side / entry_ts / entry_price / raw_strength /
strength / exit_ts / exit_reason`，并按冻结 Python 路由重建完整账户路径。
fixture 原始字节哈希为（2026-08-02 已重新冻结，见文末「Fixture 重新冻结」）：

- nonpreemptive：`25fc54595a3e941bc5c95d50601f2fe5284f581f1797b0d78afde6b9ea7f2f22`；
- preemptive：`f725da54c1a66ad65e4190469ff0f35d7ffcfe223c48e45fb5b2dd49757fc1fe`。

fixture 由冻结点以前的数据通过
[`export_binance_as6s_v6_runner_parity_fixtures.py`](../scripts/export_binance_as6s_v6_runner_parity_fixtures.py)
重建，保留在系统临时目录而不作为新的研究输入；长期证据只保存生成脚本、
哈希、计数和 strict replay 结果。机器可读摘要见
[`binance_as6s_v6_mark_joint_runner_parity_2026-07-15.json`](../artifacts/binance_as6s_v6_mark_joint_runner_parity_2026-07-15.json)。
供 manifest parity gate 使用的两条标准 schema 投影分别见
[`BIN-15M-AS6S-V6-NP_parity_2026-07-15.json`](../artifacts/BIN-15M-AS6S-V6-NP_parity_2026-07-15.json)
与 [`BIN-15M-AS6S-V6-SBP_parity_2026-07-15.json`](../artifacts/BIN-15M-AS6S-V6-SBP_parity_2026-07-15.json)。

## 执行安全与失败注入

- 保护触发固定使用 mark-price；交易 K 不得替代缺失 mark 数据。
- `15m` 腿 timeout 使用 15 分钟时钟；`1h` 腿的冻结持仓上限按四倍 15 分钟
  bar 数转换，保护检查仍逐根 15 分钟执行。
- 抢占通过显式 `Replace -> AfterFlat` 完成；pending replacement 可跨重启恢复，
  被风控挡住的入场会清除 pending 且不会虚假推进 cooldown。
- mark 或 funding 缺失时禁止新增风险；持仓期间缺 mark 不会误判平仓，也不会
  允许抢占。
- 多币种交易所保护、保护成交识别、重启补挂，以及 trailing 更新“先确认新
  stop、再撤旧 stop”均有定向测试。
- live execution 模拟覆盖订单接受后超时、用户流断连、部分保护成交、孤儿单、
  入场后保护前崩溃和紧急平仓失败等故障。

## 当前门禁结果

- `cargo fmt --all -- --check`：`PASS`。
- `cargo clippy -p quant-runner --all-targets -- -D warnings`：`PASS`。
- 常规测试：`204 unit + 2 alignment + 8 live-execution-sim + 2 offline-regression`，
  `0 failed`；5 个大型本地 fixture 测试默认 ignored。
- V6 两个大型 fixture 测试显式启用后：`2 passed / 0 failed`。
- `validate-config`：使用非路由占位钉钉 webhook 环境变量后 `PASS`；这是现有
  全局通知配置的环境依赖，不是 V6 参数。该次验证发生在启用授权之前。
- 两个禁用实例的 CLI strict replay 与安全 smoke：均 `PASS / ok=true`。

## 尚未解除的门禁

- 两条路线已于 2026-07-15 获得持续 `dry-run` 授权，但没有授权 Binance
  testnet 或小额真实订单。
- 历史逐笔一致证明 Runner 重现冻结模型，不证明未来收益。
- 最终未来 OOS 仍为
  `[2026-07-14T09:00:00Z, 2026-10-14T09:00:00Z)`；窗口完整结束前不得揭示、
  调参或 promotion。

## 持续 dry-run 启用记录

- 实例 `bin-15m-as6s-v6-mark-np-dry-run` 对应
  `BIN-15M-AS6S-V6-NP`，使用独立 state directory。
- 实例 `bin-15m-as6s-v6-mark-preemptive-dry-run` 对应
  `BIN-15M-AS6S-V6-SBP`，使用另一独立 state directory。
- 两条路线各自是单仓虚拟账户，不互相净额；公共平台 ledger 以实例名和策略 ID
  分账。基础名义金额各为 `10 USDT`，最大 allocation `2.25`。
- 本次仅改变运行状态与 forward 证据收集，不修改冻结参数、路由或未来 OOS。

## 线上 dry-run 部署

- Runner commit：`b54d07fdaecb32e62cd8af55a7712ec8fc2fa894`。
- 构建来源：GitHub Actions `Build Linux release` run
  `29416727782`；governance、tests、strict Clippy 与 Linux x86-64 release build
  全部通过。
- Artifact SHA-256：
  `11cccc4eb5ec231bf92f941c36a77346a4264cd645496bc9a4c9f9c7b568b17e`。
- 部署目标：阿里云 `quant-runner-dryrun.service`；live 服务未重启。
- 部署后 `strategy_health` 在 `2026-07-15T12:58:33Z` 显示两个 V6 实例均为
  `status=ok / position_open=0`，最后消费的决策 K 为
  `2026-07-15T12:30:00Z`；部署后 5 分钟 warning..alert 日志为空。
- 平台 `strategy_instances` 确认两个实例均 `enabled=1`，state directory 分别为
  `state/bin-15m-as6s-v6-mark-np-dry-run` 与
  `state/bin-15m-as6s-v6-mark-preemptive-dry-run`。

## Fixture 重新冻结（2026-08-02）

- 原始 V6 fixture 在 2026-07-15 导出后只保留在 `/tmp`，已被系统清理，Runner
  parity 测试所需的冻结字节一度不可复现。
- 使用既有冻结脚本重新导出（Lab venv）：
  `scripts/export_binance_as6s_v6_runner_parity_fixtures.py --output-dir <dir>`。
  重新导出字节与原始 fixture 不同（导出管道非字节级确定），但信号检查
  `45/45`、逐腿退出 `15/15`、全候选 `1486/1298`、冻结路由 `634/568` 及逐行
  路由对拍全部一致，parity 内容结论不变。
- 新 fixture 改为持久证据保存，不再依赖系统临时目录：
  - [`as6s_v6_mark_np_runner_parity_2026-08-02.json`](../artifacts/as6s_v6_mark_np_runner_parity_2026-08-02.json)，
    SHA-256 `21d48602e922191ef331408efe93b7f99f07d0db1ff1d1da3850bb80d7313249`；
  - [`as6s_v6_mark_preemptive_runner_parity_2026-08-02.json`](../artifacts/as6s_v6_mark_preemptive_runner_parity_2026-08-02.json)，
    SHA-256 `667ec9819536ef290b4f69f1e929baf5c637ca0d59f253da40166fbf99e1bd87`。
- Runner 代码常量 `NP_PARITY_FIXTURE_SHA256` / `PREEMPT_PARITY_FIXTURE_SHA256`
  已更新为上述新哈希；parity 测试新增 Lab checkout 默认路径回退（env 变量
  仍可覆盖），`cargo test -p quant-runner --lib -- --ignored` 本地 5 个
  parity 测试全部 PASS（含 V5 三个既有 fixture 测试）。
- 本记录不改变策略状态：仍为 `implementation parity PASS / dry-run authorized`，
  不涉及冻结参数、路由或未来 OOS。
