# Scripts — BIN-1H-EMAX-LGBM

一次性研究脚本。复用 15m 家族冻结引擎 [`emax_common.py`](../../15m-ema-cross-lightgbm-event-selector/scripts/emax_common.py) 的纯函数（标注、funding、指标），路径与币池口径（每天 24 根）在本目录脚本内适配；该引擎文件被 15m 冻结清单按 SHA256 锁定，不得修改。产物落 [../artifacts/](../artifacts/README.md)。

- [`run_baseline.py`](run_baseline.py)：P1 基线（含 legacy 分区修复后的装载 glob）。
- [`audit_2026h1_reused_window.py`](audit_2026h1_reused_window.py)：2026H1 复用窗口一次性审计。
- [`research_local_trend_selector.py`](research_local_trend_selector.py)：15m 局部+趋势选择器移植（a2 特征集，诊断）。
