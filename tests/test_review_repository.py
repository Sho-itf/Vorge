from datetime import date, datetime, timedelta

import pytest

from vorge.db import get_connection
from vorge.flashcard.repository import ReviewRepository
from vorge.flashcard.scheduler import CORRECT, EASY, WRONG
from vorge.vocab.models import Vocab

DAY1 = datetime(2026, 11, 1, 9, 0)


@pytest.fixture
def review(repo):
    return ReviewRepository(repo.db_path)


def add(repo, word="俯瞰", **kw):
    return repo.add(Vocab(word=word, meaning="意味", **kw))


def test_record_answer_updates_state_and_log(repo, review):
    vid = add(repo)
    state = review.record_answer(vid, CORRECT, now=DAY1)
    assert state.interval_days >= 1
    assert state.next_review == (DAY1.date() + timedelta(days=state.interval_days)).isoformat()
    assert (state.review_count, state.correct_count) == (1, 1)
    assert state.fsrs_card  # FSRS のカードが保存されている

    later = DAY1 + timedelta(days=state.interval_days)
    state = review.record_answer(vid, WRONG, now=later)
    assert state.next_review == (later.date() + timedelta(days=state.interval_days)).isoformat()
    assert (state.review_count, state.correct_count, state.wrong_count) == (2, 1, 1)

    state = review.record_answer(vid, EASY, now=later + timedelta(days=1))
    assert (state.easy_count, state.total_correct) == (1, 2)

    assert [h["result"] for h in review.history(vid)] == [EASY, WRONG, CORRECT]


def test_legacy_state_is_converted_on_next_answer(repo, review):
    """以前の方式で学習した語彙(fsrs_card が空)も、次の回答で FSRS に変換される。"""
    vid = add(repo)
    with get_connection(repo.db_path) as conn:
        conn.execute(
            "INSERT INTO review_state (vocab_id, interval_days, next_review, review_count, correct_count, "
            "unsure_count, wrong_count, last_result, last_studied_at) "
            "VALUES (?, 8, '2026-11-01', 2, 2, 0, 0, 'correct', '2026-10-24 09:00:00')",
            (vid,),
        )
    state = review.record_answer(vid, CORRECT, now=DAY1)
    assert state.interval_days > 8  # 以前の間隔を引き継いで延びる
    assert state.fsrs_card and state.review_count == 3


def test_queue_puts_due_before_new(repo, review):
    due_id = add(repo, "復習")
    later_id = add(repo, "まだ先")
    new_ids = [add(repo, f"新規{i}") for i in range(5)]

    review.record_answer(due_id, WRONG, now=DAY1)  # 翌日が復習日
    review.record_answer(later_id, CORRECT, now=DAY1)  # 3 日後が復習日

    today = date(2026, 11, 2)
    assert review.due_ids(today) == [due_id]
    assert review.new_ids() == new_ids

    queue = review.build_queue(today, new_limit=2, shuffle=False)
    assert queue == [due_id, *new_ids[:2]]

    queue = review.build_queue(today, new_limit=10, shuffle=True)
    assert queue[0] == due_id  # シャッフルしても復習が先
    assert set(queue[1:]) == set(new_ids)


def test_queue_filters_by_category_and_difficulty(repo, review):
    a = add(repo, "A", category="思考・認識", difficulty=2)
    add(repo, "B", category="感情・心理", difficulty=2)
    add(repo, "C", category="思考・認識", difficulty=5)
    assert review.new_ids(["思考・認識"], (1, 3)) == [a]


def test_counts_for_home(repo, review):
    a, b = add(repo, "A"), add(repo, "B")
    add(repo, "C")
    review.record_answer(a, WRONG, now=DAY1)
    review.record_answer(a, CORRECT, now=DAY1 + timedelta(days=1))
    review.record_answer(b, WRONG, now=DAY1 + timedelta(days=1))

    day2 = date(2026, 11, 2)
    assert review.count_new_studied_on(day2) == 1  # A は 1 日目にはじめて学習済み
    assert review.count_answers_on(day2) == 2
    assert review.count_unstudied() == 1
    assert review.count_due(date(2026, 11, 3)) == 1  # B だけ(A は 3 日後)


def test_overwrite_import_keeps_learning_records(repo, review):
    vid = add(repo, id=1)
    review.record_answer(vid, CORRECT, now=DAY1)
    repo.import_vocabs([Vocab(id=1, word="俯瞰", meaning="新しい意味")], overwrite=True)
    assert review.get_state(vid) is not None
    assert len(review.history(vid)) == 1


def test_all_states(repo, review):
    a = add(repo, "A")
    add(repo, "B")
    review.record_answer(a, CORRECT, now=DAY1)
    states = review.all_states()
    assert list(states) == [a]
    assert states[a].mastery == "学習中"


def test_trash_keeps_records_and_purge_deletes_them(repo, review):
    vid = add(repo)
    review.record_answer(vid, CORRECT, now=DAY1)
    repo.delete(vid)  # ゴミ箱へ:学習記録は残るが、出題や集計には出てこない
    assert repo.get(vid) is None
    assert review.get_state(vid) is not None
    assert review.count_due(DAY1.date() + timedelta(days=30)) == 0
    repo.restore(vid)
    assert repo.get(vid) is not None
    repo.delete(vid)
    repo.purge(vid)  # 完全に削除:学習記録も消える
    assert review.get_state(vid) is None
    assert review.history(vid) == []
