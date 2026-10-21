from datetime import datetime, timezone

from scripts.feed_metrics import weekly_metrics


def d(day):
    return datetime(2026, 10, day, 12, tzinfo=timezone.utc)


def test_weekly_metrics():
    # (post_id, author_id, root_id or None for a root, created_at) — week 2026-W43
    rows = [
        (10, 1, None, d(19)),   # root
        (11, 2, None, d(20)),   # root, never answered
        (12, 3, 10, d(20)),     # replies to 10
        (13, 3, 10, d(21)),
        (14, 1, 10, d(22)),
    ]
    # active: 1, 2, 3 → 3 replies / 3 = 1.0; roots answered: 1 of 2 = 0.5
    assert weekly_metrics(rows) == [("2026-W43", 1.0, 0.5)]


def test_empty():
    assert weekly_metrics([]) == []


def test_assignment_threads_are_not_conversation():
    rows = [
        (10, 1, None, d(19)),   # a tarea
        (12, 3, 10, d(20)),     # an entrega
        (20, 2, None, d(20)),   # a regular post, unanswered
    ]
    # Only post 20 counts: 1 active (author 2), 0 replies, 0 of 1 answered.
    assert weekly_metrics(rows, assignment_roots={10}) == [("2026-W43", 0.0, 0.0)]
