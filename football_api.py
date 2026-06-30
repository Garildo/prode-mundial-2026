import os
from datetime import datetime
from collections import defaultdict

import httpx
from sqlalchemy.orm import Session

import models

FOOTBALL_API_KEY = os.getenv("FOOTBALL_API_KEY", "")
FOOTBALL_API_BASE = "https://api.football-data.org/v4"
COMPETITION_CODE = "WC"
SEASON = "2026"

# Valores: código ISO alpha-2 para flagcdn.com (ej: "ar" → flagcdn.com/w40/ar.png)
# Excepciones: naciones constitutivas de UK usan "gb-eng", "gb-sct", "gb-wls"
FLAG_MAP = {
    # Grupo A — EN + ES
    "mexico": "mx", "méxico": "mx", "south korea": "kr", "corea del sur": "kr", "korea republic": "kr",
    "south africa": "za", "sudáfrica": "za", "sudafrica": "za",
    "czechia": "cz", "czech republic": "cz", "rep. checa": "cz", "república checa": "cz",
    # Grupo B
    "canada": "ca", "canadá": "ca", "switzerland": "ch", "suiza": "ch",
    "qatar": "qa", "bosnia": "ba", "bosnia and herzegovina": "ba", "bosnia y herzegovina": "ba",
    # Grupo C
    "brazil": "br", "brasil": "br", "morocco": "ma", "marruecos": "ma",
    "scotland": "gb-sct", "escocia": "gb-sct", "haiti": "ht", "haití": "ht",
    # Grupo D
    "united states": "us", "estados unidos": "us", "usa": "us",
    "turkey": "tr", "turquía": "tr", "turquia": "tr", "türkiye": "tr",
    "australia": "au", "paraguay": "py",
    # Grupo E
    "germany": "de", "alemania": "de", "ecuador": "ec",
    "ivory coast": "ci", "costa de marfil": "ci", "curacao": "cw", "curazao": "cw", "curaçao": "cw",
    # Grupo F
    "netherlands": "nl", "países bajos": "nl", "paises bajos": "nl",
    "japan": "jp", "japón": "jp", "japon": "jp",
    "sweden": "se", "suecia": "se", "tunisia": "tn", "túnez": "tn", "tunez": "tn",
    # Grupo G
    "belgium": "be", "bélgica": "be", "belgica": "be",
    "iran": "ir", "irán": "ir", "egypt": "eg", "egipto": "eg",
    "new zealand": "nz", "nueva zelanda": "nz",
    # Grupo H
    "spain": "es", "españa": "es", "espana": "es",
    "uruguay": "uy", "saudi arabia": "sa", "arabia saudita": "sa", "cape verde": "cv", "cabo verde": "cv",
    # Grupo I
    "france": "fr", "francia": "fr", "senegal": "sn",
    "norway": "no", "noruega": "no", "iraq": "iq", "irak": "iq",
    # Grupo J
    "argentina": "ar", "austria": "at", "algeria": "dz", "argelia": "dz",
    "jordan": "jo", "jordania": "jo",
    # Grupo K
    "portugal": "pt", "colombia": "co",
    "dr congo": "cd", "congo rd": "cd", "congo": "cd", "uzbekistan": "uz", "uzbekistán": "uz",
    # Grupo L
    "england": "gb-eng", "inglaterra": "gb-eng",
    "croatia": "hr", "croacia": "hr", "ghana": "gh", "panama": "pa", "panamá": "pa",
    # Otros
    "italy": "it", "denmark": "dk", "poland": "pl", "serbia": "rs",
    "ukraine": "ua", "nigeria": "ng", "cameroon": "cm", "chile": "cl",
    "peru": "pe", "venezuela": "ve", "bolivia": "bo", "mali": "ml",
    "slovakia": "sk", "hungary": "hu", "romania": "ro", "greece": "gr",
    "wales": "gb-wls", "ireland": "ie", "costa rica": "cr", "honduras": "hn",
    "jamaica": "jm", "cuba": "cu", "kenya": "ke", "ethiopia": "et",
}

