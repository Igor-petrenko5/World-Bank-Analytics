
import json
import logging

from datetime import datetime, timezone
from pathlib import Path

from src.api.collector import collect_all, load_config
from src.processing.quality import (
    validate_indicators,
    build_quality_report
)


ROOT = Path(__file__).resolve().parent

(ROOT / "logs").mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            ROOT / "logs" / "collection.log",
            encoding="utf-8"
        )
    ]
)


def main():

    start_year = 2000
    end_year = 2025

    run_id = datetime.now(
        timezone.utc
    ).strftime("%Y%m%d_%H%M%S_%f")

    countries, indicators = collect_all(
        start_year=start_year,
        end_year=end_year
    )

    economies = countries.loc[
        ~countries["is_aggregate"]
    ].copy()

    facts = indicators.loc[
        ~indicators["is_aggregate"]
    ].copy()

    codes = [
        item["code"] for item in load_config()
    ]

    quality = validate_indicators(
        facts,
        expected_codes=codes,
        expected_countries=(
            economies["country_id"].tolist()
        ),
        start_year=start_year,
        end_year=end_year
    )

    report = build_quality_report(facts)

    output = ROOT / "data" / "processed" / run_id

    output.mkdir(
        parents=True,
        exist_ok=False
    )

    datasets = {
        "countries": economies,
        "countries_all": countries,
        "indicators": facts,
        "indicators_all": indicators,
        "quality_report": report
    }

    for name, frame in datasets.items():

        frame.to_csv(
            output / f"{name}.csv",
            index=False,
            encoding="utf-8-sig"
        )

    with (output / "quality_summary.json").open(
        "w", encoding="utf-8"
    ) as file:
        json.dump(
            quality,
            file,
            indent=2
        )

    print("\n=== COLLECTION SUMMARY ===")
    print("Countries:", len(economies))
    print("Indicators:", facts["indicator_code"].nunique())

    print(json.dumps(quality, indent=2))

    print("\n=== QUALITY BY INDICATOR ===")

    print(
        report[
            [
                "indicator_code",
                "filled_rows",
                "missing_rows",
                "completeness_pct"
            ]
        ].to_string(index=False)
    )

    print("\nOutput:", output)
    print("FULL COLLECTION OK")


if __name__ == "__main__":
    main()
