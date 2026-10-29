from app.services.mentions import parse_usernames


def test_finds_mentions_in_order_lowercased_and_unique():
    assert parse_usernames("con @Ana y @pedro_2, otra vez @ana") == ["ana", "pedro_2"]


def test_an_email_is_not_a_mention():
    assert parse_usernames("escríbeme a pedro@gmail.com") == []


def test_too_short_lone_or_glued_at_signs_are_not_mentions():
    assert parse_usernames("@ab @ hola@@x a@pedro") == []


def test_mention_at_start_after_punctuation_and_newline():
    assert parse_usernames("@ana\n(@luis) ¡@pedro!") == ["ana", "luis", "pedro"]


def test_more_than_twenty_characters_is_not_a_username():
    assert parse_usernames("@" + "a" * 21) == []
