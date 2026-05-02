import os

import psycopg2
from dotenv import dotenv_values, load_dotenv
from psycopg2 import OperationalError


def get_connection_params() -> dict:
    """Build PostgreSQL connection settings from environment variables."""
    return {
        "host": os.getenv("PGHOST", "localhost"),
        "port": int(os.getenv("PGPORT", "5432")),
        "dbname": os.getenv("PGDATABASE", "booking"),
        "user": os.getenv("PGUSER", "postgres"),
        "password": os.getenv("PGPASSWORD", ""),
    }


def test_connection() -> None:
    params = get_connection_params()

    print("Trying to connect to PostgreSQL...")
    print(
        f"host={params['host']}, port={params['port']}, "
        f"database={params['dbname']}, user={params['user']}"
    )

    try:
        with psycopg2.connect(**params) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]

        print("Connection successful!")
        print(f"PostgreSQL version: {version}")
    except OperationalError as err:
        print("Connection failed.")
        print(f"Error: {err}")


if __name__ == "__main__":
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    load_dotenv(env_path, override=True)
    for key, value in dotenv_values(env_path).items():
        if value is not None:
            os.environ[key] = value
    test_connection()
