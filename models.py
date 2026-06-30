from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False, server_default="false")
    created_at = Column(DateTime, default=datetime.utcnow)

    memberships = relationship("GroupMember", back_populates="user")
    predictions = relationship("Prediction", back_populates="user")


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    invite_code = Column(String, unique=True, index=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    members = relationship("GroupMember", back_populates="group")
    creator = relationship("User", foreign_keys=[created_by])


class GroupMember(Base):
    __tablename__ = "group_members"
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("group_id", "user_id", name="unique_member"),)

    group = relationship("Group", back_populates="members")
    user = relationship("User", back_populates="memberships")


class Match(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True, index=True)
    api_id = Column(Integer, unique=True, index=True, nullable=True)
    home_team = Column(String, nullable=False)
    away_team = Column(String, nullable=False)
    home_flag = Column(String, default="🏳️")
    away_flag = Column(String, default="🏳️")
    match_date = Column(DateTime, nullable=False)
    stage = Column(String, nullable=False)
    status = Column(String, default="SCHEDULED")  # SCHEDULED, LIVE, FINISHED
    result = Column(String, nullable=True)         # HOME, AWAY, DRAW
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    penalty_home = Column(Integer, nullable=True)
    penalty_away = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    predictions = relationship("Prediction", back_populates="match")


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    prediction = Column(String, nullable=False)  # HOME, AWAY, DRAW (siempre seteado)
    predicted_home = Column(Integer, nullable=True)   # NULL = sistema viejo
    predicted_away = Column(Integer, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    is_exact = Column(Boolean, nullable=True)          # True si acertó score exacto
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (UniqueConstraint("user_id", "group_id", "match_id", name="unique_prediction"),)

    user = relationship("User", back_populates="predictions")
    match = relationship("Match", back_populates="predictions")
    group = relationship("Group")
