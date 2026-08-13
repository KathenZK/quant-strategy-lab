"""Build zoomable, self-contained OAPP and PEHC trade-path HTML artifacts."""

from __future__ import annotations

from dataclasses import asdict
from html import escape
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/hype/1d-ma7-asymmetric-body-trend"
SCRIPT_DIR = FAMILY_DIR / "scripts"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"

OAPP_RESEARCH_PATH = (
    SCRIPT_DIR / "research_hype_1d_ma7_opportunity_aware_profit_protection.py"
)
OAPP_CHAMPION_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_champion.json"
)
OAPP_FINAL_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_final.json"
)
PEHC_SHADOW_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_shadow_candidate.json"
)
SELECTED_V4_PATH = ARTIFACT_DIR / "hype_1d_ma7_separated_summary_2026-08-04.json"

OAPP_HTML_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_opportunity_aware_profit_protection_2026-08-10_"
    "full_trade_path_zoomable_v2.html"
)
PEHC_HTML_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_profit_exit_handoff_continuity_2026-08-10_"
    "full_trade_path_zoomable_v2.html"
)
MANIFEST_PATH = ARTIFACT_DIR / (
    "hype_1d_ma7_oapp_pehc_zoomable_trade_paths_v2_2026-08-10_manifest.json"
)
GENERATOR_PATH = Path(__file__).resolve()
TEST_PATH = ROOT / "tests/test_hype_1d_ma7_oapp_pehc_zoomable_trade_paths_v2.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sidecar(path: Path) -> Path:
    return path.with_suffix(".sha256")


def read_locked(path: Path) -> tuple[dict[str, Any], str]:
    hash_path = sidecar(path)
    if not path.is_file() or not hash_path.is_file():
        raise RuntimeError(f"missing locked artifact: {path.name}")
    fields = hash_path.read_text(encoding="utf-8").strip().split()
    digest = sha256(path)
    if len(fields) != 2 or fields[0] != digest or fields[1] != path.name:
        raise RuntimeError(f"invalid sidecar: {path.name}")
    return json.loads(path.read_text(encoding="utf-8")), digest


def write_locked_bytes(path: Path, payload: bytes) -> dict[str, Any]:
    hash_path = sidecar(path)
    if path.exists() or hash_path.exists():
        raise RuntimeError(f"locked artifact already exists: {path.name}")
    digest = hashlib.sha256(payload).hexdigest()
    with path.open("xb") as handle:
        handle.write(payload)
    with hash_path.open("x", encoding="utf-8") as handle:
        handle.write(f"{digest}  {path.name}\n")
    return {"path": str(path), "sha256": digest, "bytes": len(payload)}


def write_locked_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode()
    return write_locked_bytes(path, encoded)


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def candles_from_context(context: Any) -> list[dict[str, Any]]:
    candles = [
        {
            "ts": context.book.ts[index].isoformat(),
            "open": _finite(context.book.open[index]),
            "high": _finite(context.book.high[index]),
            "low": _finite(context.book.low[index]),
            "close": _finite(context.book.close[index]),
            "ma7": _finite(context.features.ma7[index]),
            "displayOnlyTerminal": False,
        }
        for index in range(context.book.count)
    ]
    terminal_ts = context.book.terminal_ts
    match = context.market.hourly.loc[context.market.hourly["ts"] == terminal_ts]
    if len(match) != 1:
        raise RuntimeError("unique terminal-open hourly row required")
    terminal_open = float(match.iloc[0]["open"])
    candles.append(
        {
            "ts": terminal_ts.isoformat(),
            "open": terminal_open,
            "high": terminal_open,
            "low": terminal_open,
            "close": terminal_open,
            "ma7": _finite(context.features.ma7[-1]),
            "displayOnlyTerminal": True,
        }
    )
    return candles


def _validate_run(run: dict[str, Any], candle_days: set[str], label: str) -> None:
    trades = run.get("trades")
    path = run.get("path")
    if not isinstance(trades, list) or not isinstance(path, list):
        raise RuntimeError(f"{label}: retained trades/path required")
    if len(trades) != int(run["metrics"]["closed_trades"]):
        raise RuntimeError(f"{label}: trade count mismatch")
    previous_exit: str | None = None
    for row in trades:
        entry = str(row["entry_ts"])
        exit_ = str(row["exit_ts"])
        if entry > exit_ or (previous_exit is not None and entry < previous_exit):
            raise RuntimeError(f"{label}: invalid trade ordering")
        if entry[:10] not in candle_days or exit_[:10] not in candle_days:
            raise RuntimeError(f"{label}: trade outside candle range")
        previous_exit = exit_
    for row in path:
        if str(row["ts"])[:10] not in candle_days:
            raise RuntimeError(f"{label}: equity path outside candle range")


def compact_run(run: dict[str, Any], label: str) -> dict[str, Any]:
    return {
        "label": label,
        "armId": run["arm_id"],
        "metrics": run["metrics"],
        "trades": [
            {
                "side": row["side"],
                "entryTs": row["entry_ts"],
                "exitTs": row["exit_ts"],
                "entry": float(row["entry_price"]),
                "exit": float(row["exit_price"]),
                "reason": row["exit_reason"],
                "returnPct": float(row["net_return"]) * 100.0,
                "barsHeld": int(row.get("bars_held", 0)),
                "entryLeverage": float(row.get("entry_leverage", 1.0)),
            }
            for row in run["trades"]
        ],
        "equity": [
            {
                "ts": row["ts"],
                "value": float(row["close_equity"]),
                "position": int(row["position"]),
                "action": row["action"],
            }
            for row in run["path"]
        ],
    }


