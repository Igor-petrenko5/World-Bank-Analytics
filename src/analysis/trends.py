
from pathlib import Path

import numpy as np
import pandas as pd

from src.analysis.group_analysis import (
    load_data,
    METRICS,
)


OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "reports"
    / "statistics"
)

START_YEAR = 2000
END_YEAR = 2023


def calculate_trends(df, group_column):

    results = []

    for (group_name, year), group in df.groupby(
        [group_column, "year"]
    ):

        total_countries = group["country_id"].nunique()

        for metric in METRICS:

            values = group[metric].dropna()

            results.append({
                "group": group_name,
                "year": year,
                "metric": metric,
                "countries": total_countries,
                "valid_observations": len(values),
                "coverage_pct": (
                    len(values) / total_countries * 100
                ),
                "mean": values.mean(),
                "median": values.median(),
                "std": values.std(),
                "min": values.min(),
                "max": values.max(),
            })

    report = pd.DataFrame(results)

    report = report.sort_values(
        ["group", "metric", "year"]
    ).reset_index(drop=True)

    grouped = report.groupby(
        ["group", "metric"]
    )

    report["yearly_change"] = (
        grouped["mean"].diff()
    )

    previous = grouped["mean"].shift(1)
    previous_year = grouped["year"].shift(1)

    report.loc[
        report["year"] - previous_year != 1,
        "yearly_change",
    ] = np.nan

    report["yearly_change_pct"] = np.where(
        (previous > 0)
        & (report["metric"] == "gdp_per_capita_usd")
        & (report["year"] - previous_year == 1),
        (report["mean"] / previous - 1) * 100,
        np.nan,
    )

    baseline = report.loc[
        report["year"] == START_YEAR,
        ["group", "metric", "mean"],
    ].rename(columns={"mean": "baseline_mean"})

    report = report.merge(
        baseline,
        on=["group", "metric"],
        how="left",
        validate="many_to_one",
    )

    report["change_from_2000"] = (
        report["mean"] - report["baseline_mean"]
    )

    return report.replace(
        [np.inf, -np.inf], np.nan
    )


def calculate_long_term_changes(report):

    start = report[
        report["year"] == START_YEAR
    ][
        ["group", "metric", "mean", "coverage_pct"]
    ].rename(columns={
        "mean": "start_value",
        "coverage_pct": "start_coverage",
    })

    end = report[
        report["year"] == END_YEAR
    ][
        ["group", "metric", "mean", "coverage_pct"]
    ].rename(columns={
        "mean": "end_value",
        "coverage_pct": "end_coverage",
    })

    result = start.merge(
        end,
        on=["group", "metric"],
        validate="one_to_one",
    )

    result["start_year"] = START_YEAR
    result["end_year"] = END_YEAR

    result["absolute_change"] = (
        result["end_value"]
        - result["start_value"]
    )

    result["change_pct"] = np.where(
        (result["start_value"] > 0)
        & (result["metric"] == "gdp_per_capita_usd"),
        (
            result["end_value"]
            / result["start_value"] - 1
        ) * 100,
        np.nan,
    )

    return result.replace(
        [np.inf, -np.inf], np.nan
    )


def main():

    OUTPUT.mkdir(parents=True, exist_ok=True)

    df = load_data()

    df["global_group"] = "All economies"

    income_trends = calculate_trends(
        df, "income_level"
    )

    region_trends = calculate_trends(
        df, "region_name"
    )

    global_trends = calculate_trends(
        df, "global_group"
    )

    long_term = calculate_long_term_changes(
        income_trends
    )

    reports = {
        "income_group_trends": income_trends,
        "region_trends": region_trends,
        "global_trends": global_trends,
        "long_term_changes": long_term,
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

    print("\n=== LONG TERM CHANGES ===")

    print(
        long_term[
            long_term["metric"].isin([
                "gdp_per_capita_usd",
                "life_expectancy",
            ])
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
