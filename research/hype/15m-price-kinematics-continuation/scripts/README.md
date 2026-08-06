# Scripts

本目录保存 `HYPE-15M-PKC` 一次性统计研究脚本。脚本必须在数据质量或 prospective OOS 输入出现时 fail closed，不生成订单或策略收益。

```bash
.venv/bin/python research/hype/15m-price-kinematics-continuation/scripts/research_hype_15m_pkc.py
```

脚本复用已经过哈希对拍的纯价格运动学因果内核，输出闭合时序审计、未来路径标签、固定分箱、block bootstrap、Ridge/Logit、相空间和四分钟相位敏感性。
