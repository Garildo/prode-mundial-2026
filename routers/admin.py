from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import require_admin
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
