# Binance 1D MA7 P2-E Hard-MDD 共享参数广搜合同

## 1. 研究问题

V1 原搜索把 `50%` 左右回撤作为软惩罚，导致近期收益候选在 2019–2026 长历史上暴露 `60%+` MDD。P2-B 至 P2-D 的局部修复均失败后，本轮回到完整共享状态机参数面，在排名前直接把用户目标 `MDD<=20%` 纳入 hard gate，判断现有 `SMA7/ATR7` 状态机空间内是否存在 BTC/ETH 共享参数的高收益低回撤组合。

## 2. 身份与边界

- Family：`Binance-1D-MA7-Asset-Specific-Search`
- Campaign：`P2-E hard-MDD shared search`
- 状态：`explore / not promoted / not live-ready`
- 固定核心：`SMA7/ATR7`、约 `1x`、单仓、非加仓、long/short 共用账户权益
- 本轮是现有 price-only MA7 状态机的重新搜索，不继承 P2-D 的 pullback/stop/exit 局部候选
- 不增加慢均线、RSI、OI、flow、ML、杠杆或组合资金分配；这些若需要必须另开机制合同

## 3. 数据与封存

- Development：`2019-12-24 00:00 UTC` 至 `2025-08-07 00:00 UTC` exclusive
- 数据：P2 冻结 direct `1h`、完整 UTC 日线、实际 funding/mark
- researcher-exposed audit：继续封存，不参与生成、排名、筛选或停止决定
- prospective：继续封存
- phase：本轮不参与搜索；候选冻结后才作非强制检查

## 4. 固定搜索空间

沿用 V1 engine 的离散状态机空间：

- entry：`regime / reclaim / pullback_reclaim / breakout`；short 另允许 `open_regime`
- slope lookback：`1/2/3/5/7`
- slope threshold：`0/0.02/0.05/0.10/0.20 ATR`
- confirm：`1/2/3d`
- entry buffer：`0/0.10/0.25/0.50 ATR`
- pullback lookback：`2/3/5/7/10d`
- pullback touch：`-0.50/-0.25/0/0.10/0.25 ATR`
- breakout lookback：`2/3/5/7/10/14d`
- exit confirm：`1/2/3d`
- exit buffer：`0/0.10/0.25/0.50/0.75/1.0 ATR`
- slope exit lookback：`off/1/2/3/5d`
- hard stop：`off/1.5/2/3/4/5 ATR`
- trail：`off/1.5/2/3/4/5/6 ATR`
- max hold：`off/10/20/30/60/90d`
- cooldown：`off/1/2/3/5d`

固定 seed `20260812`，每方向生成 `20,000` 个唯一配置。不得因结果不理想更换 seed 后拼接候选。

## 5. 分阶段选择

### Stage 1：单边共同筛选

- 每个配置分别在 BTC、ETH long-only 或 short-only full development 运行；
- 最低有效交易数每资产 `>=10`，禁止 bankruptcy，终值必须为正；
- 排名使用两资产最差 log-equity，并对超过 `20%` 的 MDD 逐资产惩罚；
- 每方向只保留前 `300` 进入稳定性审计。

单边 MDD 不作绝对淘汰，因为 long/short 在同账户的时序互补可能降低 combined MDD；最终 pair gate 必须严格执行 `20%`。

### Stage 2：单边稳定性

- 运行 calendar-year flat reset、rolling `730d/365d step`、full `8 bps` 与 `+1d delay`；
- 两资产 full base/stress/delay 必须都为正；
- calendar 与 rolling 以正收益比例、最差收益和最差 MDD排序；
- 每方向保留前 `60`，形成固定 `60×60=3,600` shared pairs。

### Stage 3：共享 pair hard gate

每个 pair 在 BTC、ETH combined full development 运行。排名前先记录：

1. 两资产是否均 `MDD>=-20%`；
2. 两资产是否均 `equity_multiple>=20.0`；
3. 是否 bankruptcy；
4. 两资产最差终值与最差 MDD。

只保留前 `100` 做完整稳定性审计；所有 hard-target hit 必须无条件进入审计，即使综合分数不是前100。

### Stage 4：候选审计

- full base / `8 bps` / `+1d delay`；
- calendar-year、rolling `730d`；
- combined、long-only、short-only；
- buy-and-hold 超额收益；
- exit reason、turnover、成本、funding、最大实际杠杆。

## 6. 冻结裁决

Development candidate 必须同时满足：

1. BTC、ETH base 各 `>=20x` 且 MDD `>=-20%`；
2. 两资产 `8 bps` 和 `+1d delay` 均为正，stress MDD 不低于 `-25%`；
3. 两资产 calendar 与 rolling 正收益比例均 `>=70%`；
4. 无 bankruptcy，最大实际杠杆漂移必须披露；
5. 不能由单一交易或单一 calendar year贡献大部分终值。

只有唯一候选满足上述门，才冻结参数并一次性打开 researcher-exposed audit。若无候选，裁决现有 V1 price-only MA7 参数面 `HARD-GATE-FAILED`，不得按排名次优继续调参；下一步必须建立 materially new mechanism contract。

## 7. 固定交付

- Stage 1 frontier、Stage 2 stability、Stage 3 pairs、Stage 4 metrics；
- 主 JSON 与中文 diagnostic；
- 本轮未形成 development candidate 时不生成 HTML、不登记 V2、不打开 audit、不推进 runner。

