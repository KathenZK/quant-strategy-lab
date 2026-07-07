# 1H Adaptive-Regime Search Kernel

跨资产 `1h` 多指标自适应 regime 广搜/回测引擎。它最初以 `research/hype/1h-adaptive-regime/scripts/research_hype_1h_adaptive_regime_search.py` 的形式诞生，随后被 TRX、SOL、ETH、BTC、BNB 等资产的搜索/微调/消融脚本以 SHA256 pin 动态 import 复用，事实上成为共享引擎。本目录把它登记为正式共享内核。

## 冻结版本

| Version | 文件 | SHA256 | 说明 |
| --- | --- | --- | --- |
| `v1` | `v1/engine.py` | `0420ea44854201e17d4bf5b9142fb8335d143e78772656473a1dcf4594a5f04c` | 与 `research/hype/1h-adaptive-regime/scripts/research_hype_1h_adaptive_regime_search.py` 当前内容逐字节一致；后者是 grandfathered 原始位置，保留作为 HYPE 家族历史证据。 |
| `v2` | `v2/engine.py` | `70c22ea97a7c1c678f677e4c87ac5468d2bb233144e3e2545f02b26c7e959c38` | 仅更新状态文案：移除已废弃的 `paper-live` 状态表述，统一使用 `dry-run` 与 `live`。回测逻辑与 `v1` 不变。 |

`v1` 已被消费方以 SHA256 pin 引用，**内容永久冻结**。`v2` 是新的默认引用版本；任何修改（含 bug 修复或文案修正）必须继续新建 `v(N+1)/` 并在本表登记新 SHA。

## 消费方清单

以下脚本通过 `ENGINE_PATH` + `ENGINE_SHA256` 引用本引擎（`v1` 内容）。历史脚本的 `ENGINE_PATH` 指向 HYPE 目录原始位置，属 grandfathered，不强制改路径：

- `research/trx/1h-adaptive-regime/scripts/`：search / refine / clean tune / ablation 系列。
- `research/sol/1h-adaptive-regime/scripts/`：search / high-win target search / clean tune / ablation 系列。
- `research/eth/1h-adaptive-regime/scripts/`：search / refine / clean tune / ablation 系列。
- `research/btc/1h-adaptive-regime/scripts/`：clean tune / ablation / window backtest 系列。
- `research/bnb/1h-adaptive-regime/scripts/`：search / cap3 high-win search / ablation 系列。
- `research/hype/1h-adaptive-regime/scripts/`：HYPE 本家族 V2/V3/V4 tune 与 ablation 系列。

新资产接入 `1h-adaptive-regime` 广搜时，`ENGINE_PATH` 应指向 `research/_shared-kernels/1h-adaptive-regime-search/v2/engine.py`，并沿用本文件登记的 SHA pin。只有复现旧报告时才继续使用 `v1`。

## 后续演进方向

- 每资产的 clean tune / full ablation / window backtest 脚本目前仍是近似拷贝（700-1000 行/份）。下一步应把资产（数据路径、funding 路径、目标门槛）参数化为 CLI 参数，收敛为本目录下的共享驱动脚本 + 各家族薄配置；收敛动作必须逐资产验证与旧脚本输出逐笔一致后再替换。
