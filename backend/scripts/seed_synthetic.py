"""Insert SYNTHETIC development data. These are not real students.

Run from the backend folder:  python -m scripts.seed_synthetic
Dev login: send header X-Dev-Telegram-Id: 900000001 with ALLOW_DEV_AUTH=true.
"""

from sqlalchemy import select

from app import models
from app.database import Base, SessionLocal, engine

FAKE_TELEGRAM_ID = 900000001
FAKE_NAME = "دانش‌آموز نمونه"

# subject code -> (rank, correct, wrong, blank, {reason_code: [items]})
EXAMS = [
    {
        "name": "آزمون آزمایشی ۱",
        "held_on_text": "1405/01/10",
        "overall_traz": 10850,
        "overall_rank": 420,
        "region_rank": 60,
        "subjects": {
            "math": (520, 14, 8, 8, {"careless": ["3، 7"], "budget": ["12، 15، 18"]}),
            "physics": (610, 17, 6, 7, {"knowledge_gap": ["4، 9"], "time": ["20، 22"]}),
            "chemistry": (380, 19, 4, 7, {"lucky": ["5"], "unsolved": ["25، 26"]}),
        },
        "notes": {"from_scratch": "ترمودینامیک", "more_practice": "مسائل حرکت", "review": "استوکیومتری"},
    },
    {
        "name": "آزمون آزمایشی ۲",
        "held_on_text": "1405/02/05",
        "overall_traz": 11320,
        "overall_rank": 310,
        "region_rank": 41,
        "subjects": {
            "math": (430, 16, 5, 9, {"careless": ["7"], "budget": ["20، 21"]}),
            "physics": (540, 18, 5, 7, {"knowledge_gap": ["11"], "long_solution": ["2"]}),
            "chemistry": (300, 22, 3, 5, {"time": ["24"]}),
        },
        "notes": {"more_practice": "مسائل حرکت", "review": "ترمودینامیک"},
    },
    {
        "name": "آزمون آزمایشی ۳",
        "held_on_text": "1405/03/12",
        "overall_traz": 11890,
        "overall_rank": 215,
        "region_rank": 28,
        "subjects": {
            "math": (340, 19, 4, 7, {"careless": ["14"], "unsolved": ["29"]}),
            "physics": (470, 20, 4, 6, {"knowledge_gap": ["15"]}),
            "chemistry": (240, 24, 2, 4, {"lucky": ["8"]}),
        },
        "notes": {"review": "استوکیومتری"},
    },
]


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        subjects = {s.code: s for s in db.scalars(select(models.Subject))}
        if not subjects:
            raise SystemExit("Run `python -m scripts.init_db` first.")

        student = db.scalar(
            select(models.Student).where(models.Student.telegram_user_id == FAKE_TELEGRAM_ID)
        )
        if student is None:
            student = models.Student(telegram_user_id=FAKE_TELEGRAM_ID, full_name=FAKE_NAME)
            db.add(student)
            db.flush()

        # Recreate this synthetic student's exams so the script can be re-run safely.
        for old in list(student.exams):
            db.delete(old)
        db.flush()

        for item in EXAMS:
            exam = models.Exam(
                student_id=student.id,
                name=item["name"],
                held_on_text=item["held_on_text"],
                overall_traz=item["overall_traz"],
                overall_rank=item["overall_rank"],
                region_rank=item["region_rank"],
            )
            for code, (rank, ok, bad, blank, reasons) in item["subjects"].items():
                result = models.ExamSubjectResult(
                    subject=subjects[code],
                    rank=rank,
                    correct_count=ok,
                    wrong_count=bad,
                    blank_count=blank,
                )
                for reason_code, refs in reasons.items():
                    for ref in refs:
                        result.reasons.append(
                            models.QuestionReason(reason_code=reason_code, item_ref=ref)
                        )
                exam.subject_results.append(result)
            for level, text in item["notes"].items():
                exam.notes.append(models.ExamNote(level=level, text=text))
            student.exams.append(exam)

        db.commit()
    print(f"Seeded synthetic student (telegram id {FAKE_TELEGRAM_ID}) with {len(EXAMS)} exams.")


if __name__ == "__main__":
    main()