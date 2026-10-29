import pytest

from vorge.vocab.models import UNCATEGORIZED, Vocab, parse_difficulty, split_terms


def test_normalized_strips_and_defaults_category():
    v = Vocab(word="  俯瞰 ", meaning=" 全体を見渡すこと ", category=" ").normalized()
    assert v.word == "俯瞰"
    assert v.meaning == "全体を見渡すこと"
    assert v.category == UNCATEGORIZED


def test_validate_requires_word_and_meaning():
    errors = Vocab(word="", meaning="").validate()
    assert any("語彙" in e for e in errors)
    assert any("意味" in e for e in errors)


def test_validate_difficulty_range():
    assert Vocab(word="a", meaning="b", difficulty=6).validate()
    assert not Vocab(word="a", meaning="b", difficulty=5).validate()


@pytest.mark.parametrize("value, expected", [("", 3), (None, 3), ("1", 1), (" 5 ", 5), ("4.0", 4)])
def test_parse_difficulty_ok(value, expected):
    assert parse_difficulty(value) == expected


@pytest.mark.parametrize("value", ["0", "6", "abc", "2.5"])
def test_parse_difficulty_ng(value):
    with pytest.raises(ValueError):
        parse_difficulty(value)


def test_split_terms_accepts_japanese_separators():
    assert split_terms("概観,鳥瞰、俯瞰, 展望") == ["概観", "鳥瞰", "俯瞰", "展望"]
    assert split_terms("") == []
