
from src.api.client import WorldBankAPI


def fetch_countries():

    api = WorldBankAPI()

    metadata, records = api.get_all("country")

    countries = []

    for item in records:

        region = item.get("region") or {}
        income = item.get("incomeLevel") or {}

        country = {
            "country_id": item["id"],
            "iso2_code": item.get("iso2Code"),
            "country_name": item["name"],
            "region_id": region.get("id"),
            "region_name": region.get("value", "").strip(),
            "income_level": income.get("value"),
            "capital_city": item.get("capitalCity"),
            "latitude": item.get("latitude"),
            "longitude": item.get("longitude"),
            "is_aggregate": (
                region.get("value", "").strip().lower()
                == "aggregates"
            )
        }

        countries.append(country)

    ids = [country["country_id"] for country in countries]

    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate country identifiers")

    return countries
