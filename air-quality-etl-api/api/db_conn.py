import database
from functools import lru_cache
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

@lru_cache
def get_engine():
    """Create the shared engine lazily so imports do not require a live database."""
    return database.get_connection()

def get_db():
    session_local = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    db = session_local()
    try:
        yield db
    finally:
        db.close()