TEAM_TRANSLATIONS = {
    "Mexico": "México", "South Korea": "Corea del Sur", "Korea Republic": "Corea del Sur",
    "South Africa": "Sudáfrica", "Czechia": "Rep. Checa", "Czech Republic": "Rep. Checa",
    "Canada": "Canadá", "Switzerland": "Suiza", "Bosnia and Herzegovina": "Bosnia y Herzegovina",
    "Brazil": "Brasil", "Morocco": "Marruecos", "Scotland": "Escocia", "Haiti": "Haití",
    "United States": "Estados Unidos", "USA": "Estados Unidos",
    "Turkey": "Turquía", "Türkiye": "Turquía",
    "Germany": "Alemania", "Ivory Coast": "Costa de Marfil", "Côte d'Ivoire": "Costa de Marfil",
    "Curacao": "Curazao", "Curaçao": "Curazao",
    "Netherlands": "Países Bajos", "Japan": "Japón", "Sweden": "Suecia", "Tunisia": "Túnez",
    "Belgium": "Bélgica", "Iran": "Irán", "Egypt": "Egipto", "New Zealand": "Nueva Zelanda",
    "Spain": "España", "Saudi Arabia": "Arabia Saudita", "Cape Verde": "Cabo Verde",
    "France": "Francia", "Norway": "Noruega", "Iraq": "Irak",
    "Algeria": "Argelia", "Jordan": "Jordania",
    "DR Congo": "Congo RD", "Congo": "Congo RD", "Uzbekistan": "Uzbekistán",
    "England": "Inglaterra", "Croatia": "Croacia", "Panama": "Panamá",
}


def translate_team(name: str) -> str:
    return TEAM_TRANSLATIONS.get(name, name)


STAGE_LABELS = {
    "GROUP_STAGE": "Fase de Grupos",
    "ROUND_OF_32": "Octavos",
    "ROUND_OF_16": "Octavos",
    "QUARTER_FINALS": "Cuartos",
    "SEMI_FINALS": "Semifinales",
    "THIRD_PLACE": "Tercer Puesto",
    "FINAL": "Final",
}


def get_flag(team_name: str) -> str:
    """Devuelve código ISO alpha-2 para usar con flagcdn.com."""
    if not team_name:
        return ""
    name_lower = team_name.lower()
    for key, code in FLAG_MAP.items():
        if key in name_lower or name_lower in key:
            return code
    return ""


_STAGE_NORM = {
    "LAST_32": "RONDA_32",
    "LAST_16": "OCTAVOS",
    "ROUND_OF_32": "RONDA_32",
    "ROUND_OF_16": "OCTAVOS",
    "QUARTER_FINALS": "CUARTOS",
    "SEMI_FINALS": "SEMIFINAL",
    "THIRD_PLACE": "TERCER_PUESTO",
    "FINAL": "FINAL",
}

def parse_stage(stage_raw: str, group_raw: str = "") -> str:
    if stage_raw == "GROUP_STAGE":
        letter = group_raw.replace("GROUP_", "").replace("Group ", "").strip()
        return f"GRUPO_{letter}" if letter else "GRUPOS"
    return _STAGE_NORM.get(stage_raw, stage_raw)


def determine_result(home: int, away: int, penalty_home: int = None, penalty_away: int = None) -> str:
    if home > away:
        return "HOME"
    if away > home:
        return "AWAY"
    if penalty_home is not None and penalty_away is not None:
        if penalty_home > penalty_away:
            return "HOME"
        if penalty_away > penalty_home:
            return "AWAY"
    return "DRAW"


