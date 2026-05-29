"""
seed_matches.py — Carga todos los partidos de la Fase de Grupos del Mundial 2026.
Fuente de grupos: Sorteo oficial FIFA, 6 de diciembre de 2025.
Fechas/horas: aproximadas (en UTC). Usar Sync API para datos exactos.

Uso:  python seed_matches.py
      python seed_matches.py --clear   (borra y recarga desde cero)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from database import SessionLocal, engine
from models import Base, Match
import football_api

Base.metadata.create_all(bind=engine)

# ── 12 Grupos, 4 equipos cada uno ─────────────────────────────────────────────
GROUPS: dict[str, list[str]] = {
    "GRUPO_A": ["Mexico",          "South Korea",   "South Africa",          "Czechia"],
    "GRUPO_B": ["Canada",          "Switzerland",   "Qatar",                 "Bosnia and Herzegovina"],
    "GRUPO_C": ["Brazil",          "Morocco",       "Scotland",              "Haiti"],
    "GRUPO_D": ["United States",   "Turkey",        "Australia",             "Paraguay"],
    "GRUPO_E": ["Germany",         "Ecuador",       "Ivory Coast",           "Curacao"],
    "GRUPO_F": ["Netherlands",     "Japan",         "Sweden",                "Tunisia"],
    "GRUPO_G": ["Belgium",         "Iran",          "Egypt",                 "New Zealand"],
    "GRUPO_H": ["Spain",           "Uruguay",       "Saudi Arabia",          "Cape Verde"],
    "GRUPO_I": ["France",          "Senegal",       "Norway",                "Iraq"],
    "GRUPO_J": ["Argentina",       "Austria",       "Algeria",               "Jordan"],
    "GRUPO_K": ["Portugal",        "Colombia",      "DR Congo",              "Uzbekistan"],
    "GRUPO_L": ["England",         "Croatia",       "Ghana",                 "Panama"],
}

# ── Fechas de cada jornada por grupo (UTC) ─────────────────────────────────────
# Cada grupo tiene 3 jornadas: (fecha, hora_UTC)
# Jornada 3 los dos partidos son simultáneos
GROUP_SCHEDULE: dict[str, list[tuple[str, str]]] = {
    "GRUPO_A": [("2026-06-11", "18:00"), ("2026-06-15", "21:00"), ("2026-06-24", "21:00")],
    "GRUPO_B": [("2026-06-12", "15:00"), ("2026-06-16", "18:00"), ("2026-06-25", "15:00")],
    "GRUPO_C": [("2026-06-12", "21:00"), ("2026-06-17", "15:00"), ("2026-06-25", "21:00")],
    "GRUPO_D": [("2026-06-13", "18:00"), ("2026-06-17", "21:00"), ("2026-06-26", "15:00")],
    "GRUPO_E": [("2026-06-13", "21:00"), ("2026-06-18", "18:00"), ("2026-06-26", "21:00")],
    "GRUPO_F": [("2026-06-14", "15:00"), ("2026-06-18", "21:00"), ("2026-06-27", "15:00")],
    "GRUPO_G": [("2026-06-14", "21:00"), ("2026-06-19", "15:00"), ("2026-06-27", "21:00")],
    "GRUPO_H": [("2026-06-15", "00:00"), ("2026-06-19", "21:00"), ("2026-06-27", "18:00")],
    "GRUPO_I": [("2026-06-15", "18:00"), ("2026-06-20", "15:00"), ("2026-06-26", "18:00")],
    "GRUPO_J": [("2026-06-16", "00:00"), ("2026-06-20", "21:00"), ("2026-06-24", "18:00")],
    "GRUPO_K": [("2026-06-16", "18:00"), ("2026-06-21", "15:00"), ("2026-06-25", "18:00")],
    "GRUPO_L": [("2026-06-17", "00:00"), ("2026-06-21", "21:00"), ("2026-06-24", "15:00")],
}


def build_matches(group: str, teams: list[str], schedule: list[tuple[str, str]]) -> list[dict]:
    """
    4 equipos → 6 partidos (todos contra todos).
    Distribución por jornada:
      J1: T0-T1, T2-T3
      J2: T0-T2, T1-T3
      J3: T0-T3, T1-T2  (simultáneos)
    """
    t = teams
    jornadas = [
        [(t[0], t[1]), (t[2], t[3])],
        [(t[0], t[2]), (t[1], t[3])],
        [(t[0], t[3]), (t[1], t[2])],
    ]

    matches = []
    for j_idx, (date_str, time_str) in enumerate(schedule):
        for offset, (home, away) in enumerate(jornadas[j_idx]):
            dt_str = f"{date_str}T{time_str}:00"
            # Segundo partido de cada jornada: 3 horas después
            if offset == 1:
                h, m = int(time_str[:2]), int(time_str[3:])
                h = (h + 3) % 24
                dt_str = f"{date_str}T{h:02d}:{m:02d}:00"
            matches.append({
                "home": home,
                "away": away,
                "date": datetime.fromisoformat(dt_str),
                "stage": group,
            })
    return matches


def seed(clear: bool = False):
    db = SessionLocal()
    try:
        if clear:
            deleted = db.query(Match).filter(Match.api_id.is_(None)).delete()
            db.commit()
            print(f"  Eliminados {deleted} partidos sin API ID.")

        total = 0
        skipped = 0

        for group, teams in GROUPS.items():
            schedule = GROUP_SCHEDULE[group]
            matches = build_matches(group, teams, schedule)

            for m in matches:
                # Evitar duplicados por equipos + fecha
                exists = db.query(Match).filter(
                    Match.home_team == m["home"],
                    Match.away_team == m["away"],
                    Match.stage == m["stage"],
                ).first()
                if exists:
                    skipped += 1
                    continue

                db.add(Match(
                    home_team=m["home"],
                    away_team=m["away"],
                    home_flag=football_api.get_flag(m["home"]),
                    away_flag=football_api.get_flag(m["away"]),
                    match_date=m["date"],
                    stage=m["stage"],
                    status="SCHEDULED",
                ))
                total += 1

        db.commit()

        print(f"\n  OK Fase de grupos cargada:")
        print(f"     {total} partidos nuevos agregados")
        if skipped:
            print(f"     {skipped} ya existian (omitidos)")
        print(f"\n  Grupos cargados: {len(GROUPS)}")
        print(f"  Total partidos: {total + skipped} / 72")
        print(f"\n  NOTA: Fechas/horas son aproximadas (UTC).")
        print(f"     Usa el boton Sync en la app para datos exactos de la API.")

    except Exception as e:
        db.rollback()
        print(f"\n  ❌ Error: {e}")
        raise
    finally:
        db.close()


def update_flags():
    """Actualiza los codigos de bandera en todos los partidos existentes."""
    db = SessionLocal()
    try:
        matches = db.query(Match).all()
        updated = 0
        for m in matches:
            new_home = football_api.get_flag(m.home_team)
            new_away = football_api.get_flag(m.away_team)
            if m.home_flag != new_home or m.away_flag != new_away:
                m.home_flag = new_home
                m.away_flag = new_away
                updated += 1
        db.commit()
        print(f"\n  Banderas actualizadas: {updated} partidos")
        no_flag = [m.home_team for m in matches if not m.home_flag] + \
                  [m.away_team for m in matches if not m.away_flag]
        if no_flag:
            print(f"  Sin bandera: {', '.join(set(no_flag))}")
    finally:
        db.close()


if __name__ == "__main__":
    clear = "--clear" in sys.argv
    flags = "--update-flags" in sys.argv
    print("\nSeed Fase de Grupos - Mundial 2026")
    print("=" * 45)
    if flags:
        print("  Modo: actualizar banderas\n")
        update_flags()
    else:
        if clear:
            print("  Modo: limpieza + recarga completa\n")
        seed(clear=clear)
