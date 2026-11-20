
import logging

from src.api.client import WorldBankAPI


logger = logging.getLogger(__name__)


def fetch_indicator(
    indicator_code,
    countries="all",
    start_year=2000,
    end_year=2025,
    country_mapping=None
):

    api = WorldBankAPI()

    country_mapping = country_mapping or {}

    endpoint = (
        f"country/{countries}/indicator/{indicator_code}"
    )

    metadata, records = api.get_all(
        endpoint,
        params={
            "date": f"{start_year}:{end_year}",
            "source": 2
        }
    )

    if str(metadata.get("sourceid")) != "2":
        raise ValueError("Unexpected data source")

    result = []
    restored_count = 0

    for item in records:

        country = item.get("country") or {}

        country_id = (
            item.get("countryiso3code") or ""
        ).strip()

        original_country_id = country_id

        if not country_id:

            short_code = country.get("id")

            country_id = country_mapping.get(short_code)

            if not country_id:
                raise ValueError(
                    f"Unknown country code: "
                    f"{short_code}, {country.get('value')}"
                )

            restored_count += 1

        record = {
            "country_id": country_id,
            "original_country_id": original_country_id,
            "country_short_code": country.get("id"),
            "country_name": country.get("value"),
            "indicator_code": item["indicator"]["id"],
            "indicator_name": item["indicator"]["value"],
            "year": int(item["date"]),
            "value": item["value"],
            "unit": item.get("unit"),
            "obs_status": item.get("obs_status"),
            "source_updated_at": metadata.get("lastupdated")
        }

        if record["indicator_code"] != indicator_code:
            raise ValueError("Unexpected indicator code")

        if not start_year <= record["year"] <= end_year:
            raise ValueError("Year outside requested interval")

        result.append(record)

    keys = [
        (r["country_id"], r["indicator_code"], r["year"])
        for r in result
    ]

    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate indicator records")

    logger.info(
        "%s | Restored identifiers: %s",
        indicator_code,
        restored_count
    )

    return result
