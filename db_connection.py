
import os

import mysql.connector
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


def get_db_config():
    """Read database settings from environment variables."""
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "cricbuzz_livestats"),
        "port": int(os.getenv("DB_PORT", "3306")),
    }


def get_connection():
    """Create a MySQL Connector connection."""
    return mysql.connector.connect(**get_db_config())


def get_engine():
    """Create a SQLAlchemy engine for pandas and Streamlit."""
    config = get_db_config()

    url = URL.create(
        drivername="mysql+mysqlconnector",
        username=config["user"],
        password=config["password"],
        host=config["host"],
        port=config["port"],
        database=config["database"],
    )

    return create_engine(url, pool_pre_ping=True)


if __name__ == "__main__":
    try:
        connection = get_connection()
        print("MySQL database connected successfully!")
        connection.close()

        engine = get_engine()
        with engine.connect() as connection:
            connection.exec_driver_sql("SELECT 1")

        print("SQLAlchemy connection successful!")
        engine.dispose()

    except Exception as error:
        print("Database connection failed:", error)
