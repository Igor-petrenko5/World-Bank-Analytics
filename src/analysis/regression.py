
import logging

import numpy as np
import pandas as pd
from linearmodels.panel import PanelOLS
from sqlalchemy import text

from src.database.connection import get_engine


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def prepare_panel(
    df,
    dependent,
    independent,
    transform=None,
):
    required = [
        "country_id",
        "year",
        dependent,
        independent,
    ]

    missing = set(required) - set(df.columns)

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    data = df[required].copy()

    if data.duplicated(["country_id", "year"]).any():
        raise ValueError("Duplicate country-year observations")

    data[dependent] = pd.to_numeric(
        data[dependent], errors="coerce"
    )

    data[independent] = pd.to_numeric(
        data[independent], errors="coerce"
    )

    data = data.replace(
        [np.inf, -np.inf], np.nan
    )

    data = data.dropna(
        subset=[dependent, independent]
    )

    if transform == "log":
        if (data[independent] <= 0).any():
            raise ValueError(
                "Log transformation requires positive values"
            )

        data[independent] = np.log(
            data[independent]
        )

    elif transform is not None:
        raise ValueError("Unknown transformation")

    if len(data) == 0:
        raise ValueError("No valid observations")

    if data["country_id"].nunique() < 2:
        raise ValueError("At least two countries required")

    if data["year"].nunique() < 2:
        raise ValueError("At least two years required")

    data["year"] = data["year"].astype(int)

    return data.set_index(
        ["country_id", "year"]
    ).sort_index()


def fit_panel_model(
    df,
    dependent,
    independent,
    transform=None,
):
    panel = prepare_panel(
        df,
        dependent,
        independent,
        transform,
    )

    model = PanelOLS(
        panel[dependent],
        panel[[independent]],
        entity_effects=True,
        time_effects=True,
        drop_absorbed=True,
    )

    result = model.fit(
        cov_type="clustered",
        cluster_entity=True,
    )

    if independent not in result.params.index:
        raise ValueError(
            "Independent variable was absorbed by fixed effects"
        )

    coefficient = float(
        result.params[independent]
    )

    std_error = float(
        result.std_errors[independent]
    )

    confidence = result.conf_int().loc[independent]

    return {
        "coefficient": coefficient,
        "std_error": std_error,
        "p_value": float(result.pvalues[independent]),
        "ci_lower": float(confidence.iloc[0]),
        "ci_upper": float(confidence.iloc[1]),
        "r_squared": float(result.rsquared_within),
        "n_observations": int(result.nobs),
        "n_countries": int(
            panel.index.get_level_values("country_id").nunique()
        ),
        "n_years": int(
            panel.index.get_level_values("year").nunique()
        ),
        "country_effects": True,
        "year_effects": True,
    }


def load_data():
    query = text("""
        SELECT
            country_id,
            year,
            gdp_growth_pct,
            unemployment_pct,
            inflation_pct,
            gdp_per_capita_usd,
            life_expectancy,
            health_expenditure_pct_gdp
        FROM marts.vw_macro_indicators
        WHERE year BETWEEN 2000 AND 2023
    """)

    engine = get_engine()

    try:
        with engine.connect() as connection:
            return pd.read_sql(query, connection)
    finally:
        engine.dispose()


def run_analysis():

    df = load_data()

    models = [
        ("R1_GDP_Unemployment",
         "gdp_growth_pct", "unemployment_pct", None),

        ("R2_Inflation_GDP",
         "gdp_growth_pct", "inflation_pct", None),

        ("R3_Income_Life",
         "life_expectancy", "gdp_per_capita_usd", "log"),

        ("R4_Health_Life",
         "life_expectancy", "health_expenditure_pct_gdp", None),
    ]

    results = []

    for name, dependent, independent, transform in models:

        logger.info("Running model: %s", name)

        try:
            result = fit_panel_model(
                df,
                dependent,
                independent,
                transform,
            )

            result["model"] = name
            result["dependent"] = dependent
            result["independent"] = independent

            results.append(result)

            logger.info(
                "%s | coef=%.4f | p=%.4f | N=%d",
                name,
                result["coefficient"],
                result["p_value"],
                result["n_observations"],
            )

        except Exception:
            logger.exception("Model failed: %s", name)

    if not results:
        raise RuntimeError("All regression models failed")

    report = pd.DataFrame(results)

    from pathlib import Path

    output = (
        Path(__file__).resolve().parents[2]
        / "reports"
        / "statistics"
    )

    output.mkdir(parents=True, exist_ok=True)

    report.to_csv(
        output / "regression_results.csv",
        index=False,
        encoding="utf-8-sig",
    )

    logger.info("Results saved: %s", output)

    print("\n=== REGRESSION RESULTS ===")
    print(report.to_string(index=False))

    return report


if __name__ == "__main__":
    run_analysis()
