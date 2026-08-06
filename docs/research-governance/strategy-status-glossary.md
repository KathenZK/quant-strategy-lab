# 策略状态术语表与状态机

本文件是全仓库策略版本状态词的唯一定义来源。core ledger、README、diagnostics、live specs 引用状态词时必须使用本表中的标签；发明新状态词前先更新本文件。

## 权威边界与冲突处理

三类事实各有唯一权威，不得互相替代：

1. 本术语表定义主状态、合法组合与状态迁移。
2. 家族 core ledger 是家族/版本身份与当前状态的叙事真源；asset/顶层索引是路由投影。
3. `quant-runner` 是实例运行与授权的唯一真源；实际运行/停止事实只以其代码、配置、生成锁、服务状态和运行账本为准。Lab 不保存实例授权 manifest。

active SPEC 是研究侧实现合同，不是状态或实例授权源。术语表、core ledger、索引或 active SPEC 冲突时，阻止新的 promotion 或交接并修复研究权威源；不得据此自动停止、禁用或降级 runner 实例。任何运行状态变化必须由用户明确决定并在 `quant-runner` 执行。

“登记 / 记录 / 冻结 / 命名为 Vx”只固定版本身份并更新 core ledger，默认进入 `registered`，不包含任何 promotion。只有明确提出目标状态的 “promote / 晋升 / 进入 dry-run / 上线”才是状态迁移请求，并须满足对应门禁。

## 状态机总览

主状态只有下面这些：研究侧 2 个、promotion 侧 3 个，外加两个终态（`archived` 与 dry-run/live 后的 `NO-GO`）：

```text
explore（无版本号）
   │ 用户要求登记 Vx
   ▼
registered
   │ 准备推进 quant-runner / dry-run：完成全部验证门禁与 live-executable promotion review，
   │ 参数/状态机可被 runner 复现，并写出交接规格
   ▼
live spec
   │ quant-runner 实现完成 + 指标对拍/smoke test 通过 + 进入 dry-run 时立即建立 runner-tracking/
   ▼
dry-run（模拟盘，runner-tracking 持续记录）
   │ runner 观察证据达标 + 运维审计（重启恢复、missing-bar fail-closed、kill switch）完成
   ▼
live（真实资金运行；资金边界由子账户、runner 配置或上线决策记录管理）

dry-run 前如果证据不足、回测失败或 promotion review 不通过，停留在 `registered` / `explore`，并写 `not promoted / not live-ready`；
只有 dry-run 或 live 已运行并给出负面 runner 观察/实盘证据后，才允许写 NO-GO。
研究线不再推进且无意重开时，任一阶段可以封存为 archived（终态，重开视同新研究线）。
```

`audit` 不再是主状态。审计报告、脚本文件名和 promotion review 仍可使用 audit / 审计描述验证动作，但不得把版本状态写成 `audit`。登记 `registered` 时只固定身份并记录门禁缺口；准备推进 runner 或写 `live spec` 时，一次性完成验证门禁与 live-executable promotion review。失败则保持 `registered / not promoted / not live-ready`，通过才直接进入 `live spec`。

promotion 状态只有 `live spec`、`dry-run`、`live` 三个；`handoff` 是可叠加在其上的移交标签，不是独立状态。进入任何 promotion 状态前必须完成 live-executable 审计（见 [live-executable-strategy-research.mdc](../../.cursor/rules/live-executable-strategy-research.mdc) 与 [lab-runner-handoff.mdc](../../.cursor/rules/lab-runner-handoff.mdc)），并按 [strategy-validation-gates.md](strategy-validation-gates.md) 补齐对应门禁证据。本仓库不定义额外的模拟盘阶段；模拟盘/仿真运行统一称为 `dry-run`，真实下单归入 `live`。

## 主状态定义

| 主状态 | 含义 | 准入条件 |
| --- | --- | --- |
| `explore` | 搜索、诊断进行中，未登记版本 | 无；不可被引用为"策略" |
| `registered` | 用户要求登记的冻结版本（基线或观察值），仅固定研究身份 | core ledger 已更新版本表、参数、证据链接；不代表策略可行 |
| `live spec` | 已写出 runner 交接规格，等待/正在 quant-runner 实现；未启用 | 已完成 promotion review：核验 [strategy-validation-gates.md](strategy-validation-gates.md) 的全部门禁（超额收益、消融、OOS/CPCV、MC、压力测试、相位）与 live-executable 审计；参数/状态机可被 runner 复现；满足 `lab-runner-handoff.mdc` 交接规格必备字段；core ledger 链接该规格 |
| `dry-run` | 在 quant-runner 以 dry-run 模式运行（模拟盘，不下真实订单） | quant-runner 实现完成；指标对拍/smoke test 通过；进入 dry-run 的同一变更中建立 `runner-tracking/` |
| `live` | 真实资金运行 | dry-run 的 runner 观察证据达标；已完成线上开平仓对账且无未解决的重大偏差；资金费、盘口滑点、订单失败处理已审计；decision log 记录批准；资金边界由子账户资金、runner 配置或上线 decision log 管理，策略 spec 不强制写 live notional |
| `NO-GO` | dry-run 或 live 后的最终否决状态 | 必须有 `runner-tracking/`、dry-run 对账或真实订单证据；记录否决原因，重开需新证据并写 decision log |
| `archived` | 研究线已封存：不再推进、不再复现，仅作历史证据保留 | decision log 记录封存原因；封存不需要负面 runner 观察证据；重开视同新研究线 |

