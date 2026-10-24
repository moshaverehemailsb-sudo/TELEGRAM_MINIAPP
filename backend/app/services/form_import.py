"""Converts the exam form payload (the JSON the form sends) into ORM objects.

Used by the student entry form (create and edit) and to load an exam back into the form.
"""

import re

from pydantic import BaseModel, Field

from ..models import Exam, ExamNote, ExamSubjectResult, QuestionReason, Student, Subject
from ..reasons import REASONS

SUBJECT_CODES = {"ریاضی": "math", "فیزیک": "physics", "شیمی": "chemistry"}
SUBJECT_NAME_BY_CODE = {code: name for name, code in SUBJECT_CODES.items()}
REASON_CODE_BY_LABEL = {info["label"]: code for code, info in REASONS.items()}
# Same order as the three note boxes in the form
NOTE_LEVELS = ["from_scratch", "more_practice", "review"]

# Persian (U+06F0..) and Arabic-Indic (U+0660..) digits -> ASCII digits
_DIGIT_MAP = {
    **{ord(chr(0x06F0 + i)): str(i) for i in range(10)},
    **{ord(chr(0x0660 + i)): str(i) for i in range(10)},
}
_DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")


class SubjectFormIn(BaseModel):
    name: str
    rank: str = ""
    ok: int = Field(ge=0, le=200)
    bad: int = Field(ge=0, le=200)
    blank: int = Field(ge=0, le=200)
    reasons: dict[str, list[str]] = {}


class ExamFormIn(BaseModel):
    examName: str = Field(min_length=1, max_length=120)
    date: str = Field(min_length=1, max_length=20)
    overallTraz: str = ""
    overallRank: str = ""
    regionRank: str = ""
    subjects: list[SubjectFormIn] = Field(min_length=1, max_length=3)
    notes: list[str] = []


def normalize_digits(value: str) -> str:
    return value.translate(_DIGIT_MAP).strip()


def parse_int(value: str, field: str, required: bool = False) -> int | None:
    text = normalize_digits(value).replace(",", "").replace("،", "")
    if not text:
        if required:
            raise ValueError(f"{field} الزامی است.")
        return None
    if not text.isdigit():
        raise ValueError(f"{field} باید فقط عدد باشد.")
    return int(text)


def parse_exam_date(value: str) -> str:
    text = normalize_digits(value)
    if not _DATE_RE.match(text):
        raise ValueError("تاریخ آزمون باید به شکل 1405/01/10 باشد.")
    _, month, day = (int(part) for part in text.split("/"))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError("ماه یا روز تاریخ آزمون معتبر نیست.")
    return text


def build_exam(
    student: Student,
    payload: ExamFormIn,
    subjects_by_code: dict[str, Subject],
    exam: Exam | None = None,
) -> Exam:
    """Fill `exam` (or a new Exam) from the payload.

    When updating, the caller must clear the old subject_results and notes first.
    Raises ValueError on invalid input.
    """
    target = exam if exam is not None else Exam(student_id=student.id)
    target.name = payload.examName.strip()
    target.held_on_text = parse_exam_date(payload.date)
    target.overall_traz = parse_int(payload.overallTraz, "تراز کل", required=True)
    target.overall_rank = parse_int(payload.overallRank, "رتبه کل", required=True)
    target.region_rank = parse_int(payload.regionRank, "رتبه در منطقه")

    seen_codes: set[str] = set()
    for item in payload.subjects:
        name = item.name.strip()
        code = SUBJECT_CODES.get(name)
        if code is None:
            raise ValueError(f"نام درس نامعتبر است: {name}")
        if code in seen_codes:
            raise ValueError(f"درس «{name}» بیش از یک بار ثبت شده است.")
        seen_codes.add(code)

        result = ExamSubjectResult(
            subject=subjects_by_code[code],
            rank=parse_int(item.rank, f"رتبه {name}"),
            correct_count=item.ok,
            wrong_count=item.bad,
            blank_count=item.blank,
        )
        for label, refs in item.reasons.items():
            reason_code = REASON_CODE_BY_LABEL.get(label.strip())
            if reason_code is None:
                raise ValueError(f"دلیل نامعتبر است: {label}")
            for ref in refs:
                ref = ref.strip()
                if ref:
                    result.reasons.append(QuestionReason(reason_code=reason_code, item_ref=ref[:200]))
        target.subject_results.append(result)

    for level, text in zip(NOTE_LEVELS, payload.notes):
        text = text.strip()
        if text:
            target.notes.append(ExamNote(level=level, text=text))

    return target


def export_exam_to_form(exam: Exam) -> dict:
    """Return the same JSON shape the form sends, so an exam can be loaded for editing."""
    subjects = []
    for result in sorted(exam.subject_results, key=lambda r: r.subject.sort_order):
        reasons: dict[str, list[str]] = {}
        for reason in result.reasons:
            label = REASONS[reason.reason_code]["label"]
            reasons.setdefault(label, []).append(reason.item_ref)
        subjects.append(
            {
                "name": SUBJECT_NAME_BY_CODE[result.subject.code],
                "rank": "" if result.rank is None else str(result.rank),
                "ok": result.correct_count,
                "bad": result.wrong_count,
                "blank": result.blank_count,
                "reasons": reasons,
            }
        )

    notes_by_level = {note.level: note.text for note in exam.notes}
    return {
        "id": exam.id,
        "examName": exam.name,
        "date": exam.held_on_text,
        "overallTraz": "" if exam.overall_traz is None else str(exam.overall_traz),
        "overallRank": "" if exam.overall_rank is None else str(exam.overall_rank),
        "regionRank": "" if exam.region_rank is None else str(exam.region_rank),
        "subjects": subjects,
        "notes": [notes_by_level.get(level, "") for level in NOTE_LEVELS],
    }