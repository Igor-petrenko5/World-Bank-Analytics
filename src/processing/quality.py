
import numpy as np
import pandas as pd


KEY = [
    "country_id",
    "indicator_code",
    "year"
]


def validate_indicators(
    df,
    expected_codes,
    expected_countries,
    start_year,
    end_year
):

    required = KEY + ["value"]

    missing_columns = set(required) - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing columns: {missing_columns}"
        )

    if df.empty:
        raise ValueError("Empty dataset")

    if df[KEY].isna().any().any():
        raise ValueError("Missing primary key values")

    if df.duplicated(KEY).any():
        raise ValueError("Duplicate observations")

    if not df["year"].between(
        start_year, end_year
    ).all():
        raise ValueError("Invalid year")

    numeric = pd.to_numeric(
        df["value"], errors="coerce"
    )

    invalid = df["value"].notna() & numeric.isna()

    if invalid.any():
        raise ValueError("Non-numeric values")

    if not np.isfinite(numeric.dropna()).all():
        raise ValueError("Infinite values")

    expected_grid = pd.MultiIndex.from_product(
        [
            expected_countries,
            expected_codes,
            range(start_year, end_year + 1)
        ],
        names=KEY
    )

    actual_grid = pd.MultiIndex.from_frame(
        df[KEY]
    )

    missing_keys = expected_grid.difference(
        actual_grid
    )

    unexpected_keys = actual_grid.difference(
        expected_grid
    )

    if len(missing_keys):
        raise ValueError(
            f"Missing observations: {len(missing_keys)}"
        )

    if len(unexpected_keys):
        raise ValueError(
            f"Unexpected observations: {len(unexpected_keys)}"
        )

    return {
        "total_rows": len(df),
        "duplicate_rows": 0,
        "missing_keys": 0,
        "missing_values": int(
            numeric.isna().sum()
        ),
        "completeness_pct": round(
            numeric.notna().mean() * 100, 2
        ),
        "status": "PASS"
    }


def build_quality_report(df):

    report = (
        df.groupby(
            ["indicator_code", "indicator_name"]
        )
        .agg(
            total_rows=("value", "size"),
            filled_rows=("value", "count"),
            min_value=("value", "min"),
            max_value=("value", "max"),
            first_year=("year", "min"),
            last_year=("year", "max")
        )
        .reset_index()
    )

    report["missing_rows"] = (
        report["total_rows"]
        - report["filled_rows"]
    )

    report["completeness_pct"] = (
        report["filled_rows"]
        / report["total_rows"] * 100
    ).round(2)

    return report.sort_values(
        "completeness_pct",
        ascending=False
    )
