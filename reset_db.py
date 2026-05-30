"""
reset_db.py — Limpia toda la base de datos y recarga los partidos desde cero.
Borra usuarios, grupos, predicciones y partidos. Usar solo en desarrollo o reset inicial.

Uso local:   python reset_db.py
Uso Railway: railway run python reset_db.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, engine
from models import Base
import seed_matches

print("\nReset completo de base de datos")
print("=" * 45)

print("  Eliminando tablas...")
Base.metadata.drop_all(bind=engine)

print("  Recreando tablas...")
Base.metadata.create_all(bind=engine)

print("  Cargando partidos...")
seed_matches.seed()

print("\n  Base de datos lista para comenzar.")
