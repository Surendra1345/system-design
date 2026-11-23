from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    # "Bob" and "bob" are the same learner. The database enforces it, so two simultaneous sign-ups cannot both win.
    __table_args__ = (Index("ux_users_username_lower", func.lower(text("username")), unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    salt: Mapped[str] = mapped_column(String(64))
    password_hash: Mapped[str] = mapped_column(String(256))
    xp: Mapped[int] = mapped_column(Integer, default=0, index=True)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_day: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SessionToken(Base):
    """Only a hash of the token is stored, so a leaked database cannot be used to log in."""

    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[str] = mapped_column(String(40))
    read_done: Mapped[bool] = mapped_column(Boolean, default=False)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    best_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LevelProgress(Base):
    """Stars for each level of a lesson's game. The lesson's total is the sum of its levels."""

    __tablename__ = "level_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", "level"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[str] = mapped_column(String(40))
    level: Mapped[int] = mapped_column(Integer, default=0)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    best_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class StudyTime(Base):
    """The learner chooses a target and logs time. There is no schedule."""

    __tablename__ = "study_time"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[str] = mapped_column(String(40))
    target_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spent_sec: Mapped[int] = mapped_column(Integer, default=0)


class ProjectDone(Base):
    __tablename__ = "projects_done"
    __table_args__ = (UniqueConstraint("user_id", "project_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str] = mapped_column(String(40))


class XpEvent(Base):
    """An audit trail of every XP award. It also makes one-time awards impossible to repeat."""

    __tablename__ = "xp_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    ref: Mapped[str] = mapped_column(String(60))
    xp: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChallengeAttempt(Base):
    """One run of an Unknown Problem Challenge. Best stars per scenario and the variation count come from these rows."""

    __tablename__ = "challenge_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    template: Mapped[str] = mapped_column(String(20))
    seed: Mapped[int] = mapped_column(Integer)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    diag_right: Mapped[int] = mapped_column(Integer, default=0)
    diag_total: Mapped[int] = mapped_column(Integer, default=0)
    defended: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
