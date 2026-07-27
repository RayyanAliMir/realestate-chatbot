import os

from models import get_engine, init_db, get_session_factory

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./realestate_chatbot.db")
if DATABASE_URL.startswith("postgres://"):
    # Some providers (Railway included, historically) hand out the old `postgres://`
    # scheme, which SQLAlchemy 1.4+ no longer accepts.
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = get_engine(DATABASE_URL)
init_db(engine)
SessionLocal = get_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
