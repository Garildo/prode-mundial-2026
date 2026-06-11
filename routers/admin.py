from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from auth import require_admin, hash_password
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
