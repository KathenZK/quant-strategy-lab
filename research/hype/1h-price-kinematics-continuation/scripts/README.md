# Scripts

本目录保存 `HYPE-1H-PKC` 当前一次性统计研究脚本。脚本必须 fail closed 于数据质量 blocker 和 prospective OOS 输入，不产生订单或策略收益。

```bash
.venv/bin/python research/hype/1h-price-kinematics-continuation/scripts/research_hype_1h_pkc.py
```

脚本输出完整数据审计、固定时间锚点特征、未来路径标签、Train 固定五分位、block bootstrap、Ridge/Logit、速度—加速度相空间和四相位敏感性。
