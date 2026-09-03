# Docs

本目录存放仓库级说明文档，不承载具体策略研究结论。具体策略材料仍在 [research/README.md](../research/README.md) 路由。

## 数据湖

- [data-lake-spec.md](data-lake-spec.md)：全仓库数据湖结构与质量约定的唯一规范。

## Research Governance

- [strategy-status-glossary.md](research-governance/strategy-status-glossary.md)：策略状态词与状态机的唯一定义。
- [strategy-validation-gates.md](research-governance/strategy-validation-gates.md)：从研究版本推进到 runner / dry-run / live 前的验证门禁。
- [core-ledger-template.md](research-governance/core-ledger-template.md)：新建或重构家族主账时使用的模板。
- [lab-live-spec-template.md](research-governance/lab-live-spec-template.md)：新建 Lab live spec / runner 交接规格时使用的模板。
- [artifacts-governance.md](research-governance/artifacts-governance.md)：`artifacts/` 目录的非破坏性治理（清单、预算与外置规则）。
- [schemas/lab-live-spec-frontmatter.schema.json](research-governance/schemas/lab-live-spec-frontmatter.schema.json)：Lab live spec YAML front matter 的校验 schema。
- [schemas/parity-report.schema.json](research-governance/schemas/parity-report.schema.json)：runner 对拍报告 JSON 的校验 schema。
