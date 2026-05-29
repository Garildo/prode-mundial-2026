from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth as auth_utils
import models
from database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    email = req.email.lower().strip()
    username = req.username.strip()

    if not email or not username or not req.password:
        raise HTTPException(400, "Todos los campos son obligatorios")
    if len(req.password) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(400, "El email ya está registrado")
    if db.query(models.User).filter(models.User.username == username).first():
        raise HTTPException(400, "El nombre de usuario ya está en uso")

    user = models.User(email=email, username=username, password_hash=auth_utils.hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = auth_utils.create_access_token({"sub": str(user.id)})
    return {"token": token, "username": user.username, "email": user.email, "id": user.id}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == req.email.lower().strip()).first()
    if not user or not auth_utils.verify_password(req.password, user.password_hash):
        raise HTTPException(401, "Email o contraseña incorrectos")

    token = auth_utils.create_access_token({"sub": str(user.id)})
    return {"token": token, "username": user.username, "email": user.email, "id": user.id}


@router.get("/me")
def get_me(current_user: models.User = Depends(auth_utils.get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "email": current_user.email}
