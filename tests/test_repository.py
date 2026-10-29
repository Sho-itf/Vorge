from datetime import date

from vorge.vocab.models import Vocab


def make(word="俯瞰", meaning="全体を見渡すこと", **kw):
    return Vocab(word=word, meaning=meaning, **kw)


def test_add_get_update_delete(repo):
    vid = repo.add(make(reading="ふかん", category="思考・認識", difficulty=3))
    v = repo.get(vid)
    assert v.word == "俯瞰" and v.reading == "ふかん"

    v.meaning = "高い所から全体を見渡すこと"
    assert repo.update(v)
    assert repo.get(vid).meaning == "高い所から全体を見渡すこと"

    assert repo.delete(vid)
    assert repo.get(vid) is None
    assert not repo.delete(vid)


def test_same_word_can_be_registered_twice(repo):
    a = repo.add(make(word="きく", meaning="聞く"))
    b = repo.add(make(word="きく", meaning="効く"))
    assert a != b
    assert repo.count() == 2


def test_search_by_keyword_category_difficulty(repo):
    repo.add(make(word="俯瞰", meaning="全体を見る", category="思考・認識", difficulty=3))
    repo.add(make(word="洞察", meaning="本質を見抜く", category="思考・認識", difficulty=4))
    repo.add(make(word="齟齬", meaning="食い違い", category="関係・構造", difficulty=4))

    assert [v.word for v in repo.search("本質")] == ["洞察"]
    assert len(repo.search(categories=["思考・認識"])) == 2
    assert {v.word for v in repo.search(difficulty_range=(4, 5))} == {"洞察", "齟齬"}
    assert [v.word for v in repo.search("見", ["思考・認識"], (4, 5))] == ["洞察"]
    # スペース区切りは AND 検索
    assert [v.word for v in repo.search("全体 見る")] == ["俯瞰"]


def test_search_treats_percent_literally(repo):
    repo.add(make(word="百%", meaning="完全"))
    repo.add(make(word="百", meaning="数"))
    assert [v.word for v in repo.search("%")] == ["百%"]


def test_new_category_is_registered(repo):
    repo.add(make(category="ビジネス"))
    assert "ビジネス" in repo.list_categories()
    assert repo.list_categories()[-1] == "未分類"


def test_count_added_today(repo):
    repo.add(make())
    assert repo.count_added_on(date.today()) == 1


def test_import_skips_existing_ids_by_default(repo):
    repo.add(make(id=1, word="元の語彙"))
    result = repo.import_vocabs([make(id=1, word="新しい語彙"), make(id=2, word="追加")])
    assert (result.inserted, result.updated, result.skipped) == (1, 0, 1)
    assert repo.get(1).word == "元の語彙"
    assert repo.get(2).word == "追加"


def test_import_overwrite_keeps_id_and_created_at(repo):
    repo.add(make(id=1, word="元の語彙"))
    created = repo.get(1).created_at
    result = repo.import_vocabs([make(id=1, word="新しい語彙")], overwrite=True)
    assert result.updated == 1
    v = repo.get(1)
    assert v.word == "新しい語彙"
    assert v.created_at == created


def test_import_without_id_autonumbers(repo):
    result = repo.import_vocabs([make(), make()])
    assert result.inserted == 2
    assert repo.count() == 2
