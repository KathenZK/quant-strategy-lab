# Scripts

- [research_hype_1h_pktsc.py](research_hype_1h_pktsc.py)：复现纯价格状态、逐日 causal walk-forward 延续预测、独立 Long/Short 门禁，以及同 campaign 的固定/动态仓位账本。

为避免单进程资源上限，四个冻结 horizon 独立生成、最后合并；分片不改变逐日训练截止或模型：

```bash
for horizon in 24 72 168 336; do
  .venv/bin/python research/hype/1h-price-kinematic-trend-survival-control/scripts/research_hype_1h_pktsc.py --horizon "$horizon"
done
.venv/bin/python research/hype/1h-price-kinematic-trend-survival-control/scripts/research_hype_1h_pktsc.py --finalize
```

输入出现 `2026-08-02 00:00 UTC` 及以后源 K 时，生成与合并步骤都会 fail closed。
