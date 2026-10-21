# backend/tests/test_feed_rank.py
from datetime import datetime, timedelta, timezone

import pytest

from app.services.feed_rank import Candidate, ReplyFact, rank, score

AS_OF = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
ME, ANA, LUIS = 1, 2, 3


def ago(hours):
    return AS_OF - timedelta(hours=hours)


def post(pid, author=ANA, age=0, replies=()):
    return Candidate(pid, author, ago(age), tuple(replies))


def reply(author, age, parent_author=ANA, active=True):
    return ReplyFact(author, ago(age), parent_author, active)


def test_newer_beats_older():
    assert rank([post(1, age=10), post(2, age=1)], ME, {}, AS_OF) == [2, 1]


def test_ties_break_on_post_id_descending():
    assert rank([post(1), post(2)], ME, {}, AS_OF) == [2, 1]


def test_aura_sinks_by_exactly_one_half_life():
    liked = score(post(1, age=0), ME, ago(0), AS_OF)
    day_old = score(post(2, age=24), ME, None, AS_OF)
    assert liked == pytest.approx(day_old)


def test_a_reply_sinks_by_three_half_lives():
    replied = score(post(1, age=0, replies=[reply(ME, 0)]), ME, None, AS_OF)
    # Activity from the viewer's own reply never counts, so only freshness is left.
    assert replied == pytest.approx(score(post(2, age=72), ME, None, AS_OF))


def test_authoring_counts_as_a_reply():
    mine = score(post(1, author=ME, age=0), ME, None, AS_OF)
    assert mine == pytest.approx(score(post(2, age=72), ME, None, AS_OF))


def test_a_reply_to_me_brings_my_post_above_a_fresh_one():
    mine = post(1, author=ME, age=48, replies=[reply(ANA, 0, parent_author=ME)])
    fresh = post(2, author=LUIS, age=0)
    assert rank([fresh, mine], ME, {}, AS_OF) == [1, 2]


def test_a_reply_in_my_thread_lifts_less_than_a_reply_to_me():
    # I commented on Luis's post; Ana then answers either me or Luis.
    to_me = post(1, author=LUIS, age=48,
                 replies=[reply(ME, 30, parent_author=LUIS), reply(ANA, 0, parent_author=ME)])
    in_thread = post(2, author=LUIS, age=48,
                     replies=[reply(ME, 30, parent_author=LUIS), reply(ANA, 0, parent_author=LUIS)])
    assert score(to_me, ME, None, AS_OF) > score(in_thread, ME, None, AS_OF)
    untouched_lift = score(post(3, author=LUIS, age=48,
                                replies=[reply(ME, 30, parent_author=LUIS)]), ME, None, AS_OF)
    assert score(in_thread, ME, None, AS_OF) > untouched_lift


def test_aura_alone_does_not_subscribe():
    c = post(1, age=10, replies=[reply(LUIS, 0)])
    with_aura = score(c, ME, ago(5), AS_OF)
    without = score(c, ME, None, AS_OF)
    assert with_aura == pytest.approx(without * 0.5)


def test_replies_before_my_touch_do_not_lift():
    c = post(1, author=LUIS, age=48,
             replies=[reply(ANA, 40, parent_author=ME), reply(ME, 30, parent_author=LUIS)])
    # Ana's reply predates my last touch, so it only adds activity.
    assert score(c, ME, None, AS_OF) < score(post(2, age=0), ME, None, AS_OF)


def test_my_own_replies_are_not_activity():
    lonely = score(post(1, age=5), ME, None, AS_OF)
    busy_with_me = score(post(1, age=5, replies=[reply(ME, 1)] * 5), ME, None, AS_OF)
    assert busy_with_me < lonely  # only the penalty applied, no activity gained


def test_inactive_replies_count_for_nothing():
    plain = score(post(1, age=5), ME, None, AS_OF)
    gone = score(post(1, age=5, replies=[reply(ANA, 1, active=False)]), ME, None, AS_OF)
    assert gone == pytest.approx(plain)


def test_activity_is_concave():
    one = score(post(1, age=5, replies=[reply(ANA, 1)]), ME, None, AS_OF)
    thirty = score(post(1, age=5, replies=[reply(ANA, 1)] * 30), ME, None, AS_OF)
    assert thirty < one * 5


def test_touches_and_replies_after_as_of_are_ignored():
    c = post(1, age=5, replies=[ReplyFact(ANA, AS_OF + timedelta(minutes=1), ANA, True)])
    assert score(c, ME, AS_OF + timedelta(minutes=1), AS_OF) == pytest.approx(
        score(post(1, age=5), ME, None, AS_OF))


from app.services.feed_rank import ReplyOption, pick_featured  # noqa: E402


def opt(pid, age=0, likes=0, teacher=False):
    return ReplyOption(pid, ago(age), likes, teacher)


def test_no_replies_no_featured():
    assert pick_featured([]) is None


def test_teacher_aura_beats_more_aura():
    assert pick_featured([opt(1, likes=9), opt(2, likes=1, teacher=True)]) == 2


def test_more_aura_beats_recency():
    assert pick_featured([opt(1, age=0, likes=1), opt(2, age=5, likes=3)]) == 2


def test_recency_breaks_an_aura_tie():
    assert pick_featured([opt(1, age=5, likes=2), opt(2, age=1, likes=2)]) == 2


def test_id_breaks_a_full_tie():
    assert pick_featured([opt(1), opt(2)]) == 2
