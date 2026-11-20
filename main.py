
import logging
from pathlib import Path

import pandas as pd

from src.api.countries import fetch_countries
from src.api.indicators import fetch_indicator


ROOT = Path(__file__).resolve().parent

(ROOT / "logs").mkdir(exist_ok=True)
(ROOT / "data" / "processed").mkdir(
    parents=True, exist_ok=True
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            ROOT / "logs" / "api.log",
            encoding="utf-8"
        )
    ]
)


def main():

    countries = fetch_countries()
    df_countries = pd.DataFrame(countries)

    indicators = fetch_indicator(
        indicator_code="NY.GDP.MKTP.CD",
        countries="USA;RUS;CHN;DEU;BRA",
        start_year=2000,
        end_year=2025
    )

    df_indicators = pd.DataFrame(indicators)

    df_countries.to_csv(
        ROOT / "data/processed/countries.csv",
        index=False,
        encoding="utf-8-sig"
    )

    df_indicators.to_csv(
        ROOT / "data/processed/indicators.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("\n=== COUNTRIES ===")
    print("Total:", len(df_countries))
    print(
        "Aggregates:",
        df_countries["is_aggregate"].sum()
    )

    print("\n=== INDICATORS ===")
    print("Total:", len(df_indicators))
    print(
        "Missing values:",
        df_indicators["value"].isna().sum()
    )
    print(df_indicators.head(10).to_string(index=False))

    print("\nCOLLECTION OK")


if __name__ == "__main__":
    main()
