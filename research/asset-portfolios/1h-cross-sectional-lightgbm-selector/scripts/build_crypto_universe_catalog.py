from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
FAMILY_DIR = ROOT / "research/asset-portfolios/1h-cross-sectional-lightgbm-selector"
ARTIFACT_DIR = FAMILY_DIR / "artifacts"
INVENTORY_PATH = ARTIFACT_DIR / "binance_usdm_historical_inventory_2026-07-17.csv"
CATALOG_PATH = ARTIFACT_DIR / "binance_usdm_crypto_universe_catalog_2026-07-17.csv"
SUMMARY_PATH = ARTIFACT_DIR / "binance_usdm_crypto_universe_catalog_2026-07-17.json"

HISTORICAL_INDEX_SYMBOLS = {"BLUEBIRDUSDT", "DOTECOUSDT", "FOOTBALLUSDT"}
STABLECOIN_BASES = {"USDC"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the crypto-only historical Binance USD-M universe catalog."
    )
    parser.add_argument("--inventory", type=Path, default=INVENTORY_PATH)
    return parser.parse_args()


def classify(row: pd.Series) -> tuple[bool, str, str]:
    archive_symbol = str(row["symbol"])
    base = archive_symbol.removesuffix("USDT")
    if bool(row["in_current_exchange_info"]):
        if not bool(row.get("is_current_crypto_perpetual", False)):
            return (
                False,
                "current_exchange_info",
                f"non_crypto:{row.get('current_contract_type')}:{row.get('current_underlying_type')}",
            )
        if base in STABLECOIN_BASES:
            return False, "current_exchange_info+manual", "stablecoin_base"
        return True, "current_exchange_info", "crypto_perpetual"
    if archive_symbol in HISTORICAL_INDEX_SYMBOLS:
        return False, "historical_manual", "historical_index"
    if base in STABLECOIN_BASES:
        return False, "historical_manual", "stablecoin_base"
    return True, "historical_archive", "historical_crypto_inferred"


def main() -> None:
    args = parse_args()
    inventory = pd.read_csv(args.inventory)
    inventory = inventory.loc[inventory["kline_1h_months"].gt(0)].copy()
    classifications = inventory.apply(classify, axis=1, result_type="expand")
    classifications.columns = ["eligible", "classification_source", "reason"]
    catalog = pd.concat([inventory, classifications], axis=1)
    catalog["archive_symbol"] = catalog["symbol"]
    catalog["symbol"] = (
        catalog["archive_symbol"].str.removesuffix("USDT") + "/USDT:USDT"
    )
    columns = [
        "archive_symbol",
        "symbol",
        "eligible",
        "classification_source",
        "reason",
        "in_current_exchange_info",
        "current_status",
        "current_contract_type",
        "current_underlying_type",
        "current_underlying_subtype",
        "kline_1h_first_month",
        "kline_1h_last_month",
    ]
    catalog[columns].sort_values("archive_symbol").to_csv(CATALOG_PATH, index=False)
    reason_counts = {
        str(key): int(value) for key, value in catalog["reason"].value_counts().items()
    }
    summary = {
        "generated_at": pd.Timestamp.now("UTC").isoformat(),
        "archive_symbols_with_1h_klines": len(catalog),
        "eligible_crypto_symbols": int(catalog["eligible"].sum()),
        "excluded_symbols": int((~catalog["eligible"]).sum()),
        "reason_counts": reason_counts,
        "historical_index_exclusions": sorted(HISTORICAL_INDEX_SYMBOLS),
        "stablecoin_base_exclusions": sorted(STABLECOIN_BASES),
        "classification_policy": (
            "Current metadata requires contractType=PERPETUAL and underlyingType=COIN; "
            "historical contracts absent from current metadata remain included except "
            "documented historical indices and stablecoin bases."
        ),
        "catalog": str(CATALOG_PATH),
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
