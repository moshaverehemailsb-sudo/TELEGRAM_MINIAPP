"""Helpers for the advisor-student link. Every advisor data query should go through these checks."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AdvisorStudent


def active_link_for_student(db: Session, student_id: int) -> AdvisorStudent | None:
    return db.scalar(
        select(AdvisorStudent).where(
            AdvisorStudent.student_id == student_id,
            AdvisorStudent.is_active.is_(True),
        )
    )


def is_linked(db: Session, advisor_id: int, student_id: int) -> bool:
    return db.scalar(
        select(AdvisorStudent.id).where(
            AdvisorStudent.advisor_id == advisor_id,
            AdvisorStudent.student_id == student_id,
            AdvisorStudent.is_active.is_(True),
        )
    ) is not None