from models import get_engine, init_db, get_session_factory

engine = get_engine()
init_db(engine)
SessionLocal = get_session_factory(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