async def sync_matches(db: Session) -> dict:
    if not FOOTBALL_API_KEY:
        return {"synced": 0, "error": "Sin clave API. Configura FOOTBALL_API_KEY en .env"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{FOOTBALL_API_BASE}/competitions/{COMPETITION_CODE}/matches",
                params={"season": SEASON},
                headers={"X-Auth-Token": FOOTBALL_API_KEY},
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        return {"synced": 0, "error": str(e)}

    status_map = {
        "SCHEDULED": "SCHEDULED", "TIMED": "SCHEDULED",
        "IN_PLAY": "LIVE", "PAUSED": "LIVE",
        "FINISHED": "FINISHED", "POSTPONED": "SCHEDULED",
    }

    synced = 0
    for m in data.get("matches", []):
        api_id = m["id"]
        raw_home = m["homeTeam"].get("name") or m["homeTeam"].get("shortName") or "TBD"
        raw_away = m["awayTeam"].get("name") or m["awayTeam"].get("shortName") or "TBD"
        home_team = translate_team(raw_home)
        away_team = translate_team(raw_away)

        # Saltar partidos sin equipos definidos
        if home_team == "TBD" or away_team == "TBD":
            continue

        match_date = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")).replace(tzinfo=None)
        m_stage_raw = m.get("stage", "GROUP_STAGE")
        # m.get("group") puede devolver None si la API envía null — usar or "" para evitar crash
        stage = parse_stage(m_stage_raw, m.get("group") or "")
        status = status_map.get(m.get("status", "SCHEDULED"), "SCHEDULED")

        ft = m.get("score", {}).get("fullTime", {})
        home_score = ft.get("home")
        away_score = ft.get("away")
        pen = m.get("score", {}).get("penalties", {}) or {}
        penalty_home_api = pen.get("home")
        penalty_away_api = pen.get("away")

        # B1: por api_id
        inverted = False
        existing = db.query(models.Match).filter(models.Match.api_id == api_id).first()
        if existing and existing.home_team == away_team:
            inverted = True
        # B2: equipos + stage
        if not existing:
            existing = db.query(models.Match).filter(
                models.Match.home_team == home_team,
                models.Match.away_team == away_team,
                models.Match.stage == stage,
            ).first()
        # B3: equipos invertidos + stage
        if not existing:
            existing = db.query(models.Match).filter(
                models.Match.home_team == away_team,
                models.Match.away_team == home_team,
                models.Match.stage == stage,
            ).first()
            if existing:
                inverted = True
        # B4: equipos sin stage, solo registros del seed (api_id IS NULL)
        if not existing:
            existing = db.query(models.Match).filter(
                models.Match.home_team == home_team,
                models.Match.away_team == away_team,
                models.Match.api_id.is_(None),
            ).first()
        # B5: equipos invertidos sin stage, solo registros del seed
        if not existing:
            existing = db.query(models.Match).filter(
                models.Match.home_team == away_team,
                models.Match.away_team == home_team,
                models.Match.api_id.is_(None),
            ).first()
            if existing:
                inverted = True

        if existing:
            # Si los equipos están invertidos respecto a la API, swapear scores
            db_home_score = away_score if inverted else home_score
            db_away_score = home_score if inverted else away_score
            db_pen_home = penalty_away_api if inverted else penalty_home_api
            db_pen_away = penalty_home_api if inverted else penalty_away_api
            db_result = determine_result(db_home_score, db_away_score, db_pen_home, db_pen_away) if status == "FINISHED" and db_home_score is not None else None

            existing.api_id = api_id
            existing.match_date = match_date
            existing.status = status
            existing.home_score = db_home_score
            existing.away_score = db_away_score
            existing.penalty_home = db_pen_home
            existing.penalty_away = db_pen_away
            existing.result = db_result
            existing.updated_at = datetime.utcnow()
        elif m_stage_raw != "GROUP_STAGE":
            # Solo insertar partidos que NO son de fase de grupos (eliminatorias)
            # Los de fase de grupos los carga el seed; si llegamos aquí es un duplicado fantasma
            new_result = determine_result(home_score, away_score, penalty_home_api, penalty_away_api) if status == "FINISHED" and home_score is not None else None
            db.add(models.Match(
                api_id=api_id,
                home_team=home_team,
                away_team=away_team,
                home_flag=get_flag(home_team),
                away_flag=get_flag(away_team),
                match_date=match_date,
                stage=stage,
                status=status,
                result=new_result,
                home_score=home_score,
                away_score=away_score,
                penalty_home=penalty_home_api,
                penalty_away=penalty_away_api,
            ))
        synced += 1

    db.commit()
    _update_predictions_correctness(db)
    return {"synced": synced}


def _update_predictions_correctness(db: Session):
    finished = db.query(models.Match).filter(
        models.Match.status == "FINISHED",
        models.Match.result.isnot(None),
    ).all()

    for match in finished:
        preds = db.query(models.Prediction).filter(
            models.Prediction.match_id == match.id,
        ).all()
        for p in preds:
            p.is_correct = p.prediction == match.result
            if p.predicted_home is not None and match.home_score is not None:
                p.is_exact = p.is_correct and (
                    p.predicted_home == match.home_score and
                    p.predicted_away == match.away_score
                )

    db.commit()
