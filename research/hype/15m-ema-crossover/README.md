# HYPE-EMA-X EMA Crossover

Family id: `HYPE-EMA-X`

Binance HYPEUSDT `15m` EMA96/384 金叉死叉研究线。根目录只保留家族入口三件套；其余材料按类型分子目录。

## 根目录（只读这三份起步）

| 文件 | 作用 |
| --- | --- |
| `README.md` | 本页：目录地图与阅读顺序 |
| `hype-ema-x-core-ledger.md` | 主台账：版本演化、指标、实现状态 |
| `decision-log.md` | 决策日志：提升记录与研究批次 |

## 目录结构

```
15m-ema-crossover/
├── README.md
├── hype-ema-x-core-ledger.md
├── decision-log.md
├── canonical-specs/     # 干净官方参数规格
├── ablations/           # 全参数消融与合体搜索
├── diagnostics/         # 执行审计、可行性复审、参数剔除
├── research-notes/      # 历史规则镜像与搜索笔记
├── artifacts/           # 保留 JSON/CSV 证据
├── scripts/             # 一次性复现脚本
└── legacy-canvas/       # 迁移 Canvas 历史
```

## 当前 promoted 版本

| 版本 | 定位 |
| --- | --- |
| `HYPE-EMA-X-V17` | V15/V16 合体平衡版（信号层主候选） |
| `HYPE-EMA-X-V17.1` | V17 + `hq_scale=1.1` 仓位增强 |
| `HYPE-EMA-X-V18` | **V17.1 干净参数规格**；逻辑相同，剔除 noop/关闭模块后的最小参数集 |

V15–V17.1 仍是研究候选，**不是** live-approved。V18 供 live spec / handoff 使用。

## 推荐阅读顺序

1. `hype-ema-x-core-ledger.md`
2. `decision-log.md`
3. `canonical-specs/hype-ema-x-v18-baseline-spec.md`（干净参数）
4. 按需：`diagnostics/`、`ablations/`、`research-notes/`

## Naming

使用 `HYPE-EMA-X-V6`、`HYPE-EMA-X-V17`、`HYPE-EMA-X-V17.1`、`HYPE-EMA-X-V18` 等完整家族名。不要与 `HYPE-EMA-TB` 混用。

## Scripts & Artifacts

- 脚本：`scripts/`
- 证据：`artifacts/`
- 顶层 `reports/` 已退役；引用请指向 `artifacts/`
