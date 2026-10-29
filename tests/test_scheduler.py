import pytest

from vorge.flashcard.scheduler import (
    CORRECT,
    MAX_INTERVAL,
    UNSURE,
    WRONG,
    mastery_label,
    next_interval,
)


def test_correct_extends_interval():
    # 初回(None)は 1 日扱い → 3 → 8 → 20
    assert next_interval(None, CORRECT) == 3
    assert next_interval(3, CORRECT) == 8
    assert next_interval(8, CORRECT) == 20


def test_unsure_keeps_interval():
    assert next_interval(None, UNSURE) == 1
    assert next_interval(8, UNSURE) == 8


def test_wrong_resets_to_one_day():
    assert next_interval(20, WRONG) == 1


def test_interval_has_upper_limit():
    assert next_interval(300, CORRECT) == MAX_INTERVAL


def test_unknown_result():
    with pytest.raises(ValueError):
        next_interval(1, "maybe")


@pytest.mark.parametrize(
    "days, label", [(None, "未学習"), (1, "学習中"), (7, "定着中"), (21, "習得")]
)
def test_mastery_label(days, label):
    assert mastery_label(days) == label
