from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth as auth_utils
import models
from database import get_db

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


class PredictionRequest(BaseModel):
    group_id: int
    match_id: int
    prediction: str  # HOME, AWAY, DRAW


@router.post("")
def make_prediction(
    req: PredictionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    if req.prediction not in ("HOME", "AWAY", "DRAW"):
        raise HTTPException(400, "Predicción inválida")

    if not db.query(models.GroupMember).filter(
        models.GroupMember.group_id == req.group_id,
        models.GroupMember.user_id == current_user.id,
    ).first():
        raise HTTPException(403, "No perteneces a este grupo")

    match = db.query(models.Match).filter(models.Match.id == req.match_id).first()
    if not match:
        raise HTTPException(404, "Partido no encontrado")

    if match.status in ("LIVE", "FINISHED"):
        raise HTTPException(400, "El partido ya comenzó o terminó")

    now = datetime.now(timezone.utc)
    match_date = match.match_date
    if match_date.tzinfo is None:
        match_date = match_date.replace(tzinfo=timezone.utc)
    if now >= match_date:
        raise HTTPException(400, "No se pueden hacer predicciones después del inicio del partido")

    existing = db.query(models.Prediction).filter(
        models.Prediction.user_id == current_user.id,
        models.Prediction.group_id == req.group_id,
        models.Prediction.match_id == req.match_id,
    ).first()

    if existing:
        existing.prediction = req.prediction
        existing.updated_at = datetime.utcnow()
    else:
        db.add(models.Prediction(
            user_id=current_user.id,
            group_id=req.group_id,
            match_id=req.match_id,
            prediction=req.prediction,
        ))

    db.commit()
    return {"status": "ok", "prediction": req.prediction}


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

    return [{"match_id": p.match_id, "prediction": p.prediction, "is_correct": p.is_correct}
            for p in preds]
