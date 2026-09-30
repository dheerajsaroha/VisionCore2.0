from sqlalchemy import text
from app.db.database import engine
from app.db.models.base import Base
import app.db.models.all_models  # Ensure all models are loaded

def create_tables():
    # Extensions must be committed before tables that use uuid_generate_v4(),
    # gen_random_bytes(), and vector columns are created.
    try:
        with engine.begin() as conn:
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto";'))
            conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector";'))
            print("PostgreSQL extensions enabled.")
    except Exception as e:
        print(f"Warning: Could not enable extensions automatically (probably permissions). Ensure they are enabled manually. {e}")

    Base.metadata.create_all(bind=engine)

    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_face_embeddings_hnsw 
                ON face_embeddings 
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64);
            """))
            print("HNSW index enabled.")
    except Exception as e:
        print(f"Warning: Could not create HNSW index automatically. Ensure it is enabled manually. {e}")

    _load_business_calendar()


def _load_business_calendar():
    """
    Populate the working-day calendar from the database.

    The calendar service keeps its holidays in process memory, so without this
    every holiday created through the API disappeared on restart and was
    invisible to any other worker.
    """
    try:
        from sqlalchemy.orm import sessionmaker

        from app.services.business_calendar_service import business_calendar_service

        session = sessionmaker(bind=engine)()
        try:
            business_calendar_service.load_from_db(session)
        finally:
            session.close()
    except Exception as e:
        print(f"Warning: Could not load holiday calendars. {e}")
