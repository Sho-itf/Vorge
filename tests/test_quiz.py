from datetime import date, datetime

import pytest

from vorge.flashcard.repository import ReviewRepository
from vorge.flashcard.scheduler import WRONG
from vorge.quiz.builder import (
    Blank,
    Question,
    blanks_for,
    find_blank,
    is_correct_input,
    pick_distractors,
)
from vorge.quiz.repository import FORMAT_CHOICE, QuizRepository
from vorge.vocab.models import Vocab


def v(id, word, category="思考・認識", difficulty=3, synonyms="", ex="", reading=""):
    return Vocab(id=id, word=word, meaning=f"{word}の意味", category=category,
                 difficulty=difficulty, synonyms=synonyms, example_1=ex, reading=reading)


@pytest.fixture
def quiz(repo):
    return QuizRepository(repo.db_path)


# ---------- 問題作成(builder) ----------


def test_find_blank_plain_and_conjugated():
    assert find_blank("物事を俯瞰して捉える", "俯瞰") == Blank("物事を", "俯瞰", "して捉える")
    # 活用形:「煮詰まる」→ 例文中の「煮詰ま」を空欄にする
    assert find_blank("議論が煮詰まってきた", "煮詰まる") == Blank("議論が", "煮詰ま", "ってきた")
    assert find_blank("関係のない文", "俯瞰") is None


def test_blanks_for_uses_only_examples_containing_the_word():
    vocab = Vocab(word="俯瞰", meaning="m", example_1="俯瞰する", example_2="全く別の文")
    assert [b.answer for b in blanks_for(vocab)] == ["俯瞰"]


def test_pick_distractors_prefers_same_category_and_skips_synonyms():
    answer = v(1, "俯瞰", synonyms="概観,鳥瞰")
    others = [
        v(2, "概観"),  # 類義語 → 使わない
        v(3, "洞察"),  # 同カテゴリ・同難易度
        v(4, "看破", difficulty=4),  # 同カテゴリ・難易度差 1
        v(5, "熟慮", difficulty=1),  # 同カテゴリ・難易度差 2
        v(6, "葛藤", category="感情・心理"),  # 別カテゴリ
        v(7, "俯瞰"),  # 同じ語(多義語)→ 使わない
    ]
    picked = [d.word for d in pick_distractors(answer, others)]
    assert len(picked) == 3
    assert "概観" not in picked and "俯瞰" not in picked
    assert set(picked[:2]) == {"洞察", "看破"}  # 近い難易度の同カテゴリが先
    assert picked[2] == "熟慮"  # 次に同カテゴリ


def test_pick_distractors_falls_back_to_other_categories():
    picked = pick_distractors(v(1, "A"), [v(2, "B", category="X"), v(3, "C", category="Y")])
    assert {d.word for d in picked} == {"B", "C"}


def test_input_answer_accepts_word_reading_and_example_form():
    q = Question(1, "煮詰まる", "につまる", Blank("議論が", "煮詰ま", "ってきた"), [1])
    for given in ("煮詰まる", "煮詰ま", "につまる", " 煮詰まる ", "につま"):
        assert is_correct_input(given, q), given
    assert not is_correct_input("行き詰まる", q)
    assert not is_correct_input("", q)


# ---------- 出題と記録(repository) ----------


def test_build_questions(repo, quiz):
    ids = [
        repo.add(Vocab(word=w, meaning="m", example_1=f"これは{w}の例文", category="思考・認識"))
        for w in ("俯瞰", "洞察", "看破", "熟慮")
    ]
    repo.add(Vocab(word="例文なし", meaning="m"))  # 例文が無い語彙は出題しない
    assert len(quiz.eligible_vocab()) == 4

    questions = quiz.build_questions(10)
    assert len(questions) == 4
    for q in questions:
        assert q.vocab_id in q.choices and len(q.choices) == 4
        assert q.blank.answer == q.word

    only = quiz.build_questions(5, only_ids=[ids[0]])
    assert [q.vocab_id for q in only] == [ids[0]]


def test_build_questions_respects_scope(repo, quiz):
    weak = repo.add(Vocab(word="苦手", meaning="m", example_1="苦手な例文"))
    repo.add(Vocab(word="普通", meaning="m", example_1="普通の例文"))
    ReviewRepository(repo.db_path).record_answer(weak, WRONG, now=datetime(2026, 11, 1))
    assert [x.id for x in quiz.eligible_vocab("weak")] == [weak]


def test_record_and_stats(repo, quiz):
    a = repo.add(Vocab(word="A", meaning="Aの意味"))
    b = repo.add(Vocab(word="B", meaning="Bの意味"))
    now = datetime(2026, 11, 1, 9)
    quiz.record(a, FORMAT_CHOICE, False, "B", now=now)
    quiz.record(a, FORMAT_CHOICE, False, "C", now=now)
    quiz.record(a, FORMAT_CHOICE, True, "A", now=now)
    quiz.record(b, FORMAT_CHOICE, True, "B", now=now)

    assert quiz.total_answers() == 4
    assert quiz.accuracy_between(date(2026, 11, 1), date(2026, 11, 1)) == 0.5
    assert quiz.accuracy_between(date(2026, 10, 1), date(2026, 10, 2)) is None
    missed = quiz.most_missed()
    assert [(m.word, m.wrong, m.total) for m in missed] == [("A", 2, 3)]


def test_quiz_does_not_touch_review_schedule(repo, quiz):
    a = repo.add(Vocab(word="A", meaning="m"))
    quiz.record(a, FORMAT_CHOICE, True, "A")
    assert ReviewRepository(repo.db_path).get_state(a) is None
