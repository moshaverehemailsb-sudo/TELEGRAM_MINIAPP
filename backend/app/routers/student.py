from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import schemas as s
from ..auth import Identity, get_current_student, get_identity
from ..database import get_db
from ..models import Exam, Student, Subject
from ..services.exams import (
    exams_for_student,
    to_detail,
    to_progress_point,
    to_reason_counts,
    to_summary,
)
from ..services.form_import import ExamFormIn, build_exam, export_exam_to_form

router = APIRouter(prefix="/api", tags=["student"])


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)


def _subjects_by_code(db: Session) -> dict[str, Subject]:
    subjects = {subj.code: subj for subj in db.scalars(select(Subject))}
    if not subjects:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="درس‌ها در دیتابیس تعریف نشده‌اند. init_db را اجرا کنید.",
        )
    return subjects


def _load_owned_exam(db: Session, student_id: int, exam_id: int) -> Exam | None:
    # Always scoped to the student. Another student's exam simply does not exist here.
    return db.scalar(exams_for_student(student_id).where(Exam.id == exam_id))


@router.post("/me/register", response_model=s.StudentOut, status_code=status.HTTP_201_CREATED)
def register_me(
    payload: RegisterIn,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(Student).where(Student.telegram_user_id == identity.telegram_user_id))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="شما قبلاً ثبت‌نام کرده‌اید.")

    student = Student(telegram_user_id=identity.telegram_user_id, full_name=payload.full_name.strip())
    db.add(student)
    db.commit()
    db.refresh(student)
    return s.StudentOut(full_name=student.full_name, is_advisor=identity.is_advisor, exam_count=0)


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
    exam = _load_owned_exam(db, student.id, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این آزمون یافت نشد.")
    return to_detail(exam)


@router.get("/exams/{exam_id}/form")
def get_exam_form(
    exam_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    exam = _load_owned_exam(db, student.id, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این آزمون یافت نشد.")
    return export_exam_to_form(exam)


@router.post("/exams", response_model=s.ExamSummaryOut, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamFormIn,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    subjects = _subjects_by_code(db)
    try:
        exam = build_exam(student, payload, subjects)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    db.add(exam)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این آزمون قبلاً با همین نام و تاریخ ثبت شده است.",
        )

    saved = _load_owned_exam(db, student.id, exam.id)
    return to_summary(saved)


@router.put("/exams/{exam_id}", response_model=s.ExamSummaryOut)
def update_exam(
    exam_id: int,
    payload: ExamFormIn,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    exam = _load_owned_exam(db, student.id, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این آزمون یافت نشد.")

    subjects = _subjects_by_code(db)
    # Validate first, so invalid input never touches the stored exam.
    try:
        build_exam(student, payload, subjects)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    try:
        # Remove old rows and flush before inserting new ones, so the unique constraints are not hit.
        exam.subject_results.clear()
        exam.notes.clear()
        db.flush()
        build_exam(student, payload, subjects, exam=exam)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="آزمونی با همین نام و تاریخ برای شما وجود دارد.",
        )

    saved = _load_owned_exam(db, student.id, exam_id)
    return to_summary(saved)


@router.delete("/exams/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exam(
    exam_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    exam = _load_owned_exam(db, student.id, exam_id)
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این آزمون یافت نشد.")
    db.delete(exam)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/progress", response_model=list[s.ProgressPointOut])
def get_progress(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    exams = db.scalars(exams_for_student(student.id)).all()
    return [to_progress_point(e) for e in exams]


@router.get("/progress/reasons", response_model=list[s.ReasonCountOut])
def get_reason_trends(student: Student = Depends(get_current_student), db: Session = Depends(get_db)):
    exams = db.scalars(exams_for_student(student.id)).all()
    return [to_reason_counts(e) for e in exams]