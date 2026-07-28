"""One-shot 2026H1 reused-window audit for the 1h short-side baseline finding.

2026-01..2026-06 is a CONTAMINATED holdout for the EMA-cross mechanism family
(revealed by BIN-15M-EMAX-LGBM and BIN-1H-CSLGBM). This audit checks whether
the dev-window finding (death-cross shorts net positive in recent years)
survives in that window. Results are recorded whatever they are and must not
be used for tuning or cited as clean OOS / promotion evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

import run_baseline as rb

ec = rb.ec

AUDIT_FLOOR = pd.Timestamp("2026-01-01", tz="UTC")
# lake ends 2026-06-30 23:00; last entry with a complete 96h label window
AUDIT_CUTOFF = pd.Timestamp("2026-06-30 23:00", tz="UTC") - pd.Timedelta(hours=rb.ec.HORIZON_BARS + 1)


def side_stats(frame: pd.DataFrame, name: str) -> dict:
    if frame.empty:
        return {"events": 0}
    return rb.bracket_stats(frame, name)


def main() -> None:
    output = rb.ARTIFACT_DIR / "audit_2026h1_reused_window.json"
    if output.exists():
        raise RuntimeError(f"audit already ran once, refusing to rerun: {output}")

    rb.ensure_symbol_partition_cache()
    daily = rb.build_daily_stats()
    eligibility = rb.build_universe(daily)
    funding = ec.load_funding()
    funding_lookup = {
        key: ec.prepare_funding_lookup(group)
        for key, group in funding.groupby("sym_key", sort=False)
    }

    frames = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {
            executor.submit(
                rb.extract_symbol, key, eligibility, funding_lookup,
                AUDIT_FLOOR, AUDIT_CUTOFF,
            ): key
            for key in rb.list_cached_symbols()
        }
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                frames.append(result)
    events = pd.concat(frames, ignore_index=True)
    events["entry_ts"] = pd.to_datetime(events["entry_ts"], utc=True)
    pool = events.loc[events["in_trading_pool"]]

    months = pool["entry_ts"].dt.to_period("M").astype(str)
    report = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "status": "reused-window audit; NOT clean OOS; not usable for tuning or promotion",
        "window": [str(AUDIT_FLOOR), str(AUDIT_CUTOFF)],
        "events": {
            "rows": int(len(events)),
            "trading_pool_rows": int(len(pool)),
            "pool_long": int((pool["side"] == 1).sum()),
            "pool_short": int((pool["side"] == -1).sum()),
        },
        "pool_by_bracket": {
            name: {
                "short": side_stats(pool.loc[pool["side"] == -1], name),
                "long": side_stats(pool.loc[pool["side"] == 1], name),
            }
            for name in ec.BRACKETS
        },
        "pool_short_b4_2_monthly_net_mean_atr": {
            month: round(float(group.loc[group["side"] == -1, "b4_2_net_atr"].mean()), 4)
            for month, group in pool.groupby(months)
        },
    }
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"audit -> {output}")


if __name__ == "__main__":
    main()
