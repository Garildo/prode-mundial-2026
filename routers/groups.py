import random
import string

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import auth as auth_utils
import models
from database import get_db

router = APIRouter(prefix="/api/groups", tags=["groups"])


def _gen_code(length=6) -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


class CreateGroupRequest(BaseModel):
    name: str


class JoinGroupRequest(BaseModel):
    invite_code: str


@router.post("")
def create_group(
    req: CreateGroupRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    if not req.name.strip():
        raise HTTPException(400, "El nombre del grupo no puede estar vacío")

    code = _gen_code()
    while db.query(models.Group).filter(models.Group.invite_code == code).first():
        code = _gen_code()

    group = models.Group(name=req.name.strip(), invite_code=code, created_by=current_user.id)
    db.add(group)
    db.flush()

    db.add(models.GroupMember(group_id=group.id, user_id=current_user.id))
    db.commit()
    db.refresh(group)

    return {"id": group.id, "name": group.name, "invite_code": group.invite_code}


@router.post("/join")
def join_group(
    req: JoinGroupRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    group = db.query(models.Group).filter(
        models.Group.invite_code == req.invite_code.upper().strip()
    ).first()
    if not group:
        raise HTTPException(404, "Código de grupo inválido")

    already = db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group.id,
        models.GroupMember.user_id == current_user.id,
    ).first()
    if already:
        raise HTTPException(400, "Ya eres miembro de este grupo")

    db.add(models.GroupMember(group_id=group.id, user_id=current_user.id))
    db.commit()
    return {"id": group.id, "name": group.name, "invite_code": group.invite_code}


@router.get("")
def list_groups(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    memberships = db.query(models.GroupMember).filter(
        models.GroupMember.user_id == current_user.id
    ).all()

    result = []
    for m in memberships:
        g = m.group
        count = db.query(models.GroupMember).filter(models.GroupMember.group_id == g.id).count()
        result.append({
            "id": g.id,
            "name": g.name,
            "invite_code": g.invite_code,
            "member_count": count,
            "is_creator": g.created_by == current_user.id,
        })
    return result


@router.get("/{group_id}")
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth_utils.get_current_user),
):
    if not db.query(models.GroupMember).filter(
        models.GroupMember.group_id == group_id,
        models.GroupMember.user_id == current_user.id,
    ).first():
        raise HTTPException(403, "No perteneces a este grupo")

    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(404, "Grupo no encontrado")

    members = db.query(models.GroupMember).filter(models.GroupMember.group_id == group_id).all()

    return {
        "id": group.id,
        "name": group.name,
        "invite_code": group.invite_code,
        "is_creator": group.created_by == current_user.id,
        "members": [{"id": m.user_id, "username": m.user.username} for m in members],
    }
