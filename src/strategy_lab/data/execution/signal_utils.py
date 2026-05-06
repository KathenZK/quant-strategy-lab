from __future__ import annotations

import pandas as pd


def cross_section_zscore(frame: pd.DataFrame) -> pd.DataFrame:
    mean = frame.mean(axis=1)
    std = frame.std(axis=1, ddof=0).replace(0.0, pd.NA)
    return frame.sub(mean, axis=0).div(std, axis=0).fillna(0.0)
