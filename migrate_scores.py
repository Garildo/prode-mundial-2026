"""
Migración: sistema de scores (goles) para pronósticos.

Qué hace:
  1. Agrega columnas predicted_home, predicted_away, is_exact a predictions
  2. Elimina predicciones de partidos no finalizados (para re-pronosticar con scores)

Uso local:
  python migrate_scores.py

Uso producción (bash):
  DATABASE_URL="postgresql://..." python migrate_scores.py
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL no configurada")
    exit(1)

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text("ALTER TABLE predictions ADD COLUMN IF NOT EXISTS predicted_home INTEGER"))
    conn.execute(text("ALTER TABLE predictions ADD COLUMN IF NOT EXISTS predicted_away INTEGER"))
    conn.execute(text("ALTER TABLE predictions ADD COLUMN IF NOT EXISTS is_exact BOOLEAN"))

    result = conn.execute(text("""
        DELETE FROM predictions
        WHERE match_id IN (
            SELECT id FROM matches WHERE status != 'FINISHED'
        )
    """))
    deleted = result.rowcount

    conn.commit()

print(f"OK — columnas agregadas, {deleted} predicciones futuras eliminadas.")
