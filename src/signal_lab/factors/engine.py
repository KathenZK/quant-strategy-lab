from __future__ import annotations

import pandas as pd

from signal_lab.factors.base import FactorRegistry, PandasFactor


def compute_factor_frame(
    frame: pd.DataFrame,
    factor: PandasFactor,
    *,
    group_column: str = "symbol",
    time_column: str = "ts",
) -> pd.DataFrame:
    working = frame.copy()
    sort_by = [column for column in (group_column, time_column) if column in working.columns]
    if sort_by:
        working = working.sort_values(sort_by).reset_index(drop=True)

    required = [column for column in factor.metadata.inputs if column not in working.columns]
    if required:
        raise ValueError(f"missing inputs for {factor.metadata.name}: {required}")

    if group_column in working.columns and not factor.metadata.cross_sectional:
        values = working.groupby(group_column, group_keys=False, sort=False).apply(factor.compute)
        if isinstance(values.index, pd.MultiIndex):
            values = values.reset_index(level=0, drop=True)
        working[factor.metadata.name] = values.sort_index()
    else:
        working[factor.metadata.name] = factor.compute(working)

    columns = [column for column in ("ts", "exchange", "symbol", "market_type") if column in working.columns]
    columns.append(factor.metadata.name)
    return working[columns]


def compute_factor_bundle(
    frame: pd.DataFrame,
    registry: FactorRegistry,
    *,
    factor_names: list[str] | None = None,
    group_column: str = "symbol",
    time_column: str = "ts",
) -> pd.DataFrame:
    names = factor_names or registry.names()
    base_columns = [column for column in ("ts", "exchange", "symbol", "market_type") if column in frame.columns]
    bundle = frame[base_columns].copy()

    for name in names:
        factor = registry.get(name)
        values = compute_factor_frame(frame, factor, group_column=group_column, time_column=time_column)
        bundle = bundle.merge(values, on=base_columns, how="left")
    return bundle.sort_values([column for column in ("ts", "symbol") if column in bundle.columns]).reset_index(drop=True)
