from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas as s
from ..auth import Identity, get_current_student, get_identity
from ..database import get_db
from ..models import Exam, Student
from ..services.exams import (
    exams_for_student,
    to_detail,
    to_progress_point,
    to_reason_counts,
    to_summary,
)

router = APIRouter(prefix="/api", tags=["student"])


@router.get("/me", response_model=s.StudentOut)
def get_me(
    student: Student = Depends(get_current_student),
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    exam_count = db.scalar(select(func.count(Exam.id)).where(Exam.student_id == student.id)) or 0
    return s.StudentOut(
        full_name=student.full_name,
        is_advisor=identity.is_advisor,
        exam_count=exam_count,
    )


@router.get("/exams", response_model=list[s.ExamSummaryOut])
def list_exams(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    exams = db.scalars(exams_for_student(student.id)).all()
    return [to_summary(e) for e in exams]


@router.get("/exams/{exam_id}", response_model=s.ExamDetailOut)
def get_exam(
    exam_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    # Scoped by student_id. Another student's exam returns 404, not 403, so ids cannot be probed.
    exam = db.scalar(exams_for_student(student.id).where(Exam.id == exam_id))
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این آزمون یافت نشد.")
    return to_detail(exam)


@router.get("/progress", response_model=list[s.ProgressPointOut])
def get_progress(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    exams = db.scalars(exams_for_student(student.id)).all()
    return [to_progress_point(e) for e in exams]


@router.get("/progress/reasons", response_model=list[s.ReasonCountOut])
def get_reason_trends(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    exams = db.scalars(exams_for_student(student.id)).all()
    return [to_reason_counts(e) for e in exams]