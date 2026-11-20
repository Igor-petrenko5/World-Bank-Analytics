
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from scipy import stats

from src.database.connection import get_engine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("reports/statistics")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


INDICATORS = [
    "gdp_growth_pct",
    "inflation_pct",
    "unemployment_pct",
    "gdp_per_capita_usd",
    "life_expectancy",
    "health_expenditure_pct_gdp"
]

HYPOTHESES = {
    "H1_gdp_growth_unemployment": (
        "gdp_growth_pct",
        "unemployment_pct"
    ),
    "H2_inflation_gdp_growth": (
        "inflation_pct",
        "gdp_growth_pct"
    ),
    "H3_gdp_per_capita_life": (
        "gdp_per_capita_usd",
        "life_expectancy"
    ),
    "H4_health_life": (
        "health_expenditure_pct_gdp",
        "life_expectancy"
    )
}


def load_data():

    query = """
        SELECT
            country_id,
            country_name,
            year,
            gdp_growth_pct,
            inflation_pct,
            unemployment_pct,
            gdp_per_capita_usd,
            life_expectancy,
            health_expenditure_pct_gdp
        FROM marts.vw_macro_indicators
        ORDER BY country_id, year
    """

    engine = get_engine()

    try:
        with engine.connect() as connection:
            df = pd.read_sql(query, connection)
    finally:
        engine.dispose()

    logger.info("Loaded %s observations", len(df))

    return df


def validate_data(df):

    required = [
        "country_id",
        "country_name",
        "year"
    ] + INDICATORS

    missing = set(required) - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns: {sorted(missing)}"
        )

    if df.empty:
        raise ValueError("Dataset is empty")

    if df[["country_id", "year"]].isna().any().any():
        raise ValueError("Missing country-year key")

    if df.duplicated(["country_id", "year"]).any():
        raise ValueError("Duplicate country-year observations")

    if not df["year"].between(2000, 2025).all():
        raise ValueError("Unexpected year range")

    for col in INDICATORS:
        df[col] = pd.to_numeric(
            df[col], errors="coerce"
        )

        df[col] = df[col].replace(
            [np.inf, -np.inf], np.nan
        )

    return True


def benjamini_hochberg(p_values):

    p = np.asarray(p_values, dtype=float)
    result = np.full(len(p), np.nan)

    valid = np.isfinite(p)

    if not valid.any():
        return result

    values = p[valid]
    n = len(values)

    order = np.argsort(values)
    sorted_p = values[order]

    adjusted = sorted_p * n / np.arange(1, n + 1)

    adjusted = np.minimum.accumulate(
        adjusted[::-1]
    )[::-1]

    adjusted = np.clip(adjusted, 0, 1)

    restored = np.empty(n)
    restored[order] = adjusted

    result[valid] = restored

    return result


def fisher_confidence_interval(r, n):

    if n <= 3 or abs(r) >= 1:
        return np.nan, np.nan

    z = np.arctanh(r)
    se = 1 / np.sqrt(n - 3)

    lower = np.tanh(z - 1.96 * se)
    upper = np.tanh(z + 1.96 * se)

    return lower, upper


def calculate_pair(df, x_col, y_col):

    sample = df[[x_col, y_col]].copy()

    sample = sample.replace(
        [np.inf, -np.inf], np.nan
    ).dropna()

    n = len(sample)

    result = {
        "x": x_col,
        "y": y_col,
        "n": n,
        "pearson_r": np.nan,
        "pearson_p": np.nan,
        "pearson_ci_lower": np.nan,
        "pearson_ci_upper": np.nan,
        "spearman_r": np.nan,
        "spearman_p": np.nan
    }

    if n < 10:
        return result

    if sample[x_col].nunique() < 2:
        return result

    if sample[y_col].nunique() < 2:
        return result

    pearson = stats.pearsonr(
        sample[x_col],
        sample[y_col]
    )

    spearman = stats.spearmanr(
        sample[x_col],
        sample[y_col]
    )

    lower, upper = fisher_confidence_interval(
        pearson.statistic, n
    )

    result.update({
        "pearson_r": pearson.statistic,
        "pearson_p": pearson.pvalue,
        "pearson_ci_lower": lower,
        "pearson_ci_upper": upper,
        "spearman_r": spearman.statistic,
        "spearman_p": spearman.pvalue
    })

    return result


def create_quality_report(df):

    rows = []

    for col in INDICATORS:

        values = df[col].dropna()

        if len(values):

            q1 = values.quantile(0.25)
            q3 = values.quantile(0.75)
            iqr = q3 - q1

            outliers = (
                (values < q1 - 1.5 * iqr) |
                (values > q3 + 1.5 * iqr)
            ).sum()

        else:
            outliers = 0

        rows.append({
            "indicator": col,
            "total_rows": len(df),
            "valid_rows": int(df[col].notna().sum()),
            "missing_rows": int(df[col].isna().sum()),
            "completeness_pct": round(
                df[col].notna().mean() * 100, 2
            ),
            "outliers_iqr": int(outliers)
        })

    return pd.DataFrame(rows)


def analyze_by_year(df):

    rows = []

    for hypothesis, (x, y) in HYPOTHESES.items():

        for year, group in df.groupby("year"):

            result = calculate_pair(group, x, y)

            result["hypothesis"] = hypothesis
            result["year"] = int(year)

            rows.append(result)

    result_df = pd.DataFrame(rows)

    # Корректировка p-value отдельно для каждой гипотезы
    for col in ["pearson_p", "spearman_p"]:

        result_df[col.replace("_p", "_p_adj")] = (
            result_df.groupby("hypothesis")[col]
            .transform(
                lambda values: benjamini_hochberg(values)
            )
        )

    return result_df


def analyze_first_differences(df):

    ordered = df.sort_values(
        ["country_id", "year"]
    ).copy()

    rows = []

    for hypothesis, (x, y) in HYPOTHESES.items():

        changes = ordered.groupby(
            "country_id"
        )[[x, y]].diff()

        result = calculate_pair(changes, x, y)

        result["hypothesis"] = hypothesis

        # Объединённые изменения одной страны по годам
        # зависимы. Поэтому p-value и обычный CI
        # не интерпретируются как корректные
        # статистические выводы для панели.
        result["pearson_p"] = np.nan
        result["spearman_p"] = np.nan
        result["pearson_ci_lower"] = np.nan
        result["pearson_ci_upper"] = np.nan

        rows.append(result)

    return pd.DataFrame(rows)


def main():

    logger.info("Starting statistical analysis")

    df = load_data()

    validate_data(df)

    quality = create_quality_report(df)

    yearly = analyze_by_year(df)

    differences = analyze_first_differences(df)

    quality.to_csv(
        OUTPUT_DIR / "data_quality.csv",
        index=False
    )

    yearly.to_csv(
        OUTPUT_DIR / "correlations_by_year.csv",
        index=False
    )

    differences.to_csv(
        OUTPUT_DIR / "correlations_first_differences.csv",
        index=False
    )

    print("\n=== DATA QUALITY ===")
    print(quality.to_string(index=False))

    print("\n=== CORRELATIONS BY YEAR ===")
    print(yearly.to_string(index=False))

    print("\n=== FIRST DIFFERENCES ===")
    print(differences.to_string(index=False))

    logger.info("STATISTICAL ANALYSIS COMPLETED")


if __name__ == "__main__":
    main()
