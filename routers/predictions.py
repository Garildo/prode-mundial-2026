from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

import auth as auth_utils
import football_api
import models
from database import get_db

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


class BatchPredictionItem(BaseModel):
    match_id: int
    home_score: int
    away_score: int


class BatchPredictionRequest(BaseModel):
    group_id: int
    predictions: list[BatchPredictionItem]


def _infer_result(home: int, away: int) -> str:
    if home > away:
        return "HOME"
    if away > home:
        return "AWAY"
    return "DRAW"


@router.post("/batch")
def make_predictions_batch(
    req: BatchPredictionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    if not db.query(models.GroupMember).filter(
        models.GroupMember.group_id == req.group_id,
        models.GroupMember.user_id == current_user.id,
    ).first():
        raise HTTPException(403, "No perteneces a este grupo")

    saved = 0
    errors = []
    now = datetime.now(timezone.utc)

    for item in req.predictions:
        if item.home_score < 0 or item.away_score < 0:
            errors.append({"match_id": item.match_id, "error": "Score inválido"})
            continue

        match = db.query(models.Match).filter(models.Match.id == item.match_id).first()
        if not match:
            errors.append({"match_id": item.match_id, "error": "Partido no encontrado"})
            continue

        if match.status == "FINISHED":
            errors.append({"match_id": item.match_id, "error": "Partido ya terminó"})
            continue


        result = _infer_result(item.home_score, item.away_score)
        existing = db.query(models.Prediction).filter(
            models.Prediction.user_id == current_user.id,
            models.Prediction.group_id == req.group_id,
            models.Prediction.match_id == item.match_id,
        ).first()

        if existing:
            existing.prediction = result
            existing.predicted_home = item.home_score
            existing.predicted_away = item.away_score
            existing.updated_at = datetime.utcnow()
        else:
            db.add(models.Prediction(
                user_id=current_user.id,
                group_id=req.group_id,
                match_id=item.match_id,
                prediction=result,
                predicted_home=item.home_score,
                predicted_away=item.away_score,
            ))
        saved += 1

    db.commit()
    return {"saved": saved, "errors": errors}


@router.get("/public")
def get_public_predictions(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    if not db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == current_user.id,
    ).first():
        raise HTTPException(403, "No perteneces a este grupo")

    now = datetime.utcnow()
    started_ids = [
        m.id for m in db.query(models.Match.id).filter(
            or_(
                models.Match.match_date <= now,
                models.Match.status.in_(["LIVE", "FINISHED"]),
            )
        ).all()
    ]
    if not started_ids:
        return {}

    rows = (
        db.query(models.Prediction, models.User.username)
        .join(models.User, models.Prediction.user_id == models.User.id)
        .filter(
            models.Prediction.group_id == group_id,
            models.Prediction.match_id.in_(started_ids),
        )
        .all()
    )

    result: dict[int, list] = {}
    for pred, username in rows:
        result.setdefault(pred.match_id, []).append({
            "user_id": pred.user_id,
            "username": username,
            "prediction": pred.prediction,
            "predicted_home": pred.predicted_home,
            "predicted_away": pred.predicted_away,
            "is_correct": pred.is_correct,
            "is_exact": pred.is_exact,
        })

    return result


@router.get("")
def get_predictions(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    if not db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == current_user.id,
    ).first():
        raise HTTPException(403, "No perteneces a este grupo")

    preds = db.query(models.Prediction).filter(
        models.Prediction.user_id == current_user.id,
        models.Prediction.group_id == group_id,
    ).all()

    return [{
        "match_id": p.match_id,
        "prediction": p.prediction,
        "predicted_home": p.predicted_home,
        "predicted_away": p.predicted_away,
        "is_correct": p.is_correct,
        "is_exact": p.is_exact,
    } for p in preds]
