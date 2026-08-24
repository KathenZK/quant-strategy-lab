from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[4]
BASE_SCRIPT = (
    ROOT
    / "research/asset-portfolios/1d-ma7-taker-flow-meta-label/"
    "scripts/sync_binance_vision_tfml_5m.py"
)
FAMILY_DIR = ROOT / "research/asset-portfolios/1d-ma7-taker-flow-meta-label"
FRESH_ASSETS = {
    "XRP": "XRPUSDT",
    "DOGE": "DOGEUSDT",
    "ADA": "ADAUSDT",
    "LINK": "LINKUSDT",
    "LTC": "LTCUSDT",
    "DOT": "DOTUSDT",
    "AVAX": "AVAXUSDT",
    "UNI": "UNIUSDT",
}


def load_base_module():
    spec = importlib.util.spec_from_file_location(
        "binance_1d_ma7_tfml_p0e_flow_base",
        BASE_SCRIPT,
    )
    if spec is None or spec.loader is None:
        raise ImportError(BASE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    if any(asset == "HYPE" for asset in FRESH_ASSETS):
        raise RuntimeError("HYPE source is forbidden")
    base = load_base_module()
    base.ASSET_SYMBOLS = FRESH_ASSETS
    base.ASSET_SLUGS = {
        asset: symbol.lower() for asset, symbol in FRESH_ASSETS.items()
    }
    base.CACHE_DIR = (
        ROOT / "data/cache/binance_1d_ma7_tfml_p0_unaccepted"
    )
    base.ARTIFACT_DIR = FAMILY_DIR / "artifacts/p0e_data_2026-08-10"
    base.main()


if __name__ == "__main__":
    main()
