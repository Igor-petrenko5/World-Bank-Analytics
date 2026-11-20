
import numpy as np
import pandas as pd
import pytest

from src.analysis.regression import (
    prepare_panel,
    fit_panel_model,
)


def make_panel():

    rng = np.random.default_rng(42)
    rows = []

    for country in range(25):

        country_effect = country * 0.3

        for year in range(2000, 2010):

            x = (
                country * 0.5
                + (year - 2000) * 0.8
                + rng.normal(0, 0.5)
            )

            y = (
                0.6 * x
                + country_effect
                + (year - 2000) * 0.2
                + rng.normal(0, 0.3)
            )

            rows.append({
                "country_id": str(country),
                "year": year,
                "x": x,
                "y": y,
            })

    return pd.DataFrame(rows)


def test_prepare_panel():

    df = make_panel()

    result = prepare_panel(
        df, "y", "x"
    )

    assert len(result) == 250
    assert result.index.names == [
        "country_id", "year"
    ]


def test_missing_values_are_removed():

    df = make_panel()

    df.loc[0, "x"] = np.nan

    result = prepare_panel(
        df, "y", "x"
    )

    assert len(result) == 249


def test_duplicate_country_year_raises():

    df = make_panel()

    df = pd.concat(
        [df, df.iloc[[0]]],
        ignore_index=True,
    )

    with pytest.raises(ValueError):
        prepare_panel(df, "y", "x")


def test_log_transform():

    df = make_panel()

    df["x"] = np.exp(
        df["x"] / 10 + 2
    )

    result = prepare_panel(
        df,
        "y",
        "x",
        transform="log",
    )

    assert np.isfinite(result["x"]).all()


def test_non_positive_log_value_raises():

    df = make_panel()

    df.loc[0, "x"] = 0

    with pytest.raises(ValueError):
        prepare_panel(
            df,
            "y",
            "x",
            transform="log",
        )


def test_fixed_effects_regression():

    df = make_panel()

    result = fit_panel_model(
        df,
        "y",
        "x",
    )

    assert np.isfinite(result["coefficient"])
    assert np.isfinite(result["std_error"])
    assert result["std_error"] > 0

    assert result["n_observations"] == 250
    assert result["n_countries"] == 25
    assert result["n_years"] == 10

    assert result["country_effects"] is True
    assert result["year_effects"] is True

    assert result["ci_lower"] <= result["ci_upper"]
