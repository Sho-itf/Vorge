from datetime import date, datetime

import pytest

from vorge.db import init_db
from vorge.flashcard.repository import ReviewRepository
from vorge.flashcard.scheduler import CORRECT, WRONG
from vorge.settings import get_setting, set_setting
from vorge.vocab.models import Vocab
from vorge.writing import prompts as P
from vorge.writing.repository import WritingRepository, WritingWord


@pytest.fixture
def writing(repo):
    return WritingRepository(repo.db_path)


def add(repo, word):
    return repo.add(Vocab(word=word, meaning=f"{word}の意味"))


def test_default_prompts_are_seeded_once(repo, writing):
    prompts = writing.list_prompts()
    assert len(prompts) == 60
    assert {p.kind for p in prompts} == set(P.KIND_LABELS)

    writing.delete_prompt(prompts[0].id)
    init_db(repo.db_path)  # 起動し直しても、削除したお題は復活しない
    assert len(writing.list_prompts()) == 59


def test_prompt_crud_and_active_flag(writing):
    pid = writing.add_prompt(P.KIND_DAILY, "  新しいお題  ")
    p = next(x for x in writing.list_prompts() if x.id == pid)
    assert p.text == "新しいお題" and p.active

    writing.update_prompt(pid, P.KIND_OPINION, "変えたお題", active=False)
    assert pid not in {x.id for x in writing.list_prompts(active_only=True)}
    p = next(x for x in writing.list_prompts(P.KIND_OPINION) if x.id == pid)
    assert p.text == "変えたお題"

    with pytest.raises(ValueError):
        writing.add_prompt(P.KIND_DAILY, "   ")


def test_random_prompt_respects_kind_and_exclude(writing):
    p = writing.random_prompt(P.KIND_EXPLAIN)
    assert p.kind == P.KIND_EXPLAIN
    other = writing.random_prompt(P.KIND_EXPLAIN, exclude_id=p.id)
    assert other.id != p.id
    assert writing.random_prompt(P.AUTO) is not None


def test_save_and_list_writings(repo, writing):
    a, b = add(repo, "逡巡"), add(repo, "相対化")
    prompt = writing.random_prompt(P.KIND_DAILY)
    wid = writing.save_writing(
        prompt, 100, 200, "本文", 2, [WritingWord(a, "逡巡", True), WritingWord(b, "相対化", False)]
    )
    w = writing.get_writing(wid)
    assert w.prompt_text == prompt.text and w.body == "本文"
    assert [(x.word, x.used) for x in w.words] == [("逡巡", True), ("相対化", False)]

    assert [x.id for x in writing.list_writings(vocab_id=b)] == [wid]
    assert writing.usage_count(a) == 1 and writing.usage_count(b) == 0
    assert writing.count_writings() == 1 and writing.count_writings_on(date.today()) == 1

    writing.update_feedback(wid, "よく書けています")
    assert writing.get_writing(wid).feedback == "よく書けています"


def test_writing_survives_prompt_and_vocab_deletion(repo, writing):
    a = add(repo, "逡巡")
    prompt = writing.random_prompt(P.KIND_DAILY)
    wid = writing.save_writing(prompt, 100, 200, "本文", 2, [WritingWord(a, "逡巡", True)])
    writing.delete_prompt(prompt.id)
    repo.delete(a)
    repo.purge(a)  # 語彙を完全に削除
    w = writing.get_writing(wid)
    assert w.prompt_text == prompt.text  # お題の文面は残る
    assert w.words == []  # 語彙との対応だけが消える

    writing.delete_writing(wid)  # ゴミ箱へ
    assert writing.get_writing(wid) is None
    assert [w.id for w in writing.list_trash()] == [wid]
    assert writing.count_writings() == 0
    writing.restore_writing(wid)
    assert writing.get_writing(wid) is not None
    writing.delete_writing(wid)
    writing.purge_writing(wid)
    assert writing.list_trash() == []


def test_pick_vocab_modes(repo, writing):
    review = ReviewRepository(repo.db_path)
    weak, learning, new = add(repo, "苦手"), add(repo, "学習中"), add(repo, "未学習")
    now = datetime(2026, 11, 1)
    review.record_answer(weak, WRONG, now=now)
    review.record_answer(learning, CORRECT, now=now)

    assert writing.pick_vocab(P.VOCAB_WEAK, 1) == [weak]
    assert writing.pick_vocab(P.VOCAB_NEW, 1) == [new]
    assert set(writing.pick_vocab(P.VOCAB_LEARNING, 2)) == {weak, learning}
    assert set(writing.pick_vocab(P.AUTO, 3)) == {weak, learning, new}
    # 候補が足りなければ全語彙から補う
    assert len(writing.pick_vocab(P.VOCAB_WEAK, 3)) == 3
    # exclude した語彙はなるべく避ける
    assert weak not in writing.pick_vocab(P.AUTO, 2, exclude={weak})


def test_settings_roundtrip(repo):
    assert get_setting("x", "default", repo.db_path) == "default"
    set_setting("x", 3, repo.db_path)
    set_setting("x", ["a", "b"], repo.db_path)
    assert get_setting("x", None, repo.db_path) == ["a", "b"]
