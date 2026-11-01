from vorge.reading.analyzer import build_summary_prompt, candidates, find_known, highlight_known
from vorge.reading.repository import STATUS_IGNORED, STATUS_REGISTERED, ReadingRepository
from vorge.vocab.models import Vocab

TEXT = "物事を俯瞰して捉えることは大切だ。しかし、杞憂に終わる懸念もある。忖度ばかりでは本質を見失う。"


def test_find_known_and_highlight():
    vocabs = [Vocab(id=1, word="俯瞰", meaning="全体を見渡すこと"), Vocab(id=2, word="洞察", meaning="m")]
    found = find_known(TEXT, vocabs)
    assert [(v.word, s) for v, s in found] == [("俯瞰", "物事を俯瞰して捉えることは大切だ。")]
    html = highlight_known(TEXT, [vocabs[0]])
    assert '<mark class="vg-known" title="全体を見渡すこと">俯瞰</mark>' in html


def test_highlight_does_not_break_html_when_meaning_contains_other_word():
    a = Vocab(id=1, word="俯瞰", meaning="本質を見る")
    b = Vocab(id=2, word="本質", meaning="根本的な性質")
    html = highlight_known("俯瞰して本質を見る", [a, b])
    assert html.count("<mark") == 2
    assert 'title="本質を見る"' in html  # 意味の中の「本質」には印を付けない


def test_candidates_skip_known_and_common_words():
    words = [c.word for c in candidates(TEXT, known_words={"俯瞰", "本質"})]
    assert "杞憂" in words and "忖度" in words and "懸念" in words
    assert "俯瞰" not in words and "大切" not in words  # 登録済み・よく使う言葉は出さない
    sentence = next(c.sentence for c in candidates(TEXT, set()) if c.word == "杞憂")
    assert sentence == "しかし、杞憂に終わる懸念もある。"


def test_summary_prompt():
    text = build_summary_prompt("社説", "本文", "要約です", 100)
    assert "社説" in text and "本文" in text and "要約です" in text and "100字" in text


def test_repository_notes_and_candidates(repo):
    reading = ReadingRepository(repo.db_path)
    note_id = reading.add_note("", "出典", TEXT)
    assert reading.get_note(note_id).title == "(無題)"
    reading.update_summary(note_id, "要約", "メモ")
    assert reading.get_note(note_id).summary == "要約"

    assert reading.add_candidates(note_id, [("杞憂", "s1"), ("忖度", "s2")], source="出典") == 2
    assert reading.add_candidates(None, [("杞憂", "s3")]) == 0  # 同じ語は二重に入れない
    kiyuu, sontaku = sorted(reading.list_candidates(), key=lambda c: c.word != "杞憂")
    vid = repo.add(Vocab(word="杞憂", meaning="取り越し苦労"))
    reading.mark_registered(kiyuu.id, vid)
    reading.ignore(sontaku.id)
    assert reading.list_candidates() == []
    assert [c.vocab_id for c in reading.list_candidates(STATUS_REGISTERED)] == [vid]
    assert len(reading.list_candidates(STATUS_IGNORED)) == 1

    reading.delete_note(note_id)  # 文章を消すと、その文章から拾った候補も消える(登録した語彙は残る)
    assert reading.list_candidates(STATUS_REGISTERED) == []
    assert repo.get(vid) is not None
