# Research Archive

`research/` 是本仓库的主要知识入口。它不只放 Markdown，也管理当前研究需要保留的一次性脚本和小型产物。

## 入口

- `STRATEGY_INDEX.md`：全局策略家族地图和命名规则。
- `hype/AI_CONTEXT.md`：阅读 HYPE 材料前必须先看的上下文。
- `hype/`：HYPE 策略家族档案。
- `hype/transfer/`：HYPE 内核迁移验证历史材料，暂保留 review，不是新的 HYPE 策略家族。
- `mu/README.md`：`MU-HYPE-XFER` 迁移研究入口。

已经不作为 active research 入口的历史策略研究位于 `../archive/research/`。

## 研究目录约定

新的策略研究默认由对应 topic 或 family 自管理：

- `README.md`、主账和 `decision-log.md`：长期入口和决策记录。
- `diagnostics/`、`ablations/`、`live-specs/`、`research-notes/`：按研究性质分类的 Markdown。
- `scripts/`：只服务当前研究的一次性复现、搜索、审计、报告生成脚本。
- `artifacts/`：需要随报告保留的 JSON、CSV、HTML、交易路径图等产物。

`src/strategy_lab/` 只放可复用的数据基础设施、质量检查、特征构建或窄口径研究数据集导出工具。不要把某个策略家族专用的一次性脚本提升到 `src/`。

## 报告存储规则

研究报告、策略主账、实验结论和持久 decision record 必须以 Markdown 保存在 `research/` 内。

新生成的研究报告默认使用中文，除非用户明确要求其他语言。

Cursor Canvas 和 Cursor 私有项目目录不是 canonical storage。Canvas 只能在用户明确要求时作为临时可视化界面；任何可持久化结论都必须同步写回对应 Markdown。

顶层 `reports/` 是 git 忽略的临时运行缓存或旧脚本兼容目录，不再作为 active research 的引用入口。
