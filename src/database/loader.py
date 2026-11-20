
import logging
import uuid

import pandas as pd

from sqlalchemy import text

from src.database.connection import get_engine


logger = logging.getLogger(__name__)

DATA_DIR = "data/processed/20261120_124250_149508"

BATCH_SIZE = 5000


def clean_records(df):
    """Convert pandas missing values to Python None."""
    return (
        df.astype(object)
        .where(pd.notna(df), None)
        .to_dict(orient="records")
    )


def execute_batches(conn, query, records):
    """Execute bulk inserts in manageable batches."""

    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start:start + BATCH_SIZE]
        conn.execute(text(query), batch)


def load_database():

    engine = get_engine()
    run_id = str(uuid.uuid4())

    try:

        logger.info("Starting database loading: %s", run_id)

        countries = pd.read_csv(
            f"{DATA_DIR}/countries.csv"
        )

        indicators = pd.read_csv(
            f"{DATA_DIR}/indicators.csv"
        )

        quality = pd.read_csv(
            f"{DATA_DIR}/quality_report.csv"
        )

        # 1. Basic validation

        if countries.empty or indicators.empty:
            raise ValueError("Empty input dataset")

        if countries["country_id"].duplicated().any():
            raise ValueError("Duplicate country IDs")

        if indicators.duplicated(
            ["country_id", "indicator_code", "year"]
        ).any():
            raise ValueError("Duplicate indicator observations")

        if indicators["is_aggregate"].fillna(True).any():
            raise ValueError(
                "Unexpected aggregate in indicators.csv"
            )

        if indicators["value"].notna().sum() == 0:
            raise ValueError("No valid numeric observations")

        if not indicators["year"].between(2000, 2025).all():
            raise ValueError("Invalid year range")

        # 2. Prepare dimension tables

        country_columns = [
            "country_id",
            "iso2_code",
            "country_name",
            "region_id",
            "region_name",
            "income_level",
            "capital_city",
            "latitude",
            "longitude",
            "is_aggregate"
        ]

        indicator_columns = [
            "indicator_code",
            "indicator_name",
            "category",
            "configured_unit"
        ]

        country_data = countries[country_columns].copy()

        indicator_data = (
            indicators[indicator_columns]
            .drop_duplicates("indicator_code")
            .rename(columns={"configured_unit": "unit"})
            .copy()
        )

        if indicator_data["indicator_code"].nunique() != 20:
            raise ValueError("Expected exactly 20 indicators")

        if indicator_data["unit"].isna().any():
            raise ValueError("Missing indicator units")

        # 3. Prepare fact table

        facts = indicators[
            [
                "country_id",
                "indicator_code",
                "year",
                "value",
                "obs_status",
                "source_updated_at"
            ]
        ].copy()

        facts["source_id"] = 2

        facts["year"] = facts["year"].astype(int)

        facts["value"] = pd.to_numeric(
            facts["value"],
            errors="raise"
        )

        facts["source_updated_at"] = pd.to_datetime(
            facts["source_updated_at"],
            errors="coerce"
        ).dt.date

        facts = facts[
            [
                "country_id",
                "indicator_code",
                "year",
                "source_id",
                "value",
                "obs_status",
                "source_updated_at"
            ]
        ]

        # 4. Begin transaction

        with engine.begin() as conn:

            conn.execute(
                text("""
                    INSERT INTO monitoring.etl_runs (
                        run_id, status, total_rows
                    )
                    VALUES (
                        :run_id, 'RUNNING', :total_rows
                    )
                """),
                {
                    "run_id": run_id,
                    "total_rows": len(facts)
                }
            )

            # Countries

            country_query = """
                INSERT INTO warehouse.dim_countries (
                    country_id, iso2_code, country_name,
                    region_id, region_name, income_level,
                    capital_city, latitude, longitude,
                    is_aggregate
                )
                VALUES (
                    :country_id, :iso2_code, :country_name,
                    :region_id, :region_name, :income_level,
                    :capital_city, :latitude, :longitude,
                    :is_aggregate
                )
                ON CONFLICT (country_id)
                DO UPDATE SET
                    iso2_code = EXCLUDED.iso2_code,
                    country_name = EXCLUDED.country_name,
                    region_id = EXCLUDED.region_id,
                    region_name = EXCLUDED.region_name,
                    income_level = EXCLUDED.income_level,
                    capital_city = EXCLUDED.capital_city,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    is_aggregate = EXCLUDED.is_aggregate
            """

            execute_batches(
                conn,
                country_query,
                clean_records(country_data)
            )

            # Indicators

            indicator_query = """
                INSERT INTO warehouse.dim_indicators (
                    indicator_code, indicator_name,
                    category, unit
                )
                VALUES (
                    :indicator_code, :indicator_name,
                    :category, :unit
                )
                ON CONFLICT (indicator_code)
                DO UPDATE SET
                    indicator_name = EXCLUDED.indicator_name,
                    category = EXCLUDED.category,
                    unit = EXCLUDED.unit
            """

            execute_batches(
                conn,
                indicator_query,
                clean_records(indicator_data)
            )

            # Temporary staging table

            conn.execute(text("""
                CREATE TEMP TABLE stg_fact_indicators (
                    country_id VARCHAR(10),
                    indicator_code VARCHAR(50),
                    year SMALLINT,
                    source_id INTEGER,
                    value NUMERIC,
                    obs_status TEXT,
                    source_updated_at DATE
                ) ON COMMIT DROP
            """))

            facts.to_sql(
                "stg_fact_indicators",
                con=conn,
                if_exists="append",
                index=False,
                chunksize=BATCH_SIZE,
                method="multi"
            )

            # Record changed values before upsert

            conn.execute(text("""
                INSERT INTO warehouse.fact_indicator_history (
                    country_id,
                    indicator_code,
                    year,
                    source_id,
                    old_value,
                    new_value,
                    source_updated_at,
                    run_id
                )
                SELECT
                    old.country_id,
                    old.indicator_code,
                    old.year,
                    old.source_id,
                    old.value,
                    new.value,
                    new.source_updated_at,
                    :run_id
                FROM warehouse.fact_indicators old
                JOIN stg_fact_indicators new
                  ON old.country_id = new.country_id
                 AND old.indicator_code = new.indicator_code
                 AND old.year = new.year
                 AND old.source_id = new.source_id
                WHERE old.value IS DISTINCT FROM new.value
            """), {"run_id": run_id})

            # Insert or update facts

            conn.execute(text("""
                INSERT INTO warehouse.fact_indicators (
                    country_id,
                    indicator_code,
                    year,
                    source_id,
                    value,
                    obs_status,
                    source_updated_at,
                    run_id
                )
                SELECT
                    country_id,
                    indicator_code,
                    year,
                    source_id,
                    value,
                    obs_status,
                    source_updated_at,
                    :run_id
                FROM stg_fact_indicators

                ON CONFLICT (
                    country_id,
                    indicator_code,
                    year,
                    source_id
                )
                DO UPDATE SET
                    value = EXCLUDED.value,
                    obs_status = EXCLUDED.obs_status,
                    source_updated_at = EXCLUDED.source_updated_at,
                    loaded_at = NOW(),
                    run_id = EXCLUDED.run_id
            """), {"run_id": run_id})

            # Save quality report

            quality_checks = []

            for _, row in quality.iterrows():

                quality_checks.append({
                    "run_id": run_id,
                    "check_name": (
                        f"completeness_{row['indicator_code']}"
                    ),
                    "status": "PASS",
                    "actual_value": float(
                        row["completeness_pct"]
                    ),
                    "expected_value": 0,
                    "details": (
                        f"Missing: {int(row['missing_rows'])}; "
                        f"Total: {int(row['total_rows'])}"
                    )
                })

            execute_batches(
                conn,
                """
                INSERT INTO monitoring.quality_checks (
                    run_id, check_name, status,
                    actual_value, expected_value, details
                )
                VALUES (
                    :run_id, :check_name, :status,
                    :actual_value, :expected_value, :details
                )
                """,
                quality_checks
            )

            # Finish ETL run

            conn.execute(text("""
                UPDATE monitoring.etl_runs
                SET status = 'SUCCESS',
                    finished_at = NOW()
                WHERE run_id = :run_id
            """), {"run_id": run_id})

        logger.info("Database loading completed successfully")

        print("\n=== DATABASE LOAD SUMMARY ===")
        print("Run ID:", run_id)
        print("Countries:", len(country_data))
        print("Indicators:", len(indicator_data))
        print("Fact rows:", len(facts))
        print("Quality checks:", len(quality_checks))
        print("Status: SUCCESS")

    except Exception as error:

        logger.exception("Database loading failed")

        try:
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO monitoring.etl_runs (
                        run_id, status, error_message, finished_at
                    )
                    VALUES (
                        :run_id, 'FAILED', :error, NOW()
                    )
                """), {
                    "run_id": run_id,
                    "error": str(error)[:4000]
                })

        except Exception:
            logger.exception("Could not save failed ETL run")

        raise

    finally:
        engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    load_database()
