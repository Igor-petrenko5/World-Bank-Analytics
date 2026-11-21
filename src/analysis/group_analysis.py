
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

from src.database.connection import get_engine


OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "reports"
    / "statistics"
)

METRICS = [
    "gdp_growth_pct",
    "gdp_per_capita_usd",
    "inflation_pct",
    "unemployment_pct",
    "life_expectancy",
    "health_expenditure_pct_gdp",
    "internet_users_pct",
]

PAIRS = [
    ("gdp_growth_pct", "unemployment_pct"),
    ("inflation_pct", "gdp_growth_pct"),
    ("gdp_per_capita_usd", "life_expectancy"),
    ("health_expenditure_pct_gdp", "life_expectancy"),
    ("internet_users_pct", "gdp_per_capita_usd"),
]


def load_data():

    engine = get_engine()

    try:
        df = pd.read_sql(
            """
            SELECT *
            FROM marts.vw_macro_indicators
            WHERE year BETWEEN 2000 AND 2023
            """,
            engine,
        )
    finally:
        engine.dispose()

    if df.duplicated(["country_id", "year"]).any():
        raise ValueError("Duplicate country-year records")

    for metric in METRICS:
        df[metric] = pd.to_numeric(
            df[metric], errors="coerce"
        )

    return df.replace([np.inf, -np.inf], np.nan)


def group_statistics(df, group_column):

    results = []

    for name, group in df.groupby(group_column):

        for metric in METRICS:

            values = group[metric].dropna()

            total = len(group)
            valid = len(values)

            results.append({
                "group": name,
                "metric": metric,
                "countries": group["country_id"].nunique(),
                "valid_observations": valid,
                "coverage_pct": valid / total * 100,
                "mean": values.mean(),
                "median": values.median(),
                "std": values.std(),
                "min": values.min(),
                "max": values.max(),
                "q25": values.quantile(0.25),
                "q75": values.quantile(0.75),
            })

    return pd.DataFrame(results)


def group_correlations(df):

    results = []

    for name, group in df.groupby("income_level"):

        for x, y in PAIRS:

            sample = group[[x, y]].dropna()

            if len(sample) < 10:
                continue

            if sample[x].nunique() < 2:
                continue

            if sample[y].nunique() < 2:
                continue

            pearson = pearsonr(
                sample[x], sample[y]
            ).statistic

            spearman = spearmanr(
                sample[x], sample[y]
            ).statistic

            results.append({
                "income_level": name,
                "indicator_x": x,
                "indicator_y": y,
                "pearson": pearson,
                "spearman": spearman,
                "observations": len(sample),
            })

    return pd.DataFrame(results)


def main():

    OUTPUT.mkdir(parents=True, exist_ok=True)

    df = load_data()

    income = group_statistics(df, "income_level")
    regions = group_statistics(df, "region_name")
    correlations = group_correlations(df)

    reports = {
        "income_group_statistics": income,
        "region_statistics": regions,
        "group_correlations": correlations,
    }

    for name, report in reports.items():

        path = OUTPUT / f"{name}.csv"

        report.to_csv(
            path,
            index=False,
            encoding="utf-8-sig",
        )

        print(f"Saved: {path}")
        print(f"Rows: {len(report)}")

    print("\n=== GROUP CORRELATIONS ===")

    print(
        correlations.to_string(index=False)
    )


if __name__ == "__main__":
    main()
