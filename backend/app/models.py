from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
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
    subject_results: Mapped[list["ExamSubjectResult"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan"
    )
    notes: Mapped[list["ExamNote"]] = relationship(back_populates="exam", cascade="all, delete-orphan")
    
class ExamSubjectResult(Base):
    __tablename__ = "exam_subject_results"
    __table_args__ = (
        UniqueConstraint("exam_id", "subject_id", name="uq_result_per_subject"),
        CheckConstraint(
            "correct_count >= 0 AND wrong_count >= 0 AND blank_count >= 0",
            name="ck_counts_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    rank: Mapped[int | None] = mapped_column(Integer)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    blank_count: Mapped[int] = mapped_column(Integer, default=0)

    exam: Mapped[Exam] = relationship(back_populates="subject_results")
    subject: Mapped[Subject] = relationship()
    reasons: Mapped[list["QuestionReason"]] = relationship(
        back_populates="subject_result", cascade="all, delete-orphan"
    )


class QuestionReason(Base):
    """One entry of the reason lists in the form, e.g. 'careless' -> '12، 15'."""

    __tablename__ = "question_reasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_result_id: Mapped[int] = mapped_column(
        ForeignKey("exam_subject_results.id", ondelete="CASCADE"), index=True
    )
    reason_code: Mapped[str] = mapped_column(String(32))  # see reasons.py
    item_ref: Mapped[str] = mapped_column(String(200))  # question numbers or topic, as entered

    subject_result: Mapped[ExamSubjectResult] = relationship(back_populates="reasons")


class ExamNote(Base):
    __tablename__ = "exam_notes"
    __table_args__ = (UniqueConstraint("exam_id", "level", name="uq_note_per_level"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(32))  # from_scratch | more_practice | review
    text: Mapped[str] = mapped_column(Text)

    exam: Mapped[Exam] = relationship(back_populates="notes")