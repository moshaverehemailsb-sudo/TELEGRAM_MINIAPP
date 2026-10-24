from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..auth import Identity, require_admin
from ..database import get_db
from ..models import Advisor, AdvisorStudent, Exam, Student

# The admin sees only basic information: names, Telegram IDs, counts and the summary
# of the latest exam. Subject details, reasons and notes are never returned here.
router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdvisorCreate(BaseModel):
    telegram_user_id: int = Field(gt=0)
    full_name: str = Field(min_length=2, max_length=120)


class AdvisorUpdate(BaseModel):
    is_active: bool


class AdvisorOut(BaseModel):
    id: int
    full_name: str
    telegram_user_id: int
    is_active: bool
    student_count: int


class LatestExamOut(BaseModel):
    name: str
    held_on: str
    overall_traz: int | None
    overall_rank: int | None


class AdminStudentOut(BaseModel):
    id: int
    full_name: str
    telegram_user_id: int
    linked_at: datetime | None
    exam_count: int
    latest_exam: LatestExamOut | None


def _active_student_count(db: Session, advisor_id: int) -> int:
    return db.scalar(
        select(func.count(AdvisorStudent.id)).where(
            AdvisorStudent.advisor_id == advisor_id,
            AdvisorStudent.is_active.is_(True),
        )
    ) or 0


def _advisor_out(advisor: Advisor, student_count: int) -> AdvisorOut:
    return AdvisorOut(
        id=advisor.id,
        full_name=advisor.full_name,
        telegram_user_id=advisor.telegram_user_id,
        is_active=advisor.is_active,
        student_count=student_count,
    )


def _exam_stats(db: Session, student_ids: list[int]) -> tuple[dict[int, int], dict[int, Exam]]:
    """Return (exam count per student, latest exam per student)."""
    if not student_ids:
        return {}, {}
    counts = dict(
        db.execute(
            select(Exam.student_id, func.count(Exam.id))
            .where(Exam.student_id.in_(student_ids))
            .group_by(Exam.student_id)
        ).all()
    )
    latest: dict[int, Exam] = {}
    rows = db.scalars(
        select(Exam).where(Exam.student_id.in_(student_ids)).order_by(Exam.held_on_text, Exam.id)
    ).all()
    for exam in rows:
        latest[exam.student_id] = exam  # ordered ascending, so the last one is the latest
    return counts, latest


def _to_admin_student(
    student: Student,
    linked_at: datetime | None,
    counts: dict[int, int],
    latest: dict[int, Exam],
) -> AdminStudentOut:
    last = latest.get(student.id)
    return AdminStudentOut(
        id=student.id,
        full_name=student.full_name,
        telegram_user_id=student.telegram_user_id,
        linked_at=linked_at,
        exam_count=counts.get(student.id, 0),
        latest_exam=None
        if last is None
        else LatestExamOut(
            name=last.name,
            held_on=last.held_on_text,
            overall_traz=last.overall_traz,
            overall_rank=last.overall_rank,
        ),
    )


@router.get("/advisors", response_model=list[AdvisorOut])
def list_advisors(_: Identity = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Advisor, func.count(AdvisorStudent.id))
        .outerjoin(
            AdvisorStudent,
            and_(AdvisorStudent.advisor_id == Advisor.id, AdvisorStudent.is_active.is_(True)),
        )
        .group_by(Advisor.id)
        .order_by(Advisor.full_name)
    ).all()
    return [_advisor_out(advisor, count) for advisor, count in rows]


@router.post("/advisors", response_model=AdvisorOut, status_code=status.HTTP_201_CREATED)
def create_advisor(
    payload: AdvisorCreate,
    _: Identity = Depends(require_admin),
    db: Session = Depends(get_db),
):
    advisor = db.scalar(select(Advisor).where(Advisor.telegram_user_id == payload.telegram_user_id))
    if advisor is not None and advisor.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این شناسه تلگرام قبلاً به عنوان مشاور فعال ثبت شده است.",
        )
    if advisor is None:
        advisor = Advisor(
            telegram_user_id=payload.telegram_user_id,
            full_name=payload.full_name.strip(),
            is_active=True,
        )
        db.add(advisor)
    else:
        # Re-activate a previously deactivated advisor
        advisor.is_active = True
        advisor.full_name = payload.full_name.strip()
    db.commit()
    db.refresh(advisor)
    return _advisor_out(advisor, _active_student_count(db, advisor.id))


@router.patch("/advisors/{advisor_id}", response_model=AdvisorOut)
def update_advisor(
    advisor_id: int,
    payload: AdvisorUpdate,
    _: Identity = Depends(require_admin),
    db: Session = Depends(get_db),
):
    advisor = db.get(Advisor, advisor_id)
    if advisor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مشاور یافت نشد.")

    advisor.is_active = payload.is_active
    if not payload.is_active:
        # Free the students so they can choose another advisor with a new code.
        now = datetime.now(timezone.utc)
        links = db.scalars(
            select(AdvisorStudent).where(
                AdvisorStudent.advisor_id == advisor.id,
                AdvisorStudent.is_active.is_(True),
            )
        ).all()
        for link in links:
            link.is_active = False
            link.unlinked_at = now

    db.commit()
    db.refresh(advisor)
    return _advisor_out(advisor, _active_student_count(db, advisor.id))


@router.get("/advisors/{advisor_id}/students", response_model=list[AdminStudentOut])
def list_advisor_students(
    advisor_id: int,
    _: Identity = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.get(Advisor, advisor_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="مشاور یافت نشد.")

    rows = db.execute(
        select(Student, AdvisorStudent.linked_at)
        .join(AdvisorStudent, AdvisorStudent.student_id == Student.id)
        .where(
            AdvisorStudent.advisor_id == advisor_id,
            AdvisorStudent.is_active.is_(True),
        )
        .order_by(Student.full_name)
    ).all()

    students = [row[0] for row in rows]
    counts, latest = _exam_stats(db, [st.id for st in students])
    return [_to_admin_student(st, linked_at, counts, latest) for st, linked_at in rows]


@router.get("/unassigned-students", response_model=list[AdminStudentOut])
def list_unassigned_students(
    _: Identity = Depends(require_admin),
    db: Session = Depends(get_db),
):
    linked_ids = select(AdvisorStudent.student_id).where(AdvisorStudent.is_active.is_(True))
    students = db.scalars(
        select(Student).where(Student.id.not_in(linked_ids)).order_by(Student.full_name)
    ).all()
    counts, latest = _exam_stats(db, [st.id for st in students])
    return [_to_admin_student(st, None, counts, latest) for st in students]