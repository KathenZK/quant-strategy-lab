# HYPE-1D-MA7-SNC02 MA05 固定ATR灾难止损 Stage C 冻结合同

> 冻结日期：2026-08-20。状态：`diagnostic-only / explore / not promoted / not live-ready`。本合同在首次运行 Stage C 结果前写入；结果揭示后不得新增ATR档位、修改门槛并重称预注册结果。

## 1. 研究问题与边界

Stage A 的 `MA05_1X` 为 `+148.79%/-33.61%`，但剩余最大回撤包含数次新 cross 后快速反转；Stage B 的确认扩仓全部失败，而固定0.5x虽压到 `-19.50%`，却机械损失过多趋势收益。Stage C 因此保留 `1x` 趋势仓位，只测试固定入场ATR灾难止损能否限制单笔异常不利路径。

所有臂固定：

- exact SNC02 镜像入场：`fresh SMA7 cross + directional slope >= 0.02ATR7`，下一UTC open；
- exact `MA05` 结构退出：long `close < SMA7 - 0.5ATR7` 且SMA7单日slope `<=0`，short镜像，下一UTC open；
- 每次入场目标 `1x`，不试仓、不扩仓、不部分止盈、不保本移动；
- `SMA7/ATR7`、成本、funding、窗口和V7.1身份不变。

全部历史已揭示，只能作机制诊断；不登记版本、不promotion、不修改runner。

## 2. 固定实验臂

| Arm | 固定止损参考 |
|---|---|
| `MA05_CTRL` | 无小时硬止损，仅MA05与镜像信号 |
| `MA05_HS10` | long `entry - 1.0*entry_ATR7`，short镜像 |
| `MA05_HS15` | long `entry - 1.5*entry_ATR7`，short镜像 |
| `MA05_HS20` | long `entry - 2.0*entry_ATR7`，short镜像 |

`entry_ATR7` 取生成入场信号当日的已闭合ATR7，整笔固定，不追踪、不放宽。三档是首次结果前冻结的有限单调网格；运行后不得在其间补 `1.25/1.75` 等点。

## 3. 小时成交与事件优先级

- 使用已闭合 Binance HYPEUSDT perpetual `1h` OHLC；止损在入场小时立即生效。
- long 若小时open `<= stop`，按更差的open参考成交；否则若小时low `<= stop`，按stop参考成交。short镜像。
- 所有成交价仍另扣手续费 `0.001/fill` 与不利滑点；跳过stop时不得按旧stop美化成交。
- 同一小时只存在单侧stop，不利用high/low先后顺序选择更优结果。
- 下一UTC open若有已排队的镜像信号或MA05退出，先执行日线动作；若止损已提前平仓，旧pending按trade id失效。
- 止损后保持flat，只有新的SNC02 fresh qualified signal才能重新入场；不按旧趋势状态自动重入。
- 日线动作额外 `1d lag` 压力只延迟信号/MA05动作；小时固定stop仍持续生效。

## 4. 数据、成本与窗口

- 市场：Binance USDⓈ-M perpetual `HYPEUSDT`；信号 `1d`，止损路径 `1h`，UTC。
- 主窗：扩展 `2025-05-31 -> 2026-08-20 terminal`；同时报告canonical `2025-05-31 -> 2026-08-06`。
- 成本：手续费 `0.001/fill`，基础滑点 `4bps/fill`，实际funding；压力为 `8bps`、funding-off、额外 `1d lag`。
- 最近flat-start：`1d/7d/1m/3m/6m/1y`；年度flat-start：2025 partial、2026 YTD。
- 风险：按小时open、stop fill、funding pre/post和实际订单顺序计算chronological `1h` MDD。

## 5. 首次运行前冻结的判定

以 `MA05_CTRL` 与其2026-08-09 long为参照：

- `MDD20_PASS`：扩展窗真实1h MDD `>= -20%`。
- `ROBUSTNESS_PASS`：扩展窗净收益 `>0`、PF `>=1`、8bps净收益 `>0`、额外1日lag净收益 `>0`。
- `RETURN_RETENTION_PASS`：扩展窗净收益至少为 `MA05_CTRL` 的 `50%`。
- `LATEST_TREND_CAPTURE_PASS`：存在2026-08-09 long、截至terminal仍持有，且campaign净收益至少为control同笔的 `60%`。
- `CONTINUATION_CANDIDATE`：同时满足上述四项。

通过者仍只是post-reveal候选。若多个档位通过，优先较宽且收益保留更高者；不得仅按主窗最高收益事后选择更窄档。若三档全部失败，本固定ATR止损机制关闭，不继续细搜倍数。

## 6. 产物

- 研究脚本：`scripts/research_hype_1d_ma7_snc02_ma05_hard_stop_stage_c.py`
- 机器证据：`artifacts/hype_1d_ma7_snc02_ma05_hard_stop_stage_c_2026-08-20.json`
- 诊断报告：`diagnostics/hype-1d-ma7-snc02-ma05-hard-stop-stage-c-2026-08-20.md`
