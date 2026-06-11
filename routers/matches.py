from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth as auth_utils
from auth import require_admin
import football_api
import models
from database import get_db

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _fmt(m: models.Match) -> dict:
    return {
        "id": m.id,
        "home_team": m.home_team,
        "away_team": m.away_team,
        "home_flag": m.home_flag,
        "away_flag": m.away_flag,
        "match_date": m.match_date.isoformat() if m.match_date else None,
        "stage": m.stage,
        "status": m.status,
        "result": m.result,
        "home_score": m.home_score,
        "away_score": m.away_score,
    }


@router.get("")
def list_matches(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    matches = db.query(models.Match).order_by(models.Match.match_date).all()
    return [_fmt(m) for m in matches]


@router.get("/{match_id}")
def get_match(
    match_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    m = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not m:
        raise HTTPException(404, "Partido no encontrado")
    return _fmt(m)


@router.post("/sync")
async def sync(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    return await football_api.sync_matches(db)


class CreateMatchRequest(BaseModel):
    home_team: str
    away_team: str
    match_date: str  # ISO format: "2026-06-11T18:00:00"
    stage: str       # e.g. "GRUPO_A", "FINAL"


@router.post("")
def create_match(
    req: CreateMatchRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    try:
        match_date = datetime.fromisoformat(req.match_date)
    except ValueError:
        raise HTTPException(400, "Fecha inválida. Usar formato: 2026-06-11T18:00:00")

    m = models.Match(
        home_team=req.home_team.strip(),
        away_team=req.away_team.strip(),
        home_flag=football_api.get_flag(req.home_team),
        away_flag=football_api.get_flag(req.away_team),
        match_date=match_date,
        stage=req.stage.strip().upper(),
        status="SCHEDULED",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return _fmt(m)


class SetResultRequest(BaseModel):
    home_score: int
    away_score: int


@router.put("/{match_id}/result")
def set_result(
    match_id: int,
    req: SetResultRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    m = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not m:
        raise HTTPException(404, "Partido no encontrado")

    m.home_score = req.home_score
    m.away_score = req.away_score
    m.result = football_api.determine_result(req.home_score, req.away_score)
    m.status = "FINISHED"
    m.updated_at = datetime.utcnow()
    db.commit()

    football_api._update_predictions_correctness(db)
    return _fmt(m)
