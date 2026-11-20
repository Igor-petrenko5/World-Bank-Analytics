
import json
from pathlib import Path

import pandas as pd

rows = []

for path in Path("data/raw").glob("*.json"):

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    payload = data.get("payload")

    if not isinstance(payload, list):
        continue

    if len(payload) != 2:
        continue

    for record in payload[1] or []:

        if "indicator" not in record:
            continue

        country = record.get("country") or {}

        rows.append({
            "country_id": record.get("countryiso3code"),
            "country_code": country.get("id"),
            "country_name": country.get("value"),
            "indicator": record["indicator"]["id"],
            "year": record.get("date"),
            "value": record.get("value")
        })

df = pd.DataFrame(rows)

if df.empty:
    raise ValueError("No raw observations found")

missing = df[
    df["country_id"].isna()
    | df["country_id"].eq("")
]

print("Total raw rows:", len(df))
print("Missing country ID:", len(missing))

print("\n=== PROBLEMATIC COUNTRIES ===")

print(
    missing[
        ["country_code", "country_name"]
    ]
    .drop_duplicates()
    .to_string(index=False)
)

print("\n=== EXAMPLES ===")
print(missing.head(15).to_string(index=False))