`handoff` / "交接版本"：把规格与实现移交给人或其他系统维护的动作标签，可叠加在 `live spec` 及之后的主状态上；要求双向链接的 SPEC 齐备、参数一致性验证记录在案。`handoff` 不是独立主状态。

`candidate` 不是主状态，也不是 promotion 状态。新文档可以把它作为研究角色词使用，例如参数候选、候选观察行、`registered candidate`；但不得写成独立状态，也不得用来暗示 live-ready、dry-run-ready 或可跳过 promotion review / `live spec` gate。若用户要求把候选登记为版本，主状态应写 `registered`，`candidate` 只作为角色修饰。

## 机器字段映射

| 叙事概念 | 机器字段 | 合法值 / 约束 |
| --- | --- | --- |
| 主状态 | core ledger、Lab live SPEC `main_status` | `explore`、`registered`、`live spec`、`dry-run`、`live`、`NO-GO`、`archived` |
| runner 模式与授权 | quant-runner config / generated lock | `dry_run`、`live`、enabled 等实际字段只在 runner 仓库维护 |
| 实际运行状态 | runner config / generated lock / service / runtime ledger | 判断实例正在运行、停止或使用哪个策略的唯一事实来源 |
| 对拍证据状态 | 标准 parity artifact `conclusion` 或报告备注 | `PASS`、`FAIL`、`PENDING`、`MISSING_EVIDENCE`；后两者阻止新 promotion，但不自动改变 runner |
| handoff overlay | Lab live SPEC `overlays` | 可包含 `handoff`；不是 `main_status` |
| 非晋升后缀 | 叙事 `not promoted` | 只可修饰 `explore` 或 `registered`，不写入 `main_status` |
| 未达 live 后缀 | 叙事 `not live-ready` | 可修饰 `explore`、`registered`、`live spec`、`dry-run`，不写入 `main_status` |
| 终态 | ledger `main_status` | `NO-GO` 或 `archived`；不得与历史 runner 状态并列为第二主状态 |

`dry-run / not promoted` 是自相矛盾组合：`dry-run` 已是 promotion 状态。`dry-run / NO-GO` 也非法，因为同一时刻出现两个主状态；否决后只写 `NO-GO`，历史 dry-run 事实放在 runner tracking 或历史备注。相同规则适用于 `live / NO-GO`。runner 配置中的 `dry_run` 使用下划线，叙事主状态始终写 `dry-run`。

## 修饰词（不是主状态）

以下词只能作为主状态的修饰或备注，单独出现不构成状态：

- `baseline` / `candidate` / `observation` / `clean-equivalent`：`registered` 或 `explore` 的来源/角色修饰——基线锚点、参数候选、微调观察值、与 parent 逐笔等价的参数精简版（clean-equivalent 需 trade signature 一致证据，且不提供新增收益证据）。
- `forward-test required`：gate 备注，表示状态推进依赖 `runner-tracking/` 下尚不存在的报告；口头描述不算证据。只能用于已进入 `dry-run` / `live` 的版本；未进入任何 runner 的版本没有可满足该备注的证据路径，应写 `not promoted / not live-ready`。
- `tiny-live-pilot`：`live` 主状态的限时修饰，表示真实下单只用于执行审计，
  资金必须在专用子账户内隔离，并在 quant-runner 配置或上线 decision log 中记录
  pilot 授权、资金边界和到期时间。
  它不是 production sizing，也不能由散文单独授权。
- `not promoted`：只可修饰 `explore` 或 `registered`，表示尚未进入 promotion 状态。
- `not live-ready`：表示尚不满足 `live` 准入；可修饰 `explore`、`registered`、`live spec` 或 `dry-run`，但不得修饰 `live` 或 `NO-GO`。它不是最终否决，后续可以因新机制、新数据或新审计重开。

历史文档中的 `diagnostic baseline`、`diagnostic observation`、`clean-equivalent observation`、`audit observation`、`audit candidate` 或 `audit` 状态等旧标签，按验证动作或 `registered baseline/observation`、`registered / not promoted / not live-ready` 理解，不需要批量改写。历史文档中若在 dry-run 前使用了 `NO-GO`，按新口径理解为 `not promoted / not live-ready`，除非同一文档明确引用了 dry-run/live runner 观察证据。

## 使用规则

- 状态词必须与完整 family name + 版本号一起出现，例如 `HYPE-15M-MII-V1.3：dry-run / forward-test required`。
- 一个版本同一时刻只有一个主状态；可以叠加修饰词，不可同时挂两个主状态。
- `not promoted` 只能修饰 `explore` 或 `registered`；`not live-ready` 可延续到 `live spec` 或 `dry-run`，但不得与 `live` 或 `NO-GO` 并存。
- 状态迁移（升级或降级）必须写入家族 `decision-log.md`，并同步更新 core ledger 与 asset/顶层索引中的状态标签。
- 回测再漂亮，未完成 promotion review 就标记 `live spec`，或跳过 `live spec` / `dry-run` 直接升级，均属于违规；发现即降级并记录。
- promotion review 失败后写 `registered / not promoted / not live-ready`，未登记研究线则写 `explore / not promoted / not live-ready`。
- dry-run 前不得给出 `NO-GO`；只能写 `not promoted / not live-ready`，并说明缺什么证据、什么新增证据可以重开。
