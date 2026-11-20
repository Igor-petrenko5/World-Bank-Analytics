
"""
Country-cluster bootstrap for World Bank Analytics.

Resamples countries with replacement while preserving each sampled
country's complete time series.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from sqlalchemy import text

from src.database.connection import get_engine


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "reports" / "statistics"

N_BOOTSTRAP = 2000
RANDOM_STATE = 42

HYPOTHESES = {
    "H1_gdp_growth_unemployment": (
        "gdp_growth_pct",
        "unemployment_pct",
    ),
    "H2_inflation_gdp_growth": (
        "inflation_pct",
        "gdp_growth_pct",
    ),
    "H3_gdp_per_capita_life": (
        "gdp_per_capita_usd",
        "life_expectancy",
    ),
    "H4_health_life": (
        "health_expenditure_pct_gdp",
        "life_expectancy",
    ),
}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def calculate_correlations(df, x, y):
    """Calculate Pearson and Spearman correlations."""

    data = df[[x, y]].copy()

    data[x] = pd.to_numeric(data[x], errors="coerce")
    data[y] = pd.to_numeric(data[y], errors="coerce")

    data = data.replace(
        [np.inf, -np.inf], np.nan
    ).dropna()

    if len(data) < 3:
        return None

    if data[x].nunique() < 2 or data[y].nunique() < 2:
        return None

    pearson = pearsonr(data[x], data[y])
    spearman = spearmanr(data[x], data[y])

    return {
        "n_observations": len(data),
        "pearson_r": float(pearson.statistic),
        "pearson_p": float(pearson.pvalue),
        "spearman_r": float(spearman.statistic),
        "spearman_p": float(spearman.pvalue),
    }


def cluster_bootstrap(
    df,
    x,
    y,
    n_bootstrap=N_BOOTSTRAP,
    random_state=RANDOM_STATE,
):
    """
    Bootstrap countries as clusters.

    Each selected country contributes its entire time series.
    Countries are sampled with replacement.
    """

    required = ["country_id", x, y]

    missing = set(required) - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    data = df[required].copy()

    data = data.dropna(subset=["country_id"])

    countries = data["country_id"].unique()

    if len(countries) < 10:
        raise ValueError(
            "At least 10 countries are required"
        )

    observed = calculate_correlations(
        data, x, y
    )

    if observed is None:
        raise ValueError(
            f"Cannot calculate observed correlation: {x}, {y}"
        )

    groups = {
        country: group
        for country, group in data.groupby(
            "country_id", sort=False
        )
    }

    rng = np.random.default_rng(random_state)

    pearson_values = []
    spearman_values = []

    for iteration in range(n_bootstrap):

        selected = rng.choice(
            countries,
            size=len(countries),
            replace=True,
        )

        sample = pd.concat(
            [groups[country] for country in selected],
            ignore_index=True,
        )

        result = calculate_correlations(
            sample, x, y
        )

        if result is None:
            continue

        pearson_values.append(
            result["pearson_r"]
        )

        spearman_values.append(
            result["spearman_r"]
        )

    if len(pearson_values) < n_bootstrap * 0.8:
        logger.warning(
            "Many bootstrap iterations were invalid: %s vs %s",
            x, y,
        )

    if not pearson_values:
        raise ValueError(
            "No valid bootstrap iterations"
        )

    def summarize(values, observed_value, method):

        return {
            "method": method,
            "observed_r": observed_value,
            "bootstrap_mean": float(np.mean(values)),
            "ci_lower": float(
                np.percentile(values, 2.5)
            ),
            "ci_upper": float(
                np.percentile(values, 97.5)
            ),
            "valid_iterations": len(values),
        }

    return {
        "n_countries": len(countries),
        "n_observations": observed["n_observations"],
        "pearson": summarize(
            pearson_values,
            observed["pearson_r"],
            "Pearson",
        ),
        "spearman": summarize(
            spearman_values,
            observed["spearman_r"],
            "Spearman",
        ),
    }


def load_data():

    query = text("""
        SELECT
            country_id,
            year,
            gdp_growth_pct,
            inflation_pct,
            unemployment_pct,
            gdp_per_capita_usd,
            life_expectancy,
            health_expenditure_pct_gdp
        FROM marts.vw_macro_indicators
    """)

    engine = get_engine()

    try:
        with engine.connect() as connection:
            return pd.read_sql(
                query, connection
            )
    finally:
        engine.dispose()


def run_analysis():

    logger.info(
        "Starting country-cluster bootstrap"
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = load_data()

    logger.info(
        "Loaded %s observations from %s countries",
        len(df),
        df["country_id"].nunique(),
    )

    results = []

    for name, (x, y) in HYPOTHESES.items():

        logger.info(
            "Processing %s: %s vs %s",
            name, x, y,
        )

        result = cluster_bootstrap(
            df,
            x,
            y,
        )

        for method in ("pearson", "spearman"):

            item = result[method]

            results.append({
                "hypothesis": name,
                "x": x,
                "y": y,
                "method": item["method"],
                "n_countries": result["n_countries"],
                "n_observations": result["n_observations"],
                "observed_r": item["observed_r"],
                "bootstrap_mean": item["bootstrap_mean"],
                "ci_lower_95": item["ci_lower"],
                "ci_upper_95": item["ci_upper"],
                "valid_iterations": item["valid_iterations"],
                "confidence_interval_excludes_zero": (
                    item["ci_lower"] > 0
                    or item["ci_upper"] < 0
                ),
            })

    report = pd.DataFrame(results)

    output_path = (
        OUTPUT_DIR / "cluster_bootstrap.csv"
    )

    report.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n=== CLUSTER BOOTSTRAP RESULTS ===")
    print(
        report.to_string(
            index=False,
            float_format=lambda x: f"{x:.4f}",
        )
    )

    logger.info(
        "Saved results to %s",
        output_path,
    )


if __name__ == "__main__":
    run_analysis()
