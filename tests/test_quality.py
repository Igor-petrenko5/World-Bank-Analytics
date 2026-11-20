
import pandas as pd
import pytest

from src.processing.quality import validate_indicators


@pytest.fixture
def sample():

    return pd.DataFrame({
        "country_id": ["USA", "USA"],
        "indicator_code": ["GDP", "GDP"],
        "year": [2020, 2021],
        "value": [100.0, 110.0]
    })


def validate(df):

    return validate_indicators(
        df,
        ["GDP"],
        ["USA"],
        2020,
        2021
    )


def test_valid_data(sample):
    assert validate(sample)["status"] == "PASS"


def test_duplicates(sample):

    duplicate = pd.concat(
        [sample, sample.iloc[[0]]]
    )

    with pytest.raises(ValueError):
        validate(duplicate)


def test_missing_observation(sample):

    with pytest.raises(ValueError):
        validate(sample.iloc[[0]])


def test_missing_value_allowed(sample):

    sample.loc[0, "value"] = None

    result = validate(sample)

    assert result["missing_values"] == 1
    assert result["completeness_pct"] == 50.0


def test_invalid_year(sample):

    sample.loc[0, "year"] = 1999

    with pytest.raises(ValueError):
        validate(sample)


def test_infinite_value(sample):

    sample.loc[0, "value"] = float("inf")

    with pytest.raises(ValueError):
        validate(sample)
