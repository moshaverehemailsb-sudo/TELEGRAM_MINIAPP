from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import schemas as s
from ..auth import Identity, get_identity
from ..database import get_db
from ..models import Exam, Student, Subject
from ..services.exams import exams_for_student, to_summary
from ..services.form_import import ExamFormIn, build_exam

router = APIRouter(prefix="/api/advisor", tags=["advisor"])


class StudentCreate(BaseModel):
    telegram_user_id: int = Field(gt=0)
    full_name: str = Field(min_length=2, max_length=120)


class StudentOut(BaseModel):
    id: int
    telegram_user_id: int
    full_name: str


def require_advisor(identity: Identity = Depends(get_identity)) -> Identity:
    if not identity.is_advisor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="فقط مشاوران به این بخش دسترسی دارند.",
        )
    return identity


@router.get("/students", response_model=list[StudentOut])
def list_students(_: Identity = Depends(require_advisor), db: Session = Depends(get_db)):
    students = db.scalars(select(Student).order_by(Student.full_name)).all()
    return [
        StudentOut(id=st.id, telegram_user_id=st.telegram_user_id, full_name=st.full_name)
        for st in students
    ]


@router.post("/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(
    payload: StudentCreate,
    _: Identity = Depends(require_advisor),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(Student).where(Student.telegram_user_id == payload.telegram_user_id))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="این شناسه تلگرام قبلاً ثبت شده است.",
        )
    student = Student(telegram_user_id=payload.telegram_user_id, full_name=payload.full_name.strip())
    db.add(student)
    db.commit()
    db.refresh(student)
    return StudentOut(id=student.id, telegram_user_id=student.telegram_user_id, full_name=student.full_name)


@router.post(
    "/students/{student_id}/exams",
    response_model=s.ExamSummaryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_exam(
    student_id: int,
    payload: ExamFormIn,
    _: Identity = Depends(require_advisor),
    db: Session = Depends(get_db),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="دانش‌آموز یافت نشد.")

    subjects = {subj.code: subj for subj in db.scalars(select(Subject))}
    if not subjects:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="درس‌ها در دیتابیس تعریف نشده‌اند. init_db را اجرا کنید.",
        )

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
            detail="این آزمون برای این دانش‌آموز قبلاً ثبت شده است.",
        )

    saved = db.scalar(exams_for_student(student.id).where(Exam.id == exam.id))
    return to_summary(saved)