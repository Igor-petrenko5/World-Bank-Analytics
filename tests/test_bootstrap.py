
import numpy as np
import pandas as pd
import pytest

from src.analysis.bootstrap import (
    calculate_correlations,
    cluster_bootstrap,
)


def test_perfect_positive_correlation():
    df = pd.DataFrame({
        "x": [1, 2, 3, 4, 5],
        "y": [2, 4, 6, 8, 10],
    })

    result = calculate_correlations(df, "x", "y")

    assert result["pearson_r"] == pytest.approx(1.0)
    assert result["spearman_r"] == pytest.approx(1.0)


def test_missing_values_are_excluded():
    df = pd.DataFrame({
        "x": [1, 2, np.nan, 4, 5],
        "y": [2, 4, 6, np.nan, 10],
    })

    result = calculate_correlations(df, "x", "y")

    assert result["n_observations"] == 3


def test_constant_column_returns_none():
    df = pd.DataFrame({
        "x": [1, 1, 1, 1],
        "y": [2, 3, 4, 5],
    })

    result = calculate_correlations(df, "x", "y")

    assert result is None


def test_missing_columns_raise_error():
    df = pd.DataFrame({
        "country_id": ["A", "B"],
        "x": [1, 2],
    })

    with pytest.raises(ValueError):
        cluster_bootstrap(
            df,
            "x",
            "y",
            n_bootstrap=100,
        )


def test_bootstrap_is_reproducible():

    rows = []

    for country in range(20):
        for year in range(5):
            x = country + year
            rows.append({
                "country_id": str(country),
                "x": x,
                "y": 2 * x + country * 0.1,
            })

    df = pd.DataFrame(rows)

    first = cluster_bootstrap(
        df, "x", "y",
        n_bootstrap=100,
        random_state=42,
    )

    second = cluster_bootstrap(
        df, "x", "y",
        n_bootstrap=100,
        random_state=42,
    )

    assert first["pearson"]["ci_lower"] == pytest.approx(
        second["pearson"]["ci_lower"]
    )

    assert first["pearson"]["valid_iterations"] == 100


def test_too_few_countries_raise_error():

    df = pd.DataFrame({
        "country_id": ["A", "B", "C"],
        "x": [1, 2, 3],
        "y": [2, 4, 6],
    })

    with pytest.raises(ValueError):
        cluster_bootstrap(
            df,
            "x",
            "y",
            n_bootstrap=100,
        )
