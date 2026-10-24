from datetime import datetime, timedelta, timezone

from app.models import Advisor, AdvisorStudent, Exam, InviteCode, Student
from app.services.invites import hash_code

ADMIN = {"X-Dev-Telegram-Id": "1000"}  # must match ADMIN_TELEGRAM_IDS in conftest.py


def H(tg_id: int) -> dict:
    return {"X-Dev-Telegram-Id": str(tg_id)}


def make_student(db, tg_id, name="دانش‌آموز تست"):
    st = Student(telegram_user_id=tg_id, full_name=name)
    db.add(st)
    db.commit()
    db.refresh(st)
    return st


def make_advisor(db, tg_id, name="مشاور تست"):
    adv = Advisor(telegram_user_id=tg_id, full_name=name, is_active=True)
    db.add(adv)
    db.commit()
    db.refresh(adv)
    return adv


def make_exam(db, student, name="آزمون", held="1405/01/10"):
    exam = Exam(
        student_id=student.id,
        name=name,
        held_on_text=held,
        overall_traz=10000,
        overall_rank=100,
        region_rank=10,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


def link(db, advisor, student):
    db.add(AdvisorStudent(advisor_id=advisor.id, student_id=student.id, is_active=True))
    db.commit()


def make_invite(db, advisor, code, expires_in=timedelta(days=7)):
    db.add(
        InviteCode(
            advisor_id=advisor.id,
            code_hash=hash_code(code),
            expires_at=datetime.now(timezone.utc) + expires_in,
        )
    )
    db.commit()


def redeem(client, tg_id, code):
    return client.post("/api/me/advisor/redeem", json={"code": code}, headers=H(tg_id))


# ---------- Unauthenticated access ----------

def test_health_is_public(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_requests_without_identity_are_rejected(client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/advisor/students").status_code == 401
    assert client.get("/api/admin/advisors").status_code == 401


# ---------- Role separation ----------

def test_student_cannot_use_advisor_or_admin_areas(client, db):
    make_student(db, 2001)
    assert client.get("/api/advisor/students", headers=H(2001)).status_code == 403
    assert client.get("/api/admin/advisors", headers=H(2001)).status_code == 403
    assert client.post("/api/advisor/invites", headers=H(2001)).status_code == 403


def test_advisor_cannot_use_admin_area(client, db):
    make_advisor(db, 3001)
    assert client.get("/api/admin/advisors", headers=H(3001)).status_code == 403


def test_admin_cannot_use_advisor_area(client):
    assert client.get("/api/advisor/students", headers=ADMIN).status_code == 403


def test_admin_without_student_record_has_no_student_profile(client):
    assert client.get("/api/me", headers=ADMIN).status_code == 404


def test_student_registration_happens_once(client):
    first = client.post("/api/me/register", json={"full_name": "علی تست"}, headers=H(2001))
    assert first.status_code == 201
    second = client.post("/api/me/register", json={"full_name": "علی تست"}, headers=H(2001))
    assert second.status_code == 409


# ---------- Student data isolation ----------

def test_student_cannot_read_another_students_exam(client, db):
    make_student(db, 2001)
    other = make_student(db, 2002)
    exam_of_other = make_exam(db, other)

    assert client.get(f"/api/exams/{exam_of_other.id}", headers=H(2001)).status_code == 404
    assert client.get(f"/api/exams/{exam_of_other.id}", headers=H(2002)).status_code == 200


# ---------- Advisor sees only linked students ----------

def test_advisor_sees_only_linked_students(client, db):
    adv = make_advisor(db, 3001)
    make_advisor(db, 3002, name="مشاور دیگر")
    st = make_student(db, 2001)
    make_exam(db, st)
    link(db, adv, st)

    assert client.get(f"/api/advisor/students/{st.id}/exams", headers=H(3001)).status_code == 200
    assert client.get(f"/api/advisor/students/{st.id}/exams", headers=H(3002)).status_code == 404


def test_advisor_exam_detail_requires_link(client, db):
    adv = make_advisor(db, 3001)
    st = make_student(db, 2001)
    exam = make_exam(db, st)

    assert client.get(f"/api/advisor/exams/{exam.id}", headers=H(3001)).status_code == 404
    link(db, adv, st)
    assert client.get(f"/api/advisor/exams/{exam.id}", headers=H(3001)).status_code == 200


def test_admin_sees_students_without_subject_details(client, db):
    adv = make_advisor(db, 3001)
    st = make_student(db, 2001)
    make_exam(db, st)
    link(db, adv, st)

    resp = client.get(f"/api/admin/advisors/{adv.id}/students", headers=ADMIN)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["exam_count"] == 1
    assert "subjects" not in body[0]


# ---------- Invite codes ----------

def test_invite_code_links_student_and_is_single_use(client, db):
    adv = make_advisor(db, 3001)
    make_student(db, 2001)
    make_invite(db, adv, "ABCD-2345")

    first = redeem(client, 2001, "ABCD-2345")
    assert first.status_code == 200
    assert first.json()["full_name"] == "مشاور تست"

    again = redeem(client, 2001, "ABCD-2345")
    assert again.status_code == 400


def test_used_code_cannot_be_reused_by_another_student(client, db):
    adv = make_advisor(db, 3001)
    make_student(db, 2001)
    make_student(db, 2002)
    make_invite(db, adv, "ABCD-2345")

    assert redeem(client, 2001, "ABCD-2345").status_code == 200
    assert redeem(client, 2002, "ABCD-2345").status_code == 400


def test_expired_code_is_rejected(client, db):
    adv = make_advisor(db, 3001)
    make_student(db, 2001)
    make_invite(db, adv, "WXYZ-2345", expires_in=timedelta(days=-1))

    assert redeem(client, 2001, "WXYZ-2345").status_code == 400


def test_invalid_code_format_is_rejected(client, db):
    make_student(db, 2001)
    assert redeem(client, 2001, "AAAA-0000").status_code == 400  # 0 is not in the alphabet


def test_switching_advisor_removes_old_access(client, db):
    a1 = make_advisor(db, 3001)
    a2 = make_advisor(db, 3002, name="مشاور دوم")
    st = make_student(db, 2001)
    make_exam(db, st)
    make_invite(db, a1, "ABCD-2345")
    make_invite(db, a2, "WXYZ-2345")

    assert redeem(client, 2001, "ABCD-2345").status_code == 200
    assert client.get(f"/api/advisor/students/{st.id}/exams", headers=H(3001)).status_code == 200

    assert redeem(client, 2001, "WXYZ-2345").status_code == 200
    assert client.get(f"/api/advisor/students/{st.id}/exams", headers=H(3001)).status_code == 404
    assert client.get(f"/api/advisor/students/{st.id}/exams", headers=H(3002)).status_code == 200


def test_redeeming_same_advisor_twice_is_a_conflict(client, db):
    adv = make_advisor(db, 3001)
    make_student(db, 2001)
    make_invite(db, adv, "ABCD-2345")
    make_invite(db, adv, "WXYZ-2345")

    assert redeem(client, 2001, "ABCD-2345").status_code == 200
    assert redeem(client, 2001, "WXYZ-2345").status_code == 409


# ---------- Unlinking ----------

def test_student_unlink_removes_advisor_access_but_keeps_exams(client, db):
    adv = make_advisor(db, 3001)
    st = make_student(db, 2001)
    make_exam(db, st)
    link(db, adv, st)

    assert client.delete("/api/me/advisor", headers=H(2001)).status_code == 204
    assert client.get(f"/api/advisor/students/{st.id}/exams", headers=H(3001)).status_code == 404
    assert client.get("/api/me/advisor", headers=H(2001)).json() is None
    assert len(client.get("/api/exams", headers=H(2001)).json()) == 1


def test_deactivating_advisor_frees_students_and_blocks_new_codes(client, db):
    adv = make_advisor(db, 3001)
    st = make_student(db, 2001)
    link(db, adv, st)

    resp = client.patch(f"/api/admin/advisors/{adv.id}", json={"is_active": False}, headers=ADMIN)
    assert resp.status_code == 200

    assert client.get("/api/me/advisor", headers=H(2001)).json() is None
    assert client.get("/api/advisor/students", headers=H(3001)).status_code == 403

    make_invite(db, adv, "ABCD-2345")
    assert redeem(client, 2001, "ABCD-2345").status_code == 400