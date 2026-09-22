import os
import logging

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

load_dotenv()


def get_connection() -> Engine:
    """Create a SQLAlchemy engine for the PostgreSQL database.

    Returns:
        sqlalchemy.engine.Engine: SQLAlchemy engine instance.
    """
    try:
        url = os.getenv("DATABASE_URL")
        if not url:
            required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
            values = {name: os.getenv(name) for name in required}
            missing = [name for name, value in values.items() if not value]
            if missing:
                raise ValueError(
                    "Database configuration is incomplete. Set DATABASE_URL or: "
                    + ", ".join(missing)
                )
            url = URL.create(
                drivername="postgresql+psycopg2",
                username=values["DB_USER"],
                password=values["DB_PASSWORD"],
                host=values["DB_HOST"],
                port=int(values["DB_PORT"]),
                database=values["DB_NAME"],
            )

        engine = create_engine(url, pool_pre_ping=True)

        logger.info("Database connection established successfully.")
        return engine

    except SQLAlchemyError as e:
        logger.critical(f"Failed to connect to the database: {e}")
        raise


def create_schema(conn: Connection) -> None:
    """Create the database schema if it doesn't exist.

    Args:
        conn: SQLAlchemy connection (expected to be within an active
            transaction, e.g. obtained via `engine.begin()` from the caller).

    Returns:
        None
    """
    try:
        with open("sql/schema.sql", "r", encoding="utf-8") as f:
            schema = f.read()

        conn.execute(text(schema))

        logger.info("Schema created successfully.")

    except SQLAlchemyError as e:
        logger.critical(f"Failed to create schema: {e}")
        raise