def _oapp_events(run: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index, row in enumerate(run["trades"], 1):
        reason = str(row["exit_reason"])
        if reason.startswith("long_mfe_") or reason == "short_rsi_take_profit":
            events.append(
                {
                    "event": reason,
                    "ts": row["exit_ts"],
                    "tradeIndex": index - 1,
                    "side": row["side"],
                    "price": float(row["exit_price"]),
                }
            )
    return events


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "启用" if value else "关闭"
    if value is None:
        return "OFF"
    return str(value)


def parameter_groups(
    *,
    long_config: dict[str, Any],
    short_config: dict[str, Any],
    oapp_config: dict[str, Any],
    pehc_config: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    groups = [
        {
            "title": "共同执行与指标",
            "rows": [
                ["MA", "SMA7", "所有入场、迟滞退出与反手确认使用7日简单均线。"],
                ["ATR", "ATR7", "容错带、趋势斜率归一化、保护与MFE阈值使用7日ATR。"],
                ["RSI", "Wilder RSI6", "仅固定OAPP的盈利空头止盈模块使用。"],
                ["目标杠杆", "1.0x", "每次入场按当时权益建立1倍目标仓位，持仓数量不日内再平衡。"],
                ["手续费", "0.10% / fill", "Binance taker fee，每个实际成交腿单独扣除。"],
                ["滑点", "4 bps / fill", "base回测的不利成交滑点。"],
                ["Funding", "实际历史funding", "只在真实持仓时按事件结算；shadow不计资金。"],
                ["日线执行", "close signal -> next open", "日线收盘信号最早在下一UTC日open成交。"],
            ],
        },
        {
            "title": "exact V4 多头腿",
            "rows": [
                ["entry_mode", _fmt(long_config["entry_mode"]), "前一日不在MA7上方、当日重新收在MA7上方才形成fresh reclaim。"],
                ["slope", f"{long_config['slope_lookback']}d / {long_config['slope_min_atr']} ATR", "MA7向上斜率必须至少达到阈值。"],
                ["confirm_days", _fmt(long_config["confirm_days"]), "站上MA7的收盘确认日数。"],
                ["entry_buffer_atr", _fmt(long_config["entry_buffer_atr"]), "多头入场不额外要求高于MA7的ATR距离。"],
                ["exit", f"{long_config['exit_confirm_days']}d below MA7-{long_config['exit_buffer_atr']}ATR", "收盘严格跌出MA7下方迟滞带后退出。"],
                ["hard_stop_atr", _fmt(long_config["hard_stop_atr"]), "0表示固定硬止损关闭。"],
                ["trail_atr", _fmt(long_config["trail_atr"]), "原V4多头保护/追踪止损距离；命中可产生forced-short资格。"],
                ["max_hold_days", _fmt(long_config["max_hold_days"]), "最长持仓90日。"],
                ["cooldown_days", _fmt(long_config["cooldown_days"]), "多头退出后2日不重新开多。"],
                ["休眠字段", f"pullback={long_config['pullback_lookback']}, breakout={long_config['breakout_lookback']}", "entry_mode=reclaim时这两个搜索遗留字段不参与路径。"],
            ],
        },
        {
            "title": "exact V4 空头腿",
            "rows": [
                ["entry_mode", _fmt(short_config["entry_mode"]), "前一日不在MA7下方、当日重新收在MA7下方才形成fresh reclaim。"],
                ["slope", f"{short_config['slope_lookback']}d / {short_config['slope_min_atr']} ATR", "MA7向下斜率归一化后至少达到0.02。"],
                ["confirm_days", _fmt(short_config["confirm_days"]), "跌破MA7的收盘确认日数。"],
                ["entry_buffer_atr", _fmt(short_config["entry_buffer_atr"]), "自然空头要求收盘低于MA7至少0.10ATR。"],
                ["exit", f"{short_config['exit_confirm_days']}d above MA7+{short_config['exit_buffer_atr']}ATR", "V4使用0.75ATR空头退出迟滞，防止过早回补。"],
                ["slope_exit_lookback", _fmt(short_config["slope_exit_lookback"]), "1日MA7下降斜率消失时也可退出空头。"],
                ["hard_stop_atr", _fmt(short_config["hard_stop_atr"]), "空头1.5ATR固定保护止损。"],
                ["trail_atr", _fmt(short_config["trail_atr"]), "空头4ATR追踪保护。"],
                ["max_hold_days", _fmt(short_config["max_hold_days"]), "空头最长持有20日。"],
                ["cooldown_days", _fmt(short_config["cooldown_days"]), "空头退出后5日不重新开空。"],
                ["forced reversal", "MA_ONLY", "多头追踪止损后的拟反手open必须严格低于上一完整日MA7；不再要求short slope。"],
                ["休眠字段", f"pullback={short_config['pullback_lookback']}, breakout={short_config['breakout_lookback']}", "entry_mode=reclaim时这两个字段不参与路径。"],
            ],
        },
        {
            "title": "固定 OAPP 增量",
            "rows": [
                ["entry filter", _fmt(oapp_config["entry"]["kind"]), "关闭；完全继承exact V4入场。"],
                ["long activation", f"{oapp_config['long_exit']['activation_atr']} ATR", "多头历史最高收盘浮盈至少达到0.5ATR后才允许利润保护。"],
                ["long giveback", f"{float(oapp_config['long_exit']['giveback']) * 100:.0f}% of MFE", "当前收盘从最高浮盈回吐至少10%。"],
                ["long confirm", f"{oapp_config['long_exit']['confirm_days']} days", "上述回吐条件连续2个持仓日成立才在下一open退出。"],
                ["profit guard", f"> {float(oapp_config['roundtrip_guard']) * 100:.2f}% gross", "退出时仍须有超过0.28%的毛利润，避免利润保护变成亏损止损。"],
                ["short MFE exit", _fmt(oapp_config["short_exit"]["mode"]), "关闭；空头不使用对称MFE回吐。"],
                ["short RSI", f"RSI6 < {oapp_config['short_rsi']['threshold']} for {oapp_config['short_rsi']['days']} days", "实际持仓空头连续2日RSI6低于20且仍盈利，下一open止盈。"],
            ],
        },
    ]
    if pehc_config is not None:
        groups.append(
            {
                "title": "PEHC_294 增量",
                "rows": [
                    ["inherits", "固定 OAPP + exact V4", "实际交易层完整继承上面全部参数。"],
                    ["shadow expiry", f"{pehc_config['expiry_days']} calendar days", "OAPP平多后保留虚拟原V4多头状态至age=8；age>8才过期。"],
                    ["shadow trigger", "exact V4 protective/trailing stop only", "只有虚拟原仓本应触发V4保护/追踪止损时才产生handoff opportunity；普通MA退出不产生。"],
                    ["short slope", _fmt(pehc_config["slope_threshold"]), "handoff空头不要求额外MA7向下斜率。"],
                    ["anti-chase", _fmt(pehc_config["chase_cap_atr"]), "INF表示没有ATR追价上限，但仍必须严格低于上一完整日MA7。"],
                    ["execution", _fmt(pehc_config["execution"]), "机会出现后等到下一UTC日open重新检查条件，合格才开空。"],
                    ["single consume", "enabled", "每个shadow最多消费一次，不能叠加、刷新或重复开空。"],
                    ["cancel", "expiry / native exit / actual new long / nonfinite", "超期、虚拟原仓先自然退出、实际新开多或数据异常都会清除shadow。"],
                    ["episode filters", "all episodes", "allowed/blocked列表均为空；正式候选不事后删除任何历史episode。"],
                    ["capital isolation", "strict", "shadow没有仓位、费用、funding或PnL，只保留反手机会资格。"],
                ],
            }
        )
    return groups


HTML_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{--bg:#0c1116;--panel:#121920;--panel2:#171f27;--line:#2a3540;--text:#edf2f5;--muted:#91a0ac;--accent:#d6b45f;--long:#5b9fd6;--short:#d17691;--up:#58ad88;--down:#ca6d72;--shadow:#8a86a8}
*{box-sizing:border-box}html{color-scheme:dark}body{margin:0;background:var(--bg);color:var(--text);font:14px Geist,Satoshi,"Helvetica Neue",system-ui,sans-serif;line-height:1.45}
main{max-width:1580px;margin:0 auto;padding:28px 24px 64px}.eyebrow{color:var(--accent);font:600 11px ui-monospace,SFMono-Regular,Menlo,monospace;letter-spacing:.16em;text-transform:uppercase}h1{margin:7px 0 8px;font-size:clamp(24px,3vw,39px);line-height:1.05;letter-spacing:-.035em;font-weight:650}h2{margin:0;font-size:17px;letter-spacing:-.015em}p{color:var(--muted);max-width:92ch;margin:0}.lede{font-size:15px;line-height:1.65}
.header{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(280px,.7fr);gap:32px;align-items:end;margin-bottom:24px}.status{border-top:1px solid var(--line);padding-top:12px;display:grid;grid-template-columns:1fr auto;gap:6px 16px;font:12px ui-monospace,SFMono-Regular,Menlo,monospace}.status span:nth-child(odd){color:var(--muted)}
.toolbar{position:sticky;top:0;z-index:3;display:flex;flex-wrap:wrap;align-items:center;gap:8px;padding:12px 0;background:color-mix(in srgb,var(--bg) 94%,transparent);backdrop-filter:blur(12px)}button{appearance:none;border:1px solid var(--line);border-radius:7px;background:var(--panel2);color:var(--text);padding:8px 11px;font:600 12px ui-monospace,SFMono-Regular,Menlo,monospace;cursor:pointer;transition:transform .18s cubic-bezier(.16,1,.3,1),border-color .18s,color .18s}button:hover{border-color:#52606d}button:active{transform:translateY(1px) scale(.985)}button.active{border-color:var(--accent);color:var(--accent)}button:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.spacer{flex:1}.window-readout{min-width:300px;text-align:right;color:var(--muted);font:12px ui-monospace,SFMono-Regular,Menlo,monospace}
.metrics{display:grid;grid-template-columns:1.4fr repeat(4,minmax(130px,1fr));gap:1px;background:var(--line);border:1px solid var(--line);margin:2px 0 14px}.metric{background:var(--panel);padding:11px 13px;min-height:67px}.metric span{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.metric b{display:block;margin-top:6px;font:600 17px ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums}
.chart-shell{border:1px solid var(--line);background:var(--panel);border-radius:10px;overflow:hidden}.chart-help{display:flex;flex-wrap:wrap;gap:8px 20px;padding:10px 13px;border-bottom:1px solid var(--line);color:var(--muted);font:12px ui-monospace,SFMono-Regular,Menlo,monospace}.chart-help b{color:var(--text);font-weight:600}.canvas-wrap{position:relative;height:min(72vh,780px);min-height:560px}canvas{display:block;width:100%;height:100%;touch-action:none;cursor:grab}canvas.dragging{cursor:grabbing}.tooltip{position:absolute;display:none;pointer-events:none;min-width:220px;padding:9px 11px;border:1px solid #44515d;border-radius:7px;background:rgba(12,17,22,.94);box-shadow:0 12px 32px rgba(4,8,12,.26);font:12px ui-monospace,SFMono-Regular,Menlo,monospace;color:var(--text);white-space:pre-line;transform:translate(12px,12px)}
.range-panel{display:grid;grid-template-columns:auto 1fr auto 1fr;gap:9px;align-items:center;padding:11px 13px;border-top:1px solid var(--line);color:var(--muted);font:11px ui-monospace,SFMono-Regular,Menlo,monospace}input[type=range]{width:100%;accent-color:var(--accent)}
.lower{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(330px,.75fr);gap:18px;margin-top:18px}.section{border-top:1px solid var(--line);padding-top:13px}.section-head{display:flex;justify-content:space-between;align-items:baseline;gap:12px;margin-bottom:9px}.section-head span{color:var(--muted);font:11px ui-monospace,SFMono-Regular,Menlo,monospace}.table-wrap{overflow:auto;max-height:520px;border-bottom:1px solid var(--line)}table{width:100%;border-collapse:collapse;font-size:12px}th,td{padding:8px 9px;border-top:1px solid var(--line);text-align:left;white-space:nowrap}th{position:sticky;top:0;background:var(--bg);color:var(--muted);font:600 10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.08em}tbody tr{cursor:pointer}tbody tr:hover{background:#17212a}td.num{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums}.long{color:var(--long)}.short{color:var(--short)}
.params{display:grid;gap:16px}.param-group{border-top:1px solid var(--line);padding-top:10px}.param-group h3{font-size:13px;margin:0 0 8px}.param-row{display:grid;grid-template-columns:120px 145px 1fr;gap:9px;padding:7px 0;border-top:1px solid #202a33;font-size:11px}.param-row code{color:var(--accent);font:11px ui-monospace,SFMono-Regular,Menlo,monospace;word-break:break-word}.param-row span:last-child{color:var(--muted)}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:12px;color:var(--muted);font-size:11px}.legend i{display:inline-block;width:13px;height:2px;margin-right:5px;vertical-align:middle}.note{margin-top:18px;padding-top:12px;border-top:1px solid var(--line);font-size:12px;color:var(--muted)}
@media(max-width:900px){main{padding:20px 14px 48px}.header,.lower{grid-template-columns:1fr}.window-readout{width:100%;min-width:0;text-align:left}.metrics{grid-template-columns:repeat(2,1fr)}.metric:first-child{grid-column:1/-1}.canvas-wrap{height:620px;min-height:500px}.range-panel{grid-template-columns:auto 1fr}.param-row{grid-template-columns:100px 120px 1fr}}
@media(max-width:560px){.metrics{grid-template-columns:1fr}.metric:first-child{grid-column:auto}.canvas-wrap{height:540px}.param-row{grid-template-columns:1fr}.range-panel{grid-template-columns:1fr}.toolbar button{flex:1 0 auto}}
</style>
</head>
<body>
<main>
  <div class="header">
    <div><div class="eyebrow">HYPE / 1D / MA7 / frozen research path</div><h1>__TITLE__</h1><p class="lede">这不是静态截图。把鼠标放在主图上滚轮缩放，按住拖拽平移；点击交易行聚焦该笔，双击图表或点击“全局复位”恢复完整432日视图。</p></div>
    <div class="status"><span>数据角色</span><b id="evidenceRole"></b><span>路径</span><b id="pathCount"></b><span>外部依赖</span><b>0</b></div>
  </div>
  <div class="toolbar" aria-label="图表工具栏">
    <button id="candidate" class="active" data-testid="candidate-toggle">候选策略</button><button id="control" data-testid="control-toggle">Exact V4</button>
    <button id="zoomIn" data-testid="zoom-in">放大</button><button id="zoomOut" data-testid="zoom-out">缩小</button><button id="panLeft">向左</button><button id="panRight">向右</button><button id="reset" data-testid="reset-view">全局复位</button>
    <div class="spacer"></div><div id="windowReadout" class="window-readout" data-testid="window-readout"></div>
  </div>
  <div id="metrics" class="metrics"></div>
  <div class="chart-shell">
    <div class="chart-help"><span><b>滚轮</b> 以指针为中心缩放</span><span><b>拖拽</b> 左右平移</span><span><b>双击 / 0</b> 全局复位</span><span><b>+ / -</b> 键盘缩放</span><span><b>点击交易</b> 聚焦完整持仓</span></div>
    <div class="canvas-wrap"><canvas id="chart" data-testid="zoom-chart"></canvas><div id="tooltip" class="tooltip"></div></div>
    <div class="range-panel"><label for="rangeStart">起点</label><input id="rangeStart" type="range"><label for="rangeEnd">终点</label><input id="rangeEnd" type="range"></div>
  </div>
  <div class="legend"><span><i style="background:var(--accent)"></i>SMA7</span><span><i style="background:var(--long)"></i>Long trade</span><span><i style="background:var(--short)"></i>Short trade</span><span><i style="background:var(--shadow)"></i>OAPP / shadow / handoff event</span><span><i style="background:#d9e0e5"></i>Equity</span></div>
  <div class="lower">
    <section class="section"><div class="section-head"><h2>逐笔交易</h2><span>点击任意一行聚焦</span></div><div class="table-wrap"><table><thead><tr><th>#</th><th>Side</th><th>Entry</th><th>Exit</th><th>Reason</th><th>Net</th><th>Days</th></tr></thead><tbody id="trades"></tbody></table></div></section>
    <section class="section"><div class="section-head"><h2>冻结参数</h2><span>休眠字段明确标注</span></div><div id="params" class="params"></div></section>
  </div>
  <div class="note">完整历史均为 researcher-exposed diagnostic evidence。图表缩放只改变显示窗口，不改变任何交易、指标、artifact SHA链或研究状态。</div>
</main>
<script>
window.TRADE_PATH_DATA=__PAYLOAD__;
const D=window.TRADE_PATH_DATA,C=document.getElementById('chart'),X=C.getContext('2d'),tip=document.getElementById('tooltip');
const day=s=>String(s).slice(0,10),N=D.candles.length,dayIndex=new Map(D.candles.map((r,i)=>[day(r.ts),i]));
let state={mode:'candidate',start:0,end:N-1,hover:null,dragging:false,lastX:0};const MIN_SPAN=Math.min(8,N),pointers=new Map();
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function normalizeWindow(start,end){start=Math.round(start);end=Math.round(end);if(end-start+1<MIN_SPAN){const c=(start+end)/2;start=Math.floor(c-(MIN_SPAN-1)/2);end=start+MIN_SPAN-1}if(start<0){end-=start;start=0}if(end>N-1){start-=end-(N-1);end=N-1}return[clamp(start,0,N-1),clamp(end,0,N-1)]}
function setWindow(start,end){[state.start,state.end]=normalizeWindow(start,end);syncRange();render()}
function resetView(){setWindow(0,N-1)}
function zoom(factor,anchor=.5){const span=state.end-state.start+1,target=clamp(Math.round(span*factor),MIN_SPAN,N),center=state.start+anchor*(span-1);setWindow(center-anchor*(target-1),center+(1-anchor)*(target-1))}
function pan(bars){setWindow(state.start+bars,state.end+bars)}
function focusTrade(index){const t=D[state.mode].trades[index];if(!t)return;const a=dayIndex.get(day(t.entryTs)),b=dayIndex.get(day(t.exitTs)),pad=Math.max(3,Math.round((b-a+1)*.35));setWindow(a-pad,b+pad)}
function syncRange(){const a=document.getElementById('rangeStart'),b=document.getElementById('rangeEnd');for(const r of[a,b]){r.min=0;r.max=N-1;r.step=1}a.value=state.start;b.value=state.end;const span=state.end-state.start+1,zoomLevel=(N/span).toFixed(1);document.getElementById('windowReadout').textContent=`${day(D.candles[state.start].ts)} → ${day(D.candles[state.end].ts)} | ${span} days | ${zoomLevel}x`}
function fmt(v,d=2){return Number.isFinite(Number(v))?Number(v).toFixed(d):'—'}
function resize(){const rect=C.getBoundingClientRect(),dpr=Math.min(2,window.devicePixelRatio||1);C.width=Math.max(1,Math.round(rect.width*dpr));C.height=Math.max(1,Math.round(rect.height*dpr));X.setTransform(dpr,0,0,dpr,0,0);render()}
function render(){const rect=C.getBoundingClientRect(),W=rect.width,H=rect.height,R=D[state.mode],P=D.candles,loI=state.start,hiI=state.end,span=hiI-loI+1,left=64,right=18,top=25,priceH=Math.round(H*.62),eqTop=Math.round(H*.72),eqH=H-eqTop-35,plotW=W-left-right;
X.clearRect(0,0,W,H);X.fillStyle='#10171e';X.fillRect(0,0,W,H);const visible=P.slice(loI,hiI+1),rawLo=Math.min(...visible.map(r=>r.low)),rawHi=Math.max(...visible.map(r=>r.high)),pad=Math.max((rawHi-rawLo)*.06,rawHi*.004),pLo=rawLo-pad,pHi=rawHi+pad;
const xx=i=>left+(i-loI+.5)*plotW/span,yy=v=>top+(pHi-v)/(pHi-pLo)*priceH;X.font='11px ui-monospace,SFMono-Regular,Menlo,monospace';X.textBaseline='middle';
for(let k=0;k<=5;k++){const y=top+k*priceH/5,val=pHi-k*(pHi-pLo)/5;X.strokeStyle='#25313b';X.beginPath();X.moveTo(left,y);X.lineTo(W-right,y);X.stroke();X.fillStyle='#82909c';X.fillText(fmt(val,2),5,y)}
X.save();X.beginPath();X.rect(left,top,plotW,priceH);X.clip();const cw=clamp(plotW/span*.62,1.2,9);for(let i=loI;i<=hiI;i++){const r=P[i],x=xx(i),yo=yy(r.open),yc=yy(r.close);X.strokeStyle=r.close>=r.open?'#58ad88':'#ca6d72';X.beginPath();X.moveTo(x,yy(r.high));X.lineTo(x,yy(r.low));X.stroke();X.fillStyle=X.strokeStyle;X.fillRect(x-cw/2,Math.min(yo,yc),cw,Math.max(1,Math.abs(yc-yo)))}
X.strokeStyle='#d6b45f';X.lineWidth=1.5;X.beginPath();let begun=false;for(let i=loI;i<=hiI;i++){const v=P[i].ma7;if(v==null)continue;begun?X.lineTo(xx(i),yy(v)):(X.moveTo(xx(i),yy(v)),begun=true)}X.stroke();
for(const t of R.trades){const a=dayIndex.get(day(t.entryTs)),b=dayIndex.get(day(t.exitTs));if(b<loI||a>hiI)continue;X.strokeStyle=t.side==='long'?'#5b9fd6':'#d17691';X.lineWidth=2;X.beginPath();X.moveTo(xx(a),yy(t.entry));X.lineTo(xx(b),yy(t.exit));X.stroke();for(const [i,v] of[[a,t.entry],[b,t.exit]]){if(i<loI||i>hiI)continue;X.fillStyle=X.strokeStyle;X.beginPath();X.arc(xx(i),yy(v),3.5,0,Math.PI*2);X.fill()}}
for(const e of D.events){const i=dayIndex.get(day(e.ts));if(i==null||i<loI||i>hiI)continue;X.strokeStyle=e.event==='handoff_accept'?'#58ad88':String(e.event).includes('reject')?'#ca6d72':'#8a86a8';X.globalAlpha=.62;X.setLineDash([3,4]);X.beginPath();X.moveTo(xx(i),top);X.lineTo(xx(i),top+priceH);X.stroke();X.setLineDash([]);X.globalAlpha=1}X.restore();
const eqMap=new Map(R.equity.map(r=>[day(r.ts),r])),eqVals=[];for(let i=loI;i<=hiI;i++){const q=eqMap.get(day(P[i].ts));if(q)eqVals.push(q.value)}const eLo=Math.min(...eqVals),eHi=Math.max(...eqVals),ePad=Math.max((eHi-eLo)*.08,.01),ey=v=>eqTop+(eHi+ePad-v)/(eHi-eLo+2*ePad)*eqH;X.strokeStyle='#25313b';X.beginPath();X.moveTo(left,eqTop);X.lineTo(W-right,eqTop);X.stroke();X.fillStyle='#82909c';X.fillText('EQUITY',5,eqTop+8);X.strokeStyle='#d9e0e5';X.lineWidth=1.5;X.beginPath();begun=false;for(let i=loI;i<=hiI;i++){const q=eqMap.get(day(P[i].ts));if(!q)continue;begun?X.lineTo(xx(i),ey(q.value)):(X.moveTo(xx(i),ey(q.value)),begun=true)}X.stroke();X.lineWidth=1;
if(state.hover!=null&&state.hover>=loI&&state.hover<=hiI){const i=state.hover,x=xx(i),r=P[i];X.strokeStyle='#6f7d89';X.setLineDash([2,3]);X.beginPath();X.moveTo(x,top);X.lineTo(x,eqTop+eqH);X.stroke();X.setLineDash([]);const q=eqMap.get(day(r.ts));const ev=D.events.filter(e=>day(e.ts)===day(r.ts)).map(e=>e.event).join(', ');tip.textContent=`${day(r.ts)}\nO ${fmt(r.open)}  H ${fmt(r.high)}\nL ${fmt(r.low)}  C ${fmt(r.close)}\nMA7 ${fmt(r.ma7)}  Equity ${q?fmt(q.value,3):'—'}${ev?'\nEvent '+ev:''}`}
const m=R.metrics;document.getElementById('metrics').innerHTML=[['Strategy',R.label],['Net return',fmt(m.net_return_pct)+'%'],['Real 1h MDD',fmt(m.chronological_1h_mdd_pct)+'%'],['Daily MDD',fmt(m.daily_extreme_mdd_pct)+'%'],['Trades',m.closed_trades]].map(v=>`<div class="metric"><span>${v[0]}</span><b>${v[1]}</b></div>`).join('');syncRange()}
function renderTrades(){const R=D[state.mode];document.getElementById('trades').innerHTML=R.trades.map((t,i)=>`<tr data-index="${i}"><td class="num">${i+1}</td><td class="${t.side}">${t.side}</td><td>${t.entryTs}</td><td>${t.exitTs}</td><td>${t.reason}</td><td class="num">${fmt(t.returnPct)}%</td><td class="num">${t.barsHeld}</td></tr>`).join('');document.querySelectorAll('#trades tr').forEach(row=>row.onclick=()=>focusTrade(Number(row.dataset.index)))}
function renderParams(){document.getElementById('params').innerHTML=D.parameterGroups.map(g=>`<div class="param-group"><h3>${g.title}</h3>${g.rows.map(r=>`<div class="param-row"><b>${r[0]}</b><code>${r[1]}</code><span>${r[2]}</span></div>`).join('')}</div>`).join('')}
function setMode(mode){state.mode=mode;for(const id of['candidate','control'])document.getElementById(id).classList.toggle('active',id===mode);renderTrades();render()}
document.getElementById('candidate').onclick=()=>setMode('candidate');document.getElementById('control').onclick=()=>setMode('control');document.getElementById('zoomIn').onclick=()=>zoom(.65);document.getElementById('zoomOut').onclick=()=>zoom(1.55);document.getElementById('panLeft').onclick=()=>pan(-Math.max(1,Math.round((state.end-state.start+1)*.2)));document.getElementById('panRight').onclick=()=>pan(Math.max(1,Math.round((state.end-state.start+1)*.2)));document.getElementById('reset').onclick=resetView;
document.getElementById('rangeStart').oninput=e=>setWindow(Math.min(Number(e.target.value),state.end-MIN_SPAN+1),state.end);document.getElementById('rangeEnd').oninput=e=>setWindow(state.start,Math.max(Number(e.target.value),state.start+MIN_SPAN-1));
C.addEventListener('wheel',e=>{e.preventDefault();const r=C.getBoundingClientRect(),anchor=clamp((e.clientX-r.left-64)/Math.max(1,r.width-82),0,1);zoom(e.deltaY < 0 ? .72 : 1.38,anchor)},{passive:false});C.ondblclick=resetView;
C.addEventListener('pointerdown',e=>{pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});C.setPointerCapture(e.pointerId);if(pointers.size===1){state.dragging=true;state.lastX=e.clientX;C.classList.add('dragging')}});C.addEventListener('pointermove',e=>{const r=C.getBoundingClientRect();if(pointers.has(e.pointerId))pointers.set(e.pointerId,{x:e.clientX,y:e.clientY});if(state.dragging&&pointers.size===1){const dx=e.clientX-state.lastX,bars=-dx/Math.max(1,r.width-82)*(state.end-state.start+1);if(Math.abs(bars)>=.35){pan(bars);state.lastX=e.clientX}}else if(!state.dragging){const i=clamp(Math.floor(state.start+(e.clientX-r.left-64)/Math.max(1,r.width-82)*(state.end-state.start+1)),state.start,state.end);state.hover=i;tip.style.display='block';tip.style.left=clamp(e.clientX-r.left,0,r.width-245)+'px';tip.style.top=clamp(e.clientY-r.top,0,r.height-130)+'px';render()}});function endPointer(e){pointers.delete(e.pointerId);if(!pointers.size){state.dragging=false;C.classList.remove('dragging')}}C.addEventListener('pointerup',endPointer);C.addEventListener('pointercancel',endPointer);C.addEventListener('pointerleave',e=>{if(!state.dragging){state.hover=null;tip.style.display='none';render()}endPointer(e)});
window.addEventListener('keydown',e=>{if(e.target.matches('input'))return;if(e.key==='+'||e.key==='=')zoom(.65);else if(e.key==='-')zoom(1.55);else if(e.key==='0')resetView();else if(e.key==='ArrowLeft')pan(-1);else if(e.key==='ArrowRight')pan(1)});window.addEventListener('resize',resize);
document.getElementById('evidenceRole').textContent=D.evidenceRole;document.getElementById('pathCount').textContent=`${D.candidate.trades.length} / ${D.control.trades.length} trades`;renderParams();renderTrades();syncRange();resize();
window.__ZOOMABLE_TRADE_PATH__={getState:()=>({...state}),setWindow,resetView,zoom,pan,focusTrade,setMode,render};
</script>
</body>
</html>'''


def build_document(
    *,
    title: str,
    evidence_role: str,
    candles: list[dict[str, Any]],
    candidate: dict[str, Any],
    candidate_label: str,
    control: dict[str, Any],
    events: list[dict[str, Any]],
    parameter_groups_payload: list[dict[str, Any]],
) -> tuple[bytes, dict[str, Any]]:
    if len(candles) < 2:
        raise RuntimeError("at least two candles required")
    days = {str(row["ts"])[:10] for row in candles}
    if len(days) != len(candles):
        raise RuntimeError("candle days must be unique")
    _validate_run(candidate, days, "candidate")
    _validate_run(control, days, "control")
    for row in events:
        if str(row["ts"])[:10] not in days:
            raise RuntimeError("event outside candle range")
    payload = {
        "schema": "hype-ma7-zoomable-trade-path-v2",
        "title": title,
        "evidenceRole": evidence_role,
        "candles": candles,
        "candidate": compact_run(candidate, candidate_label),
        "control": compact_run(control, "Exact V4 1x"),
        "events": events,
        "parameterGroups": parameter_groups_payload,
    }
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    document = (
        HTML_TEMPLATE.replace("__TITLE__", escape(title))
        .replace("__PAYLOAD__", data)
        .encode("utf-8")
    )
    audit = {
        "schema": payload["schema"],
        "sha256": hashlib.sha256(document).hexdigest(),
        "bytes": len(document),
        "candles": len(candles),
        "candidate_trades": len(candidate["trades"]),
        "control_trades": len(control["trades"]),
        "events": len(events),
        "all_trades_connected": True,
        "display_only_terminal_candles": sum(
            bool(row.get("displayOnlyTerminal")) for row in candles
        ),
        "interaction": {
            "wheel_zoom": True,
            "drag_pan": True,
            "range_controls": True,
            "double_click_reset": True,
            "keyboard_zoom_pan": True,
            "trade_row_focus": True,
            "responsive_canvas": True,
            "crosshair_tooltip": True,
        },
        "external_dependencies": 0,
    }
    return document, audit


def _assert_metric_equal(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    for key in (
        "net_return_pct",
        "chronological_1h_mdd_pct",
        "daily_extreme_mdd_pct",
        "closed_trades",
    ):
        if not math.isclose(
            float(actual[key]),
            float(expected[key]),
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise RuntimeError(f"frozen metric drift: {key}")


def main() -> None:
    for path in (OAPP_HTML_PATH, PEHC_HTML_PATH, MANIFEST_PATH):
        if path.exists() or sidecar(path).exists():
            raise RuntimeError(f"zoomable V2 artifact already exists: {path.name}")
    oapp_champion, oapp_champion_sha = read_locked(OAPP_CHAMPION_PATH)
    oapp_final, oapp_final_sha = read_locked(OAPP_FINAL_PATH)
    pehc_shadow, pehc_shadow_sha = read_locked(PEHC_SHADOW_PATH)
    selected_v4 = json.loads(SELECTED_V4_PATH.read_text(encoding="utf-8"))
    v1_selected = selected_v4["historically_profitable_all_checks"][0]

    research = load_module(OAPP_RESEARCH_PATH, "hype_oapp_zoomable_v2_research")
    manifest, champion, oapp_config, runtime = research.load_champion()
    if champion["arm_id"] != "C_2AA556432E9E":
        raise RuntimeError("unexpected fixed OAPP identity")
    engine, risk, adapter, _, context = runtime
    oapp_control = research.run_one(
        engine=engine,
        risk=risk,
        adapter=adapter,
        context=context,
        window=(0, 432),
        config=None,
        retain=True,
    )
    oapp_candidate = research.run_one(
        engine=engine,
        risk=risk,
        adapter=adapter,
        context=context,
        window=(0, 432),
        config=oapp_config,
        retain=True,
    )
    _assert_metric_equal(oapp_candidate["metrics"], oapp_final["full"]["one_x"])
    _assert_metric_equal(oapp_control["metrics"], oapp_final["full"]["control"])
    if pehc_shadow.get("status") != "SHADOW_FROZEN":
        raise RuntimeError("PEHC shadow artifact is not frozen")
    pehc_candidate = pehc_shadow["candidate"]
    pehc_control = pehc_shadow["exact_v4"]
    _assert_metric_equal(pehc_control["metrics"], oapp_control["metrics"])

    candles = candles_from_context(context)
    long_config = asdict(context.long_config)
    short_config = asdict(context.short_config)
    if long_config["exit_buffer_atr"] != 0.75 or short_config["exit_buffer_atr"] != 0.75:
        raise RuntimeError("exact V4 0.75ATR exit hysteresis drift")
    if v1_selected["long_config"]["side"] != 1 or v1_selected["short_config"]["side"] != -1:
        raise RuntimeError("selected V4 ancestry drift")

    oapp_params = parameter_groups(
        long_config=long_config,
        short_config=short_config,
        oapp_config=champion["config"],
        pehc_config=None,
    )
    pehc_params = parameter_groups(
        long_config=long_config,
        short_config=short_config,
        oapp_config=champion["config"],
        pehc_config=pehc_shadow["config"],
    )
    oapp_document, oapp_audit = build_document(
        title="固定 OAPP vs Exact V4 — Zoomable V2",
        evidence_role="Exposed history / OAPP H FAIL / diagnostic only",
        candles=candles,
        candidate=oapp_candidate,
        candidate_label="Fixed OAPP 1x",
        control=oapp_control,
        events=_oapp_events(oapp_candidate),
        parameter_groups_payload=oapp_params,
    )
    pehc_document, pehc_audit = build_document(
        title="PEHC_294 vs Exact V4 — Zoomable V2",
        evidence_role="Exposed history / shadow-only / prospective pending",
        candles=candles,
        candidate=pehc_candidate,
        candidate_label="PEHC_294 1x shadow candidate",
        control=pehc_control,
        events=pehc_candidate["handoff_events"],
        parameter_groups_payload=pehc_params,
    )
    oapp_write = write_locked_bytes(OAPP_HTML_PATH, oapp_document)
    pehc_write = write_locked_bytes(PEHC_HTML_PATH, pehc_document)
    manifest_payload = {
        "schema": "hype-ma7-oapp-pehc-zoomable-trade-paths-v2-manifest",
        "status": "PASS",
        "strategy_artifacts_unchanged": True,
        "old_locked_html_replaced": False,
        "source_artifacts": {
            "oapp_champion": oapp_champion_sha,
            "oapp_final": oapp_final_sha,
            "pehc_shadow": pehc_shadow_sha,
            "selected_v4": sha256(SELECTED_V4_PATH),
        },
        "implementation": {
            "generator": {"path": str(GENERATOR_PATH), "sha256": sha256(GENERATOR_PATH)},
            "test": {"path": str(TEST_PATH), "sha256": sha256(TEST_PATH)},
        },
        "oapp": {"audit": oapp_audit, "artifact": oapp_write},
        "pehc": {"audit": pehc_audit, "artifact": pehc_write},
        "frozen_identity": {
            "oapp_arm_id": oapp_champion["arm_id"],
            "oapp_config_sha256": oapp_champion["config_sha256"],
            "pehc_arm_id": pehc_shadow["config"]["arm_id"],
            "pehc_config_sha256": pehc_shadow["config_sha256"],
            "exact_v4_control": "registered HYPE-1D-MA7-ABT-V4 1x",
        },
        "research_state": "diagnostic visualization only; no registration/promotion/live change",
    }
    research.assert_pins(manifest["pins"])
    write_locked_json(MANIFEST_PATH, manifest_payload)
    print(
        json.dumps(
            {
                "status": "PASS",
                "oapp": str(OAPP_HTML_PATH),
                "pehc": str(PEHC_HTML_PATH),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
