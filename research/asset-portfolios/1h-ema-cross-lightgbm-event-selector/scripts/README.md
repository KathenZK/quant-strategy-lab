# Scripts — BIN-1H-EMAX-LGBM

一次性研究脚本。复用 15m 家族冻结引擎 [`emax_common.py`](../../15m-ema-cross-lightgbm-event-selector/scripts/emax_common.py) 的纯函数（标注、funding、指标），路径与币池口径（每天 24 根）在本目录脚本内适配；该引擎文件被 15m 冻结清单按 SHA256 锁定，不得修改。产物落 [../artifacts/](../artifacts/README.md)。
