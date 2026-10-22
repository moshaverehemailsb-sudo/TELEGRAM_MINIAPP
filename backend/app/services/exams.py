"""Turns ORM objects into API responses. Shared by student and advisor routes."""

from sqlalchemy import Select, select
from sqlalchemy.orm import selectinload

from .. import schemas as s
from ..models import Exam, ExamSubjectResult, QuestionReason
from ..reasons import NOTE_LABELS, REASONS


def exams_for_student(student_id: int) -> Select:
    """Query that only ever returns exams owned by student_id."""
    return (
        select(Exam)
        .where(Exam.student_id == student_id)
        .options(
            selectinload(Exam.subject_results).selectinload(ExamSubjectResult.subject),
            selectinload(Exam.subject_results).selectinload(ExamSubjectResult.reasons),
            selectinload(Exam.notes),
        )
        .order_by(Exam.held_on_text, Exam.id)
    )


def _totals(exam: Exam) -> s.ExamTotals:
    return s.ExamTotals(
        correct=sum(r.correct_count for r in exam.subject_results),
        wrong=sum(r.wrong_count for r in exam.subject_results),
        blank=sum(r.blank_count for r in exam.subject_results),
    )


def _group_reasons(reasons: list[QuestionReason]) -> list[s.ReasonOut]:
    grouped: dict[str, list[str]] = {}
    for reason in reasons:
        grouped.setdefault(reason.reason_code, []).append(reason.item_ref)
    return [
        s.ReasonOut(code=code, label=REASONS[code]["label"], items=grouped[code])
        for code in REASONS
        if code in grouped
    ]


def to_summary(exam: Exam) -> s.ExamSummaryOut:
    return s.ExamSummaryOut(
        id=exam.id,
        name=exam.name,
        held_on=exam.held_on_text,
        overall_traz=exam.overall_traz,
        overall_rank=exam.overall_rank,
        region_rank=exam.region_rank,
        totals=_totals(exam),
    )


def to_detail(exam: Exam) -> s.ExamDetailOut:
    subjects = [
        s.SubjectResultOut(
            subject_code=r.subject.code,
            subject_name=r.subject.name_fa,
            rank=r.rank,
            correct=r.correct_count,
            wrong=r.wrong_count,
            blank=r.blank_count,
            reasons=_group_reasons(r.reasons),
        )
        for r in sorted(exam.subject_results, key=lambda r: r.subject.sort_order)
    ]
    notes = [
        s.NoteOut(level=n.level, label=NOTE_LABELS.get(n.level, n.level), text=n.text)
        for n in exam.notes
    ]
    return s.ExamDetailOut(**to_summary(exam).model_dump(), subjects=subjects, notes=notes)


def to_progress_point(exam: Exam) -> s.ProgressPointOut:
    summary = to_summary(exam)
    return s.ProgressPointOut(
        exam_id=exam.id,
        exam_name=exam.name,
        held_on=exam.held_on_text,
        overall_traz=summary.overall_traz,
        overall_rank=summary.overall_rank,
        region_rank=summary.region_rank,
        totals=summary.totals,
        subjects={
            r.subject.code: s.SubjectPointOut(
                rank=r.rank, correct=r.correct_count, wrong=r.wrong_count, blank=r.blank_count
            )
            for r in exam.subject_results
        },
    )


def to_reason_counts(exam: Exam) -> s.ReasonCountOut:
    """Number of reason entries per code for one exam (entries, not questions)."""
    counts = {code: 0 for code in REASONS}
    for result in exam.subject_results:
        for reason in result.reasons:
            counts[reason.reason_code] = counts.get(reason.reason_code, 0) + 1
    return s.ReasonCountOut(
        exam_id=exam.id, exam_name=exam.name, held_on=exam.held_on_text, counts=counts
    )