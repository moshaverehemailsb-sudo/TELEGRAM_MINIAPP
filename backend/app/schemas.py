from pydantic import BaseModel


class ExamTotals(BaseModel):
    correct: int
    wrong: int
    blank: int


class ReasonOut(BaseModel):
    code: str
    label: str
    items: list[str]


class SubjectResultOut(BaseModel):
    subject_code: str
    subject_name: str
    rank: int | None
    correct: int
    wrong: int
    blank: int
    reasons: list[ReasonOut]


class NoteOut(BaseModel):
    level: str
    label: str
    text: str


class ExamSummaryOut(BaseModel):
    id: int
    name: str
    held_on: str
    overall_traz: int | None
    overall_rank: int | None
    region_rank: int | None
    totals: ExamTotals


class ExamDetailOut(ExamSummaryOut):
    subjects: list[SubjectResultOut]
    notes: list[NoteOut]


class StudentOut(BaseModel):
    full_name: str
    is_advisor: bool
    exam_count: int


class SubjectPointOut(BaseModel):
    rank: int | None
    correct: int
    wrong: int
    blank: int


class ProgressPointOut(BaseModel):
    exam_id: int
    exam_name: str
    held_on: str
    overall_traz: int | None
    overall_rank: int | None
    region_rank: int | None
    totals: ExamTotals
    subjects: dict[str, SubjectPointOut]


class ReasonCountOut(BaseModel):
    exam_id: int
    exam_name: str
    held_on: str
    counts: dict[str, int]