from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_admin, hash_password
import football_api
import models
from database import get_db

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    users = db.query(models.User).order_by(models.User.created_at).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.get("/groups")
def list_groups(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    groups = db.query(models.Group).order_by(models.Group.created_at).all()
    result = []
    for g in groups:
        members = (
            db.query(models.GroupMember, models.User.username)
            .join(models.User, models.GroupMember.user_id == models.User.id)
            .filter(models.GroupMember.group_id == g.id)
            .all()
        )
        creator = db.query(models.User.username).filter(models.User.id == g.created_by).scalar()
        result.append({
            "id": g.id,
            "name": g.name,
            "invite_code": g.invite_code,
            "creator": creator,
            "member_count": len(members),
            "members": [{"username": username} for _, username in members],
        })
    return result


@router.post("/recalculate")
def recalculate_points(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    football_api._update_predictions_correctness(db)
    processed = db.query(models.Match).filter(
        models.Match.status == "FINISHED",
        models.Match.result.isnot(None),
    ).count()
    return {"ok": True, "matches_processed": processed}


class ResetPasswordRequest(BaseModel):
    new_password: str


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    req: ResetPasswordRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    if len(req.new_password) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"ok": True, "username": user.username}
