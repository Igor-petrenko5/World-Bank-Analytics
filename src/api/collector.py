
import json
import logging
import time

from pathlib import Path

import pandas as pd

from src.api.countries import fetch_countries
from src.api.indicators import fetch_indicator


logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


def load_config():

    path = ROOT / "config" / "indicators.json"

    with path.open(
        "r", encoding="utf-8-sig"
    ) as file:
        config = json.load(file)

    codes = [item["code"] for item in config]

    if len(codes) != len(set(codes)):
        raise ValueError("Duplicate indicator codes")

    if len(codes) != 20:
        raise ValueError("Expected 20 indicators")

    return config


def collect_all(start_year=2000, end_year=2025):

    config = load_config()

    countries = pd.DataFrame(fetch_countries())

    mapping_rows = countries[
        ["iso2_code", "country_id"]
    ].dropna()

    mapping_rows = mapping_rows[
        mapping_rows["iso2_code"].ne("")
    ]

    if mapping_rows["iso2_code"].duplicated().any():
        raise ValueError("Ambiguous country mapping")

    country_mapping = dict(zip(
        mapping_rows["iso2_code"],
        mapping_rows["country_id"]
    ))

    logger.info(
        "Country mapping created: %s codes",
        len(country_mapping)
    )

    frames = []

    for number, indicator in enumerate(config, 1):

        code = indicator["code"]

        logger.info(
            "Collecting %s/%s: %s",
            number,
            len(config),
            code
        )

        records = fetch_indicator(
            indicator_code=code,
            countries="all",
            start_year=start_year,
            end_year=end_year,
            country_mapping=country_mapping
        )

        if not records:
            raise ValueError(
                f"No records received: {code}"
            )

        frame = pd.DataFrame(records)

        frame["category"] = indicator["category"]
        frame["configured_unit"] = indicator["unit"]

        frames.append(frame)

        logger.info(
            "%s | Rows: %s | Missing: %s",
            code,
            len(frame),
            frame["value"].isna().sum()
        )

        time.sleep(1)

    indicators = pd.concat(
        frames, ignore_index=True
    )

    indicators = indicators.merge(
        countries[["country_id", "is_aggregate"]],
        on="country_id",
        how="left",
        validate="many_to_one"
    )

    if indicators["is_aggregate"].isna().any():

        unknown = indicators.loc[
            indicators["is_aggregate"].isna(),
            "country_id"
        ].unique()

        raise ValueError(
            f"Unknown country identifiers: {unknown}"
        )

    return countries, indicators
