from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_student
from ..database import get_db
from ..models import Advisor, AdvisorStudent, InviteCode, Student
from ..services.invites import hash_code
from ..services.links import active_link_for_student

router = APIRouter(prefix="/api/me/advisor", tags=["student-advisor"])

INVALID_CODE = "کد نامعتبر، استفاده‌شده یا منقضی است."


class RedeemIn(BaseModel):
    code: str = Field(min_length=4, max_length=20)


class AdvisorOut(BaseModel):
    id: int
    full_name: str
    linked_at: datetime


@router.get("", response_model=AdvisorOut | None)
def get_my_advisor(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    link = active_link_for_student(db, student.id)
    if link is None:
        return None
    advisor = db.get(Advisor, link.advisor_id)
    return AdvisorOut(id=advisor.id, full_name=advisor.full_name, linked_at=link.linked_at)


@router.post("/redeem", response_model=AdvisorOut)
def redeem_code(
    payload: RedeemIn,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    code_hash = hash_code(payload.code)
    if code_hash is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_CODE)

    # Lock the row so the same code cannot be used twice at the same moment.
    invite = db.scalar(
        select(InviteCode).where(InviteCode.code_hash == code_hash).with_for_update()
    )
    now = datetime.now(timezone.utc)
    if invite is None or invite.used_at is not None or invite.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=INVALID_CODE)

    advisor = db.get(Advisor, invite.advisor_id)
    if advisor is None or not advisor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="این مشاور در حال حاضر فعال نیست.",
        )

    current = active_link_for_student(db, student.id)
    if current is not None and current.advisor_id == advisor.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="شما هم‌اکنون به این مشاور متصل هستید.",
        )
    if current is not None:
        # Keep the old link as history, but deactivate it first.
        current.is_active = False
        current.unlinked_at = now
        db.flush()

    link = AdvisorStudent(advisor_id=advisor.id, student_id=student.id, is_active=True)
    db.add(link)
    invite.used_at = now
    invite.used_by_student_id = student.id
    db.commit()
    db.refresh(link)
    return AdvisorOut(id=advisor.id, full_name=advisor.full_name, linked_at=link.linked_at)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def unlink_advisor(
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    link = active_link_for_student(db, student.id)
    if link is not None:
        link.is_active = False
        link.unlinked_at = datetime.now(timezone.utc)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)