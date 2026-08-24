# BIN-1D-BE-RCR Decision Log

## 2026-08-12 — P0 家族与合同冻结

- MA7 shared V1 在长历史、全消融、硬回撤搜索、尾部状态、entry information、小时确认与 entry shape 上均未达到目标。
- 去重后排除 Turtle、EWMAC、经典 TSMOM、MTF、MA7 meta-label 与 adaptive-regime 的重复实现。
- 新建确定性 BTC/ETH relative-cycle rotation 家族；它不是 MA7 V2，也不沿用 HYPE 参数。
- 冻结 development / researcher-exposed audit / prospective 三段边界。
- 先执行有限穷举；若 development 无硬门槛候选，不揭示 audit，不以加杠杆或波动目标救援。

## 2026-08-12 — P0 HARD-GATE-FAILED

- `7,560/7,560` 配置完成；最高收益 `21.2605x`，但 ordered MDD `-69.6600%`。
- 全网格最低 daily MDD `-24.5154%`，对应收益 `8.6109x`；ordered MDD `-30.7607%`。
- daily 初筛通过数为 0，audit/prospective 未揭示，不登记版本。
- 固定两条前沿用于下一步尾部退出/再武装 exact-control 研究；风险缩放继续禁止。

## 2026-08-12 — P1 HARD-GATE-FAILED

- growth/risk controls parity PASS；`184/184` 个保护 overlay 完成。
- base hard-target 通过数 `0`；最高收益 `14.1870x/-71.1539%`，最低 MDD `1.5092x/-26.0732%`。
- 停止扩展 stop/EMA/cooldown；side attribution 指向 growth 的 ETH sleeves 与 risk 的 short sleeve 为下一信息归因对象。
- audit/prospective 继续封存，不登记版本。

## 2026-08-12 — P5 HARD-GATE-FAILED

- `5,778` 小时 landmarks、`332` danger labels、growth/risk danger episodes `39/20`。
- 小时 price hazard `0/6 PASS`；最好 vol-shock 仍未跨资产、四 strata 稳定。
- 关闭 price-only entry/daily/hourly hazard 路线；下一步只检验真实 funding/crowding omitted state。
- 若 funding attribution 仍失败，关闭本 family 并另立机制；audit/prospective 继续封存。

## 2026-08-12 — P6 HARD-GATE-FAILED；research line closed

- funding/crowding `0/6 PASS`；`POSITION_CROWD24` AUC 强，但最弱 strata edge 仅 `4.56pp < 8pp`。
- 遵守预注册门槛，不围绕边缘结果搜索 threshold，不做 economic conversion。
- `BIN-1D-BE-RCR` 当前研究线关闭：`explore / HARD-GATE-FAILED / not promoted / not live-ready`。
- audit/prospective 从未揭示；无版本、无 runner handoff。

## 2026-08-12 — P2 signal found；P3 HARD-GATE-FAILED

- `RELATIVE_EXTREME20` 为 `1/6` attribution PASS，跨 growth/risk 与 BTC/ETH 成立。
- 预注册 `10/10` 个绝对 z-score entry gates；base hard-target 通过数为 0。
- 最高 `21.3284x/-69.6600%`，最低 MDD `8.6109x/-30.7607%`；分类信号未转化为路径风险改善。
- 下一步只允许研究持仓期间且早于尾部的 state transition；audit/prospective 继续封存。

## 2026-08-12 — P4 HARD-GATE-FAILED

- `1,811` landmarks、`269` danger labels、growth/risk danger episodes `44/21`。
- 日频持仓 transition `0/6 PASS`；giveback/entry-loss AUC 低于 0.5，与 P1 过早退出损害收益一致。
- 停止日频 transition threshold 搜索；下一步仅允许闭合 `1h` hazard attribution。
- audit/prospective 继续封存，不登记版本。
