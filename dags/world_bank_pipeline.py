
import os
import csv
import logging
import subprocess

from datetime import datetime, timedelta, timezone
from pathlib import Path

from airflow.sdk import dag, task


PROJECT = Path("/opt/project")
PYTHON = "/opt/wb-venv/bin/python"
REPORTS = PROJECT / "reports" / "statistics"

logger = logging.getLogger(__name__)


def run_python(*args, extra_env=None):

    env = os.environ.copy()

    if extra_env:
        env.update(extra_env)

    result = subprocess.run(
        [PYTHON, "-u", *args],
        cwd=PROJECT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    print(result.stdout)

    if result.stderr:
        print(result.stderr)

    result.check_returncode()

    return result.stdout


@dag(
    dag_id="world_bank_pipeline",
    description="Automated World Bank analytics",
    start_date=datetime(
        2026, 11, 21, tzinfo=timezone.utc
    ),
    schedule="0 6 * * 1",
    catchup=False,
    max_active_runs=1,
    max_active_tasks=2,
    is_paused_upon_creation=True,
    default_args={
        "owner": "world_bank",
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=60),
    },
    tags=[
        "world-bank",
        "etl",
        "analytics",
        "diploma",
    ],
)
def world_bank_pipeline():

    @task
    def collect_data():

        output = run_python("collect_all.py")

        paths = [
            line.split("Output:", 1)[1].strip()
            for line in output.splitlines()
            if line.startswith("Output:")
        ]

        if not paths:
            raise RuntimeError(
                "Dataset path not found"
            )

        folder = Path(paths[-1]).resolve()

        if not folder.is_dir():
            raise FileNotFoundError(folder)

        print(f"Collected dataset: {folder}")

        return str(folder)


    @task
    def validate_data(dataset):

        folder = Path(dataset)

        required = [
            "countries.csv",
            "indicators.csv",
            "quality_report.csv",
            "quality_summary.json",
        ]

        for name in required:

            path = folder / name

            if not path.is_file():
                raise FileNotFoundError(path)

            if path.stat().st_size == 0:
                raise ValueError(f"Empty file: {name}")

        run_python(
            "-c",
            """
import sys
from pathlib import Path
import pandas as pd

from src.api.collector import load_config
from src.processing.quality import validate_indicators

folder = Path(sys.argv[1])

countries = pd.read_csv(folder / "countries.csv")
facts = pd.read_csv(folder / "indicators.csv")

if countries.empty or facts.empty:
    raise ValueError("Empty dataset")

if countries["country_id"].duplicated().any():
    raise ValueError("Duplicate countries")

if facts["is_aggregate"].fillna(True).any():
    raise ValueError("Unexpected aggregate")

validate_indicators(
    facts,
    expected_codes=[
        item["code"] for item in load_config()
    ],
    expected_countries=countries["country_id"].tolist(),
    start_year=2000,
    end_year=2025,
)

print("DATA QUALITY CHECK PASSED")
""",
            dataset,
        )

        return dataset


    @task
    def load_database(dataset):

        run_python(
            "load_database.py",
            extra_env={
                "WB_DATA_DIR": dataset
            },
        )

        print("DATABASE LOAD COMPLETED")


    @task
    
    @task
    def check_marts():

        run_python(
            "-c",
            '''
from sqlalchemy import text
from src.database.connection import get_engine

views = [
    "vw_country_ranking",
    "vw_gdp_dynamics",
    "vw_gdp_growth",
    "vw_gdp_per_capita",
    "vw_macro_indicators",
]

engine = get_engine()

try:
    with engine.connect() as conn:

        for view in views:

            rows = conn.execute(
                text(f"SELECT COUNT(*) FROM marts.{view}")
            ).scalar_one()

            if rows == 0:
                raise ValueError(f"Empty view: {view}")

            print(f"{view}: {rows} rows")

        duplicates = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM (
                    SELECT country_id, year
                    FROM marts.vw_macro_indicators
                    GROUP BY country_id, year
                    HAVING COUNT(*) > 1
                ) d
            """)
        ).scalar_one()

        if duplicates:
            raise ValueError("Duplicate country-year rows")

finally:
    engine.dispose()

print("ALL MARTS CHECKED")
''',
        )


    def run_analysis(module, filenames):

        before = {
            name: (
                (REPORTS / name).stat().st_mtime_ns
                if (REPORTS / name).exists()
                else None
            )
            for name in filenames
        }

        run_python("-m", module)

        for name in filenames:

            path = REPORTS / name

            if not path.is_file():
                raise FileNotFoundError(path)

            if path.stat().st_mtime_ns == before[name]:
                raise RuntimeError(
                    f"Report not updated: {name}"
                )

            with path.open(
                encoding="utf-8-sig", newline=""
            ) as file:
                rows = list(csv.DictReader(file))

            if not rows:
                raise RuntimeError(
                    f"Empty report: {name}"
                )

            if name == "regression_results.csv":
                if len(rows) != 4:
                    raise RuntimeError(
                        "Expected four regression models"
                    )

            print(f"Verified: {name}, rows={len(rows)}")


    @task
    def run_correlation():

        run_analysis(
            "src.analysis.correlation",
            [
                "correlations_by_year.csv",
                "correlations_first_differences.csv",
                "data_quality.csv",
            ],
        )


    @task
    def run_bootstrap():

        run_analysis(
            "src.analysis.bootstrap",
            ["cluster_bootstrap.csv"],
        )


    @task
    def run_regression():

        run_analysis(
            "src.analysis.regression",
            ["regression_results.csv"],
        )


    @task
    def run_group_analysis():

        run_analysis(
            "src.analysis.group_analysis",
            [
                "income_group_statistics.csv",
                "region_statistics.csv",
                "group_correlations.csv",
            ],
        )


    @task
    def run_trends():

        run_analysis(
            "src.analysis.trends",
            [
                "income_group_trends.csv",
                "region_trends.csv",
                "global_trends.csv",
                "long_term_changes.csv",
            ],
        )


    @task
    def verify_reports():

        required = [
            "correlations_by_year.csv",
            "correlations_first_differences.csv",
            "data_quality.csv",
            "cluster_bootstrap.csv",
            "regression_results.csv",
            "income_group_statistics.csv",
            "region_statistics.csv",
            "group_correlations.csv",
            "income_group_trends.csv",
            "region_trends.csv",
            "global_trends.csv",
            "long_term_changes.csv",
        ]

        for filename in required:

            path = REPORTS / filename

            if not path.is_file():
                raise FileNotFoundError(path)

            if path.stat().st_size == 0:
                raise ValueError(
                    f"Empty report: {filename}"
                )

            print(f"OK: {filename}")

        print(
            f"All {len(required)} reports verified"
        )


    @task
    def finish():

        logger.info(
            "WORLD BANK PIPELINE SUCCESS"
        )


    collected = collect_data()
    validated = validate_data(collected)
    loaded = load_database(validated)

    marts = check_marts()

    correlation = run_correlation()
    bootstrap = run_bootstrap()
    regression = run_regression()
    groups = run_group_analysis()
    trends = run_trends()

    verified = verify_reports()
    completed = finish()

    loaded >> marts

    marts >> [
        correlation,
        bootstrap,
        regression,
        groups,
        trends,
    ]

    [
        correlation,
        bootstrap,
        regression,
        groups,
        trends,
    ] >> verified >> completed


pipeline = world_bank_pipeline()
