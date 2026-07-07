# Shared Research Kernels（共享研究内核）

本目录存放**被多个资产或多个策略家族复用的研究引擎**。它解决的问题是：跨资产复用的搜索/回测引擎既不是某个家族的一次性脚本，也不满足 `src/strategy_lab/` 的 active package code 准入（接口稳定、长期维护），需要一个介于两者之间的正式位置。

## 存放规则

- 目录格式：`_shared-kernels/<kernel-slug>/vN/`，例如 `_shared-kernels/1h-adaptive-regime-search/v1/`。
- 每个 `vN/` 目录是**冻结版本**：一旦有任何消费方脚本以 SHA256 pin 引用它，内容不得再修改。修 bug 或加功能必须开 `v(N+1)/` 新目录。
- 每个 kernel 必须有自己的 `README.md`，记录：内核身份与机制、各冻结版本的 SHA256、消费方清单（哪些资产/家族脚本在引用哪个版本）、版本间差异。
- 消费方脚本引用 kernel 时必须继续使用 SHA256 pin（防止引擎漂移污染历史结论），并在所属家族的 `scripts/README.md` 或研究报告中写明引用的 kernel 版本。
- 新的跨资产研究应优先引用本目录下的 kernel 路径；历史脚本中指向其他 family `scripts/` 的引用属于 grandfathered，不强制迁移，但迁移时必须验证 SHA 不变。
- 本目录只放引擎代码和说明；产物仍进各消费方家族的 `artifacts/`，报告仍进各家族的 Markdown 目录。

## 当前内核索引

| Kernel | 最新冻结版本 | 机制 | 消费方 |
| --- | --- | --- | --- |
| `1h-adaptive-regime-search/` | `v2` | Binance USD-M `1h` 多指标自适应 regime 广搜/回测引擎 | HYPE、BTC、ETH、SOL、BNB、TRX、asset-portfolios ensemble 的 `1h-adaptive-regime` 脚本 |
