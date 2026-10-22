



import os

import mysql.connector
from sqlalchemy import create_engine
from sqlalchemy.engine import URL


# Database settings
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "223705@Josh",  # Replace with your actual MySQL password
    "database": "cricbuzz_livestats",
    "port": 3306,
}


def get_connection():
    """Create a MySQL Connector connection."""
    connection = mysql.connector.connect(**DB_CONFIG)
    return connection


def get_engine():
    """Create a SQLAlchemy engine for pandas and Streamlit."""
    url = URL.create(
        drivername="mysql+mysqlconnector",
        username=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
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


