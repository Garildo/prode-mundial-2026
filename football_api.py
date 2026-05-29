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
    # Grupo A
    "mexico": "mx", "south korea": "kr", "korea republic": "kr",
    "south africa": "za", "czechia": "cz", "czech republic": "cz",
    # Grupo B
    "canada": "ca", "switzerland": "ch", "qatar": "qa",
    "bosnia": "ba", "bosnia and herzegovina": "ba",
    # Grupo C
    "brazil": "br", "morocco": "ma", "scotland": "gb-sct", "haiti": "ht",
    # Grupo D
    "united states": "us", "usa": "us", "turkey": "tr", "türkiye": "tr",
    "australia": "au", "paraguay": "py",
    # Grupo E
    "germany": "de", "ecuador": "ec", "ivory coast": "ci",
    "curacao": "cw", "curaçao": "cw",
    # Grupo F
    "netherlands": "nl", "japan": "jp", "sweden": "se", "tunisia": "tn",
    # Grupo G
    "belgium": "be", "iran": "ir", "egypt": "eg", "new zealand": "nz",
    # Grupo H
    "spain": "es", "uruguay": "uy", "saudi arabia": "sa", "cape verde": "cv",
    # Grupo I
    "france": "fr", "senegal": "sn", "norway": "no", "iraq": "iq",
    # Grupo J
    "argentina": "ar", "austria": "at", "algeria": "dz", "jordan": "jo",
    # Grupo K
    "portugal": "pt", "colombia": "co", "dr congo": "cd", "congo": "cd", "uzbekistan": "uz",
    # Grupo L
    "england": "gb-eng", "croatia": "hr", "ghana": "gh", "panama": "pa",
    # Otros
    "italy": "it", "denmark": "dk", "poland": "pl", "serbia": "rs",
    "ukraine": "ua", "nigeria": "ng", "cameroon": "cm", "chile": "cl",
    "peru": "pe", "venezuela": "ve", "bolivia": "bo", "mali": "ml",
    "slovakia": "sk", "hungary": "hu", "romania": "ro", "greece": "gr",
    "wales": "gb-wls", "ireland": "ie", "costa rica": "cr", "honduras": "hn",
    "jamaica": "jm", "cuba": "cu", "kenya": "ke", "ethiopia": "et",
}

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
    name_lower = team_name.lower()
    for key, code in FLAG_MAP.items():
        if key in name_lower or name_lower in key:
            return code
    return ""


def parse_stage(stage_raw: str, group_raw: str = "") -> str:
    if stage_raw == "GROUP_STAGE":
        letter = group_raw.replace("GROUP_", "").replace("Group ", "").strip()
        return f"GRUPO_{letter}" if letter else "GRUPOS"
    return stage_raw


def determine_result(home: int, away: int) -> str:
    if home > away:
        return "HOME"
    if away > home:
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
        home_team = m["homeTeam"]["name"] or m["homeTeam"].get("shortName", "TBD")
        away_team = m["awayTeam"]["name"] or m["awayTeam"].get("shortName", "TBD")

        match_date = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")).replace(tzinfo=None)
        stage = parse_stage(m.get("stage", "GROUP_STAGE"), m.get("group", ""))
        status = status_map.get(m.get("status", "SCHEDULED"), "SCHEDULED")

        ft = m.get("score", {}).get("fullTime", {})
        home_score = ft.get("home")
        away_score = ft.get("away")
        result = determine_result(home_score, away_score) if status == "FINISHED" and home_score is not None else None

        existing = db.query(models.Match).filter(models.Match.api_id == api_id).first()
        if existing:
            existing.status = status
            existing.home_score = home_score
            existing.away_score = away_score
            existing.result = result
            existing.updated_at = datetime.utcnow()
        else:
            db.add(models.Match(
                api_id=api_id,
                home_team=home_team,
                away_team=away_team,
                home_flag=get_flag(home_team),
                away_flag=get_flag(away_team),
                match_date=match_date,
                stage=stage,
                status=status,
                result=result,
                home_score=home_score,
                away_score=away_score,
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
            models.Prediction.is_correct.is_(None),
        ).all()
        for p in preds:
            p.is_correct = p.prediction == match.result

    db.commit()
