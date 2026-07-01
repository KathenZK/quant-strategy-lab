# HYPE-15M-Riptide Scripts

本目录保存 `HYPE-15M-Riptide` 研究线的一次性复现、审计和对账脚本。

- `research_hype_15m_riptide_v13_cache_audit.py`：按外部 `SPEC-v13-RIPTIDE.md` 实现 V13，使用本地 `data/cache/hypeusdt_15m_fapi.csv` 做缓存口径审计，输出固定切点、150d rolling cut 和 `train150/test21/step21` walk-forward 结果。

当前脚本不应作为 live runner 使用；它只服务研究复现和差异定位。
