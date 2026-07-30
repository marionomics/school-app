from datetime import timedelta
from decimal import Decimal

from app.models import PointsLedger


def _row(db, user, klass, st, sid, pts, revoked=False):
    from app.models import utcnow
    r = PointsLedger(user_id=user.id, class_id=klass.id, source_type=st,
                     source_id=sid, points=Decimal(str(pts)))
    if revoked:
        r.revoked_at = utcnow()
    db.add(r)
    db.commit()
    return r


def test_grade_totals_ignore_revoked(client, db, auth_headers, enrolled, klass, student):
    _row(db, student, klass, "participacion", 1, 2.0)
    _row(db, student, klass, "forum_like", 10, 1.0)
    _row(db, student, klass, "forum_like", 11, 1.0, revoked=True)
    res = client.get(f"/api/students/me/grade?class_id={klass.id}", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 3.0
    assert body["counts"] == {"participaciones": 1, "likes_received": 1}
    assert len(body["events"]) == 2


def test_grade_all_classes_list(client, auth_headers, enrolled, klass):
    res = client.get("/api/students/me/grade", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list) and body[0]["class_id"] == klass.id
    assert body[0]["total"] == 0.0


def test_grade_404_when_not_enrolled(client, auth_headers, klass):
    res = client.get(f"/api/students/me/grade?class_id={klass.id}", headers=auth_headers)
    assert res.status_code == 404


def test_grade_events_are_newest_first(client, db, auth_headers, enrolled, klass, student):
    from app.models import utcnow
    base = utcnow()
    # insert oldest first, newest last, with explicit timestamps
    for i in range(3):
        r = PointsLedger(user_id=student.id, class_id=klass.id, source_type="forum_like",
                         source_id=100 + i, points=Decimal("1.0"))
        r.created_at = base + timedelta(minutes=i)  # i=2 is newest
        db.add(r)
    db.commit()
    res = client.get(f"/api/students/me/grade?class_id={klass.id}", headers=auth_headers)
    events = res.json()["events"]
    times = [e["created_at"] for e in events]
    assert times == sorted(times, reverse=True)  # newest-first


def test_grade_events_capped_at_50(client, db, auth_headers, enrolled, klass, student):
    for i in range(55):
        db.add(PointsLedger(user_id=student.id, class_id=klass.id, source_type="forum_like",
                            source_id=200 + i, points=Decimal("1.0")))
    db.commit()
    res = client.get(f"/api/students/me/grade?class_id={klass.id}", headers=auth_headers)
    body = res.json()
    assert len(body["events"]) == 50          # events capped
    assert body["counts"]["likes_received"] == 55  # but counts reflect all non-revoked rows
    assert body["total"] == 55.0              # and total reflects all non-revoked rows
