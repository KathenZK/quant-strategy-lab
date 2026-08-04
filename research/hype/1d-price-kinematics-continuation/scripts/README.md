# Scripts

- [research_hype_1d_pkc.py](research_hype_1d_pkc.py)：从连续闭合 `15m` K 聚合完整 UTC 日 K，复现 `3/7/14d` 纯价格运动学、未来路径标签、透明模型、14 日 block bootstrap 和冻结门禁。

运行：

```bash
.venv/bin/python research/hype/1d-price-kinematics-continuation/scripts/research_hype_1d_pkc.py
```

脚本在输入出现 `2026-08-03 00:00 UTC` 及以后的源 K 时拒绝执行，防止触碰 prospective OOS。
