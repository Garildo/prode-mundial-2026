import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./prode.db")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE matches ADD COLUMN IF NOT EXISTS penalty_home INTEGER"))
    conn.execute(text("ALTER TABLE matches ADD COLUMN IF NOT EXISTS penalty_away INTEGER"))
    conn.commit()
    print("OK: penalty_home y penalty_away agregados a matches")
