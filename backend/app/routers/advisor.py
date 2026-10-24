from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas as s
from ..auth import Identity, require_advisor
from ..config import get_settings
from ..database import get_db
from ..models import AdvisorStudent, Exam, InviteCode, Student
from ..services.exams import exams_for_student, to_detail, to_summary
from ..services.invites import generate_code, hash_code
from ..services.links import is_linked

router = APIRouter(prefix="/api/advisor", tags=["advisor"])

# Same message for "does not exist" and "not linked to you", so IDs cannot be probed.
NOT_FOUND = "یافت نشد."


class InviteCreatedOut(BaseModel):
    code: str  # shown once, never stored in plain text
    expires_at: datetime


class InviteStatusOut(BaseModel):
    id: int
    status: str  # pending | used | expired
    created_at: datetime
    expires_at: datetime


class LinkedStudentOut(BaseModel):
    id: int
    full_name: str
    linked_at: datetime
    exam_count: int


def _invite_status(invite: InviteCode, now: datetime) -> str:
    if invite.used_at is not None:
        return "used"
    if invite.expires_at <= now:
        return "expired"
    return "pending"


def _ensure_linked(db: Session, advisor_id: int, student_id: int) -> None:
    if not is_linked(db, advisor_id, student_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)


@router.post("/invites", response_model=InviteCreatedOut, status_code=status.HTTP_201_CREATED)
def create_invite(identity: Identity = Depends(require_advisor), db: Session = Depends(get_db)):
    ttl_days = get_settings().invite_code_ttl_days
    code = generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)
    db.add(
        InviteCode(
            advisor_id=identity.advisor_id,
            code_hash=hash_code(code),
            expires_at=expires_at,
        )
    )
    db.commit()
    return InviteCreatedOut(code=code, expires_at=expires_at)


@router.get("/invites", response_model=list[InviteStatusOut])
def list_invites(identity: Identity = Depends(require_advisor), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    invites = db.scalars(
        select(InviteCode)
        .where(InviteCode.advisor_id == identity.advisor_id)
        .order_by(InviteCode.created_at.desc())
    ).all()
    return [
        InviteStatusOut(
            id=inv.id,
            status=_invite_status(inv, now),
            created_at=inv.created_at,
            expires_at=inv.expires_at,
        )
        for inv in invites
    ]


@router.get("/students", response_model=list[LinkedStudentOut])
def list_students(identity: Identity = Depends(require_advisor), db: Session = Depends(get_db)):
    rows = db.execute(
        select(Student.id, Student.full_name, AdvisorStudent.linked_at, func.count(Exam.id))
        .join(AdvisorStudent, AdvisorStudent.student_id == Student.id)
        .outerjoin(Exam, Exam.student_id == Student.id)
        .where(
            AdvisorStudent.advisor_id == identity.advisor_id,
            AdvisorStudent.is_active.is_(True),
        )
        .group_by(Student.id, Student.full_name, AdvisorStudent.linked_at)
        .order_by(Student.full_name)
    ).all()
    return [
        LinkedStudentOut(id=r[0], full_name=r[1], linked_at=r[2], exam_count=r[3])
        for r in rows
    ]


@router.get("/students/{student_id}/exams", response_model=list[s.ExamSummaryOut])
def list_student_exams(
    student_id: int,
    identity: Identity = Depends(require_advisor),
    db: Session = Depends(get_db),
):
    _ensure_linked(db, identity.advisor_id, student_id)
    exams = db.scalars(exams_for_student(student_id)).all()
    return [to_summary(e) for e in exams]


@router.get("/exams/{exam_id}", response_model=s.ExamDetailOut)
def get_exam(
    exam_id: int,
    identity: Identity = Depends(require_advisor),
    db: Session = Depends(get_db),
):
    exam_row = db.get(Exam, exam_id)
    if exam_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_FOUND)
    _ensure_linked(db, identity.advisor_id, exam_row.student_id)

    exam = db.scalar(exams_for_student(exam_row.student_id).where(Exam.id == exam_id))
    return to_detail(exam)