"""Converts the advisor form payload (the same JSON index.html sends) into ORM objects.

Every value is validated here. Persian labels from the form are mapped to internal codes.
"""

import re

from pydantic import BaseModel, Field

from ..models import Exam, ExamNote, ExamSubjectResult, QuestionReason, Student, Subject
from ..reasons import REASONS

SUBJECT_CODES = {"ریاضی": "math", "فیزیک": "physics", "شیمی": "chemistry"}
REASON_CODE_BY_LABEL = {info["label"]: code for code, info in REASONS.items()}
# Same order as the three note boxes in index.html
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
) -> Exam:
    """Build (but do not save) an Exam from the form payload. Raises ValueError on bad input."""
    exam = Exam(
        student_id=student.id,
        name=payload.examName.strip(),
        held_on_text=parse_exam_date(payload.date),
        overall_traz=parse_int(payload.overallTraz, "تراز کل", required=True),
        overall_rank=parse_int(payload.overallRank, "رتبه کل", required=True),
        region_rank=parse_int(payload.regionRank, "رتبه در منطقه"),
    )

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
        exam.subject_results.append(result)

    for level, text in zip(NOTE_LEVELS, payload.notes):
        text = text.strip()
        if text:
            exam.notes.append(ExamNote(level=level, text=text))

    return exam