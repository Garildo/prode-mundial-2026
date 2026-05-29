from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import auth as auth_utils
import models
from database import get_db

router = APIRouter(prefix="/api/rankings", tags=["rankings"])


def _calc_bonus(user_id: int, group_id: int, db: Session) -> int:
    finished_matches = db.query(models.Match).filter(
        models.Match.status == "FINISHED",
        models.Match.result.isnot(None),
    ).all()

    stage_match_ids: dict[str, set] = defaultdict(set)
    for m in finished_matches:
        if m.stage.startswith("GRUPO_"):
            stage_match_ids[m.stage].add(m.id)

    if not stage_match_ids:
        return 0

    correct_preds = db.query(models.Prediction).filter(
        models.Prediction.user_id == user_id,
        models.Prediction.group_id == group_id,
        models.Prediction.is_correct == True,
    ).all()
    all_preds = db.query(models.Prediction).filter(
        models.Prediction.user_id == user_id,
        models.Prediction.group_id == group_id,
    ).all()

    correct_ids = {p.match_id for p in correct_preds}
    all_pred_ids = {p.match_id for p in all_preds}

    bonus = 0
    for stage, match_ids in stage_match_ids.items():
        if match_ids and match_ids.issubset(all_pred_ids) and match_ids.issubset(correct_ids):
            bonus += 1
    return bonus


@router.get("/{group_id}")
def get_ranking(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    if not db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == current_user.id,
    ).first():
        raise HTTPException(403, "No perteneces a este grupo")

    members = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id
    ).all()

    total_matches = db.query(models.Match).count()

    rankings = []
    for member in members:
        u = member.user
        preds = db.query(models.Prediction).filter(
            models.Prediction.user_id == u.id,
            models.Prediction.group_id == group_id,
        ).all()

        base = sum(1 for p in preds if p.is_correct)
        bonus = _calc_bonus(u.id, group_id, db)
        total = base + bonus

        rankings.append({
            "user_id": u.id,
            "username": u.username,
            "base_points": base,
            "bonus_points": bonus,
            "total_points": total,
            "predictions_made": len(preds),
            "total_matches": total_matches,
        })

    rankings.sort(key=lambda x: x["total_points"], reverse=True)
    for i, r in enumerate(rankings):
        r["position"] = i + 1

    return rankings
