"""Create tables and the base subject rows.

Run from the backend folder:  python -m scripts.init_db
"""

from sqlalchemy import select

from app import models
from app.database import Base, SessionLocal, engine

SUBJECTS = [
    ("math", "ریاضی", 1),
    ("physics", "فیزیک", 2),
    ("chemistry", "شیمی", 3),
]


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for code, name_fa, order in SUBJECTS:
            exists = db.scalar(select(models.Subject).where(models.Subject.code == code))
            if exists is None:
                db.add(models.Subject(code=code, name_fa=name_fa, sort_order=order))
        db.commit()
    print("Database is ready.")


if __name__ == "__main__":
    main()