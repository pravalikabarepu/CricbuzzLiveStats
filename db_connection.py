
import os
import tempfile

import mysql.connector
import streamlit as st
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

load_dotenv()

_ssl_ca_path = None


def get_db_config():
    """Read Streamlit Cloud Secrets or local .env settings."""

    try:
        secrets = st.secrets["mysql"]

        return {
            "host": secrets["host"],
            "port": int(secrets["port"]),
            "user": secrets["user"],
            "password": secrets["password"],
            "database": secrets.get("database", "defaultdb"),
            "ssl_ca_content": secrets["ssl_ca"],
        }

    except Exception:
        # Local computer: use .env
        return {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "database": os.getenv(
                "DB_NAME", "cricbuzz_livestats"
            ),
            "ssl_ca_content": None,
        }


def get_ssl_ca_path(config):
    """Save the Aiven CA certificate to a temporary file."""
    global _ssl_ca_path

    certificate = config.get("ssl_ca_content")

    if not certificate:
        return None

    if _ssl_ca_path and os.path.exists(_ssl_ca_path):
        return _ssl_ca_path

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".pem",
        encoding="utf-8",
        delete=False,
    ) as cert_file:
        cert_file.write(certificate.strip() + "\n")
        _ssl_ca_path = cert_file.name

    return _ssl_ca_path


def get_connection():
    """Create a MySQL connection."""
    config = get_db_config()

    options = {
        "host": config["host"],
        "port": config["port"],
        "user": config["user"],
        "password": config["password"],
        "database": config["database"],
        "connection_timeout": 15,
    }

    ssl_ca = get_ssl_ca_path(config)

    if ssl_ca:
        options.update({
            "ssl_ca": ssl_ca,
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        })

    return mysql.connector.connect(**options)


def get_engine():
    """Create a SQLAlchemy engine."""
    config = get_db_config()

    url = URL.create(
        drivername="mysql+mysqlconnector",
        username=config["user"],
        password=config["password"],
        host=config["host"],
        port=config["port"],
        database=config["database"],
    )

    connect_args = {}
    ssl_ca = get_ssl_ca_path(config)

    if ssl_ca:
        connect_args.update({
            "ssl_ca": ssl_ca,
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        })

    return create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


if __name__ == "__main__":
    try:
        connection = get_connection()
        print("MySQL database connected successfully!")
        connection.close()

        engine = get_engine()
        with engine.connect() as connection:
            result = connection.exec_driver_sql("SELECT 1")
            print("Test query result:", result.scalar())

        engine.dispose()
        print("SQLAlchemy connection successful!")

    except Exception as error:
        print("Database connection failed:", error)
