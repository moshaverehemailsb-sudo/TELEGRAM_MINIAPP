"""Add or re-activate an advisor. Server-side tool only.

Run from the backend folder:
  python -m scripts.add_advisor <telegram_id> "<full name>"
"""

import sys

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Advisor


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit('Usage: python -m scripts.add_advisor <telegram_id> "<full name>"')

    telegram_id = int(sys.argv[1])
    full_name = sys.argv[2].strip()

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        advisor = db.scalar(select(Advisor).where(Advisor.telegram_user_id == telegram_id))
        if advisor is None:
            db.add(Advisor(telegram_user_id=telegram_id, full_name=full_name))
            action = "added"
        else:
            advisor.is_active = True
            advisor.full_name = full_name
            action = "updated"
        db.commit()

    print(f"Advisor {action}: {telegram_id}")


if __name__ == "__main__":
    main()