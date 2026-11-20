
import os

from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")


def get_engine():

    url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        database=os.environ["POSTGRES_DB"]
    )

    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10}
    )


def check_connection():

    engine = get_engine()

    try:
        with engine.connect() as conn:

            result = conn.execute(
                text("SELECT current_database(), current_user")
            )

            print(result.fetchone())
            print("DATABASE CONNECTION OK")

    finally:
        engine.dispose()


if __name__ == "__main__":
    check_connection()
