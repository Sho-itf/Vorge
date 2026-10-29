from datetime import date, datetime, timedelta

import pytest

from vorge.flashcard import session
from vorge.flashcard.repository import ReviewRepository
from vorge.flashcard.scheduler import CORRECT, UNSURE, WRONG
from vorge.history.repository import HistoryRepository
from vorge.vocab.models import Vocab

DAY1 = date(2026, 11, 1)


def at(day: date, hour: int = 9) -> datetime:
    return datetime(day.year, day.month, day.day, hour)


@pytest.fixture
def review(repo):
    return ReviewRepository(repo.db_path)


@pytest.fixture
def history(repo):
    return HistoryRepository(repo.db_path)


def add(repo, word):
    return repo.add(Vocab(word=word, meaning=f"{word}の意味"))


def test_empty_history(history):
    assert history.total_answers() == 0
    assert history.streak(DAY1) == 0
    assert history.accuracy_between(DAY1, DAY1) is None
    assert history.weak_vocab() == []


def test_daily_counts_fill_missing_days(repo, review, history):
    a = add(repo, "A")
    review.record_answer(a, CORRECT, now=at(DAY1))
    review.record_answer(a, WRONG, now=at(DAY1, 10))
    review.record_answer(a, UNSURE, now=at(DAY1 + timedelta(days=2)))

    daily = history.daily_counts(DAY1, DAY1 + timedelta(days=2))
    assert [d.total for d in daily] == [2, 0, 1]
    assert (daily[0].correct, daily[0].wrong, daily[2].unsure) == (1, 1, 1)


def test_accuracy_excludes_unsure(repo, review, history):
    a = add(repo, "A")
    for result in (CORRECT, UNSURE, WRONG, CORRECT):
        review.record_answer(a, result, now=at(DAY1))
    assert history.accuracy_between(DAY1, DAY1) == 0.5


def test_streak(repo, review, history):
    a = add(repo, "A")
    for offset in (0, 1, 2, 4):  # 11/1, 11/2, 11/3, 11/5
        review.record_answer(a, CORRECT, now=at(DAY1 + timedelta(days=offset)))
    assert history.streak(date(2026, 11, 3)) == 3
    assert history.streak(date(2026, 11, 5)) == 1
    # 今日まだ学習していなくても、昨日まで続いていれば数える
    assert history.streak(date(2026, 11, 4)) == 3
    assert history.streak(date(2026, 11, 7)) == 0


def test_mastery_distribution(repo, review, history):
    a, b = add(repo, "A"), add(repo, "B")
    add(repo, "C")
    review.record_answer(a, CORRECT, now=at(DAY1))  # 3日 → 学習中
    for _ in range(2):
        review.record_answer(b, CORRECT, now=at(DAY1))  # 3 → 8日 → 定着中
    assert history.mastery_distribution() == {"未学習": 1, "学習中": 1, "定着中": 1, "習得": 0}


def test_upcoming_reviews_include_overdue_today(repo, review, history):
    a, b = add(repo, "A"), add(repo, "B")
    review.record_answer(a, WRONG, now=at(DAY1))  # 11/2 が復習日
    review.record_answer(b, CORRECT, now=at(DAY1))  # 11/4 が復習日
    upcoming = dict(history.upcoming_reviews(date(2026, 11, 3), 3))
    assert upcoming == {date(2026, 11, 3): 1, date(2026, 11, 4): 1, date(2026, 11, 5): 0}


def test_weak_vocab_order(repo, review, history):
    good, bad, mid = add(repo, "得意"), add(repo, "苦手"), add(repo, "普通")
    review.record_answer(good, CORRECT, now=at(DAY1))
    review.record_answer(bad, WRONG, now=at(DAY1))
    review.record_answer(bad, WRONG, now=at(DAY1))
    review.record_answer(mid, CORRECT, now=at(DAY1))
    review.record_answer(mid, UNSURE, now=at(DAY1))

    weak = history.weak_vocab()
    assert [w.word for w in weak] == ["苦手", "普通"]  # 全問正解の語彙は含まない
    assert weak[0].accuracy == 0
    assert weak[1].accuracy == 0.5


def test_recent_logs(repo, review, history):
    a = add(repo, "A")
    review.record_answer(a, CORRECT, now=at(DAY1))
    review.record_answer(a, WRONG, now=at(DAY1, 10))
    logs = history.recent_logs()
    assert [r["result"] for r in logs] == [WRONG, CORRECT]
    assert logs[0]["word"] == "A"


def test_session_start_and_reset():
    state: dict = {}
    session.init(state)
    assert state["fc_queue"] is None
    session.start(state, [3, 1], "meaning_to_word", label="苦手な語彙")
    assert (state["fc_queue"], state["fc_pos"], state["fc_label"]) == ([3, 1], 0, "苦手な語彙")
    session.reset(state)
    assert state["fc_queue"] is None
