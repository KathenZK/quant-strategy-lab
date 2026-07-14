# SOL-1H-Volatility-Compression-Breakout Decision Log

## 2026-07-13：建立独立 family 并刷新数据

- 新建 `SOL-1H-Volatility-Compression-Breakout`（`SOL-1H-VCB`），不继承 `SOL-1H-Adaptive-Regime` 的 V1/V2。
- 机制固定为多 K 波动压缩 arm、冻结区间、有限窗口突破确认和 ATR 正偏退出，排除 V2 邻域继续微调。
- 从 Binance FAPI 刷新最近两年闭合 `SOLUSDT` perpetual `1h` K：`2024-07-13T07:00:00Z` 至 `2026-07-13T06:00:00Z`，`17520` 根；missing、duplicate、critical null、OHLCV violation、raw/normalized mismatch 均为 `0`。
- 成本固定为 fee `0.001`/fill、slippage `4 bps`/fill，并逐笔计真实 funding。
- 旧 SOL 研究已揭盲的 `2026-04-03` 至 `2026-07-03` 只作 reused-holdout audit；新增 `2026-07-03` 至 `2026-07-13` 仅作短 fresh-forward 观察。

## 2026-07-13：首轮扩展搜索 NO-GO

- 搜索 `3000` 组 entry state，生成 `14848` 个候选，`1579` 个通过 train/validation 基础门槛；`10x / 80% / <20% DD` prefit hard pass 为 `0`。
- prefit-only 最佳观察 `SOL_1H_VCB_R002346`：prefit annual `1.5279x`、DD `-16.69%`、win `37.84%`、trades `37`，payoff `3.868`。
- reused holdout annual `0.8870x`、return `-2.94%`、DD `-8.87%`；fresh forward `0` 笔。
- current full annual `1.4126x`、DD `-16.69%`；K+2 full annual `1.0425x`、DD `-27.65%`，延迟稳健性失败。
- 决策：首轮 `NO-GO / explore / not promoted / not live-ready`；不登记 V1，不继续扩大同一参数空间。

