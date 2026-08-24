# BIN-1D-BE-DASE P0 冻结合同

## 1. 研究问题与边界

- Family：`Binance-1D-BTCETH-Dual-Alpha-Sleeve-Ensemble`
- Component A：CBCT P1 development growth frontier，固定 `entry20/exit10/EMA50/trail5ATR/confirm2/cooldown7/maxhold120` + `1ATR/35%/2d` profit protection。
- Component B：RCR P0 development growth frontier，固定 `regime40/relative40/vol28/deadzone0/switch0.25/confirm3`。
- 研究问题：两个终值均约 `21.26x`、机制不同的 frozen alpha sleeve，能否在不加杠杆、不重新选参的情况下把组合 MDD降至 `20%` 内。

组件来自已揭示 development，只能作为开发组件；二者 audit/prospective 均保持 sealed。DASE 的价值判断来自冻结组合规则在未来 audit/prospective 的表现，不把历史组合命中称为 clean OOS。

## 2. 固定资本 sleeve 会计

- 初始总权益 `1.0`，CBCT 权重 `w`，RCR 权重 `1-w`。
- 两个组件各自在自身初始资本内运行；其标准化权益分别为 `E_C(t)` 与 `E_R(t)`，组合 close equity 为 `wE_C(t)+(1-w)E_R(t)`。
- sleeve 之间不转移现金、不再平衡、不补保证金；某 sleeve 的盈利不能扩大另一 sleeve 下一笔的数量。
- 每个组件只对自己的 sleeve 目标约 `1x`；组合初始目标 gross 不超过 `1x`。持仓期间固定数量造成的自然 leverage drift必须报告，但不做 vol target 或动态缩放。
- 任一 sleeve 归零或发生 intrahour bankruptcy，组合该权重资本归零且 hard fail；不得用另一 sleeve 掩盖执行破产。

## 3. 冻结权重

- controls：`w∈{0,1}`，只验证组件 exact parity；
- ensemble：`w∈{0.25,0.50,0.75}`；
- 结果后不得增加 `0.1` 步长、最小方差、最大 Sharpe、vol parity、drawdown parity 或滚动权重。

## 4. 小时级保守风险路径

必须从同一冻结直接 `1h` 数据重放两组件：

1. 每小时各 sleeve 按自身合同处理 open orders、fee、funding 与 stop；
2. 记录各 sleeve 的 favorable、adverse 与 close equity；flat 时三者相同；
3. 组合 favorable peak 使用 `wF_C+(1-w)F_R`，组合 adverse trough 使用 `wA_C+(1-w)A_R`；这保守假设两个 sleeve 的有利/不利小时极值可同时发生；
4. 每小时顺序固定 `favorable → adverse → close`，以此计算 ordered MDD；
5. close-path terminal 必须等于两个独立组件 terminal 的权重和，绝对误差 `<=1e-12`。

## 5. 成本与压力

- base：各组件原 `0.001/fill + 4bps/fill + actual funding`；
- stress：两组件均改为 `8bps/fill`，其余不变；
- delay：两个组件所有日频 orders 各额外延迟一天；CBCT 小时 stop 仍按因果 level执行，RCR state execution整体再延迟一天。

## 6. 门禁

- base hard target：组合 terminal `>=20x` 且 conservative ordered MDD `<=20%`；
- 两个 sleeve 均无 intrahour bankruptcy；
- stress `>=16x/MDD<=22%`；
- delay `>=8x/MDD<=25%` 且 log-growth retention `>=70%`；
- 完整年及 rolling 365d 正收益比例均 `>=70%`；
- 至少 `20` 笔独立 closed trades，两个 sleeve 各至少 `10` 笔；
- 单一 sleeve 对总正 log-growth 的贡献不得超过 `75%`；最大单笔对组合正 log-growth贡献 `<=30%`；
- 三个 ensemble weights 若都失败则 research line关闭；只允许唯一 hard-pass path进入 audit。

## 7. 固定交付与停止规则

- 两组件 base/stress/delay exact parity；
- 逐小时 favorable/adverse/close 组合路径、权重表、相关性与 drawdown overlap attribution；
- growth/risk frontier 完整交互 HTML；
- 测试、JSON/CSV、中文诊断、core ledger和索引；
- `0` hard-pass：`HARD-GATE-FAILED`并关闭 family，不搜索新权重、不换风险臂、不引入杠杆；audit/prospective保持未读取。
