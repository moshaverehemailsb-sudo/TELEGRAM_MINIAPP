from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    exams: Mapped[list["Exam"]] = relationship(back_populates="student", cascade="all, delete-orphan")


class Advisor(Base):
    """Created only by an admin. Advisors cannot create other advisors."""

    __tablename__ = "advisors"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdvisorStudent(Base):
    """Link between a student and an advisor. Rows are deactivated, not deleted, to keep history."""

    __tablename__ = "advisor_students"
    __table_args__ = (
        # A student may have at most ONE active advisor at a time.
        Index(
            "uq_one_active_advisor_per_student",
            "student_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    advisor_id: Mapped[int] = mapped_column(ForeignKey("advisors.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    advisor: Mapped["Advisor"] = relationship()
    student: Mapped["Student"] = relationship()


class InviteCode(Base):
    """One-time code created by an advisor. Only a hash is stored, never the code itself."""

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    advisor_id: Mapped[int] = mapped_column(ForeignKey("advisors.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by_student_id: Mapped[int | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # math | physics | chemistry
    name_fa: Mapped[str] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (
        UniqueConstraint("student_id", "name", "held_on_text", name="uq_exam_per_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    held_on_text: Mapped[str] = mapped_column(String(10))  # Jalali, zero-padded, e.g. 1405/01/10
    held_on: Mapped[date | None] = mapped_column(Date)  # optional Gregorian date
    overall_traz: Mapped[int | None] = mapped_column(Integer)
    overall_rank: Mapped[int | None] = mapped_column(Integer)
    region_rank: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    student: Mapped[Student] = relationship(back_populates="exams")