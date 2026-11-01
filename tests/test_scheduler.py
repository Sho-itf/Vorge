from datetime import datetime

import pytest

from vorge import timeutil
from vorge.flashcard import scheduler
from vorge.flashcard.scheduler import CORRECT, EASY, UNSURE, WRONG, legacy_card, load_card, mastery_label

NOW = datetime(2026, 11, 1, 9, 0)


def test_first_answers_order():
    """はじめての語彙:簡単 > 正解 > 自信がない ≧ 不正解 の順に間隔が長い。"""
    days = scheduler.preview(load_card(""), NOW)
    assert days[EASY] > days[CORRECT] > days[UNSURE] >= days[WRONG] >= 1
    assert days[WRONG] == 1


def test_repeated_correct_grows():
    card, due, interval1 = scheduler.review(load_card(""), CORRECT, NOW)
    review_time = datetime.combine(due, NOW.time())
    _, _, interval2 = scheduler.review(card, CORRECT, review_time)
    assert interval2 > interval1  # 期日どおりに正解すると、間隔は大きく延びる


def test_wrong_after_long_interval_shrinks():
    card = legacy_card(30, "2026-11-01", "2026-10-02 09:00:00")
    _, _, interval = scheduler.review(card, WRONG, NOW)
    assert interval < 30


def test_legacy_card_keeps_interval_scale():
    """以前の方式の間隔(8 日)を引き継ぐので、正解すれば 8 日より長くなる。"""
    card = legacy_card(8, "2026-11-01", "2026-10-24 09:00:00")
    _, _, interval = scheduler.review(card, CORRECT, NOW)
    assert interval > 8


def test_due_date_uses_logical_day():
    """深夜 1 時の回答は前日の学習として数え、翌日以降が復習日になる。"""
    timeutil.set_day_start_hour(4)
    late = datetime(2026, 11, 2, 1, 0)
    _, due, interval = scheduler.review(load_card(""), WRONG, late)
    assert due.isoformat() == "2026-11-02" and interval == 1


def test_card_roundtrip_json():
    card, _, _ = scheduler.review(load_card(""), CORRECT, NOW)
    assert load_card(card.to_json()).stability == card.stability


def test_unknown_result():
    with pytest.raises(ValueError):
        scheduler.review(load_card(""), "maybe", NOW)


@pytest.mark.parametrize("days, label", [(None, "未学習"), (1, "学習中"), (7, "定着中"), (21, "習得")])
def test_mastery_label(days, label):
    assert mastery_label(days) == label


@pytest.mark.parametrize("days, text", [(1, "明日"), (5, "5日後"), (90, "約3か月後"), (400, "約1.1年後")])
def test_interval_text(days, text):
    assert scheduler.interval_text(days) == text
