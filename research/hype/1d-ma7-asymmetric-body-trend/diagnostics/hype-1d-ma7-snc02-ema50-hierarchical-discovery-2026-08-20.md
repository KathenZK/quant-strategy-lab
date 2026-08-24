# HYPE-1D-MA7-SNC02 EMA50分层趋势发现诊断

> 日期：2026-08-20。状态：`post-reveal successor diagnostic / trend-first / not promoted / not live-ready`。

## 结论

`HCSM50` 未通过趋势优先门，不能推进。EMA50把无约束CSM02的delayed trade从38笔降到16笔、总campaign从59降到37笔，但仍在08-12用delayed short破坏08-09 exact long；major MFE加权capture只有 `36.01%`，低于control的 `47.19%`。扩展窗为 `-10.93%/-57.50%`，8bps为负。

这不是EMA50 span需要调参，而是机制冲突：慢趋势EMA在新趋势切换初期天然滞后。最新行情开始时EMA50仍允许旧方向short补票，因此它不能同时完成“更早发现新趋势”和“保护刚成立的快趋势”。继续搜索EMA span只会在同一历史上折中两类错误。

## 1. 固定机制

按[首次运行前合同](../specs/hype-1d-ma7-snc02-ema50-hierarchical-discovery-contract-2026-08-20.md)：

- exact SNC02始终不受EMA过滤；
- 只有delayed maturation额外要求close位于目标EMA50侧且EMA50单日斜率同向；
- EMA固定 `span=50, adjust=False, min_periods=50`；
- 无stop、止盈、仓位变化和lag筛选。

## 2. 对比

| 指标 | SNC02 | 无约束CSM02 | HCSM50 |
|---|---:|---:|---:|
| 净收益 | +32.56% | -66.03% | -10.93% |
| 真实1h MDD | -50.79% | -81.68% | -57.50% |
| Campaign | 25 | 59 | 37 |
| Delayed trade | 0 | 38 | 16 |
| Delayed gross为正 | — | 11 | 6 |
| 补回事后major cross | — | 13 | 6 |
| Major正收益campaign | 7 | 15 | 11 |
| Major加权capture | **47.19%** | 39.26% | 36.01% |
| 08-09 long连续到terminal | **是** | 否 | 否 |

HCSM50补到的六个raw-cross机会包括2025-08-07 long、09-20 short、10-06 short、10-30 short、2026-02-06 short与04-04 long。但“补到事后机会”没有转化为更完整的campaign；EMA过滤仍允许趋势内反向切换。

## 3. 最新路径

- 08-08 exact qualified long，08-09 `55.113`入场；
- 08-09之后的反向seed在EMA50旧趋势条件下仍能成熟；
- 08-12 `54.492`翻空，long gross `-1.13%`；
- 因此没有连续持有到terminal，直接违反第一目标。

这比净收益失败更关键：一个声称改善趋势发现的机制，不能破坏control已经正确抓住的目标趋势。

## 4. 裁决

- `HCSM50`：`TREND_FIRST_GATE_FAILED / STOP`；不搜索EMA span、斜率幅度或价格距离。
- exact SNC02继续作为唯一权威反转基准。
- rejected cross只保留shadow opportunity标签；在没有独立信息前，不得获得自动反手权。
- 不登记版本、不改V7.1、不推进runner。

## 证据

- [冻结合同](../specs/hype-1d-ma7-snc02-ema50-hierarchical-discovery-contract-2026-08-20.md)
- [机器证据](../artifacts/hype_1d_ma7_snc02_ema50_hierarchical_discovery_2026-08-20.json)及其[SHA256](../artifacts/hype_1d_ma7_snc02_ema50_hierarchical_discovery_2026-08-20.json.sha256)
- [可执行脚本](../scripts/research_hype_1d_ma7_snc02_ema50_hierarchical_discovery.py)
