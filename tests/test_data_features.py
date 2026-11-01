"""第 8 段階のデータまわり:3 本目以降の例文・関連語・多義語・使い分けクイズ。"""

from vorge.quiz.builder import blanks_for, pick_distractors
from vorge.quiz.repository import QuizRepository
from vorge.vocab.models import Vocab
from vorge.vocab.relations import linked_terms, other_senses, sense_number, synonym_ids, word_index


def test_extra_examples_saved_and_not_wiped_by_csv_overwrite(repo):
    vid = repo.add(Vocab(word="俯瞰", meaning="m", example_1="例1", extra_examples=[" 例3 ", "", "例4"]))
    v = repo.get(vid)
    assert v.extra_examples == ["例3", "例4"]
    assert v.all_examples == ["例1", "例3", "例4"]

    # CSV の上書き取り込み(extra_examples=None)では、アプリで足した例文は消えない
    repo.import_vocabs([Vocab(id=vid, word="俯瞰", meaning="新しい意味")], overwrite=True)
    assert repo.get(vid).extra_examples == ["例3", "例4"]

    # 編集で空にすれば消える
    v = repo.get(vid)
    v.extra_examples = []
    repo.update(v)
    assert repo.get(vid).extra_examples == []


def test_quiz_uses_extra_examples(repo):
    vocab = Vocab(id=1, word="俯瞰", meaning="m", example_1="関係ない文", extra_examples=["全体を俯瞰する"])
    assert [b.sentence for b in blanks_for(vocab)] == ["全体を俯瞰する"]


def test_relations():
    a = Vocab(id=1, word="俯瞰", meaning="m", synonyms="概観,鳥瞰", antonyms="細部")
    b = Vocab(id=2, word="概観", meaning="m")
    c = Vocab(id=3, word="鳥瞰", meaning="m")
    d = Vocab(id=4, word="大局", meaning="m", synonyms="俯瞰")  # 片方だけに書いてあってもつながる
    e1 = Vocab(id=5, word="きく", meaning="聞く")
    e2 = Vocab(id=6, word="きく", meaning="効く")
    vocabs = [a, b, c, d, e1, e2]
    index = word_index(vocabs)
    assert linked_terms(a, index) == {"概観": 2, "鳥瞰": 3}  # 「細部」は未登録なのでリンクしない
    assert synonym_ids(a, vocabs, index) == [2, 3, 4]
    assert other_senses(e1, index) == [6]
    assert (sense_number(e1, index), sense_number(e2, index), sense_number(a, index)) == (1, 2, None)


def test_contrast_mode_prefers_synonyms():
    answer = Vocab(id=1, word="俯瞰", meaning="m", synonyms="概観,鳥瞰", category="A")
    others = [
        Vocab(id=2, word="概観", meaning="m", category="B"),
        Vocab(id=3, word="鳥瞰", meaning="m", category="B"),
        Vocab(id=4, word="洞察", meaning="m", category="A"),
        Vocab(id=5, word="看破", meaning="m", category="A"),
    ]
    normal = {v.word for v in pick_distractors(answer, others)}
    assert "概観" not in normal and "鳥瞰" not in normal
    contrast = [v.word for v in pick_distractors(answer, others, contrast=True)]
    assert set(contrast[:2]) == {"概観", "鳥瞰"}  # 類義語が先に入る


def test_contrast_eligible_only_words_with_registered_synonyms(repo):
    quiz = QuizRepository(repo.db_path)
    repo.add(Vocab(word="俯瞰", meaning="m", synonyms="概観", example_1="全体を俯瞰する"))
    repo.add(Vocab(word="概観", meaning="m", example_1="歴史を概観する"))
    repo.add(Vocab(word="葛藤", meaning="m", example_1="心の葛藤"))
    assert {v.word for v in quiz.eligible_vocab(contrast=True)} == {"俯瞰", "概観"}
    assert len(quiz.eligible_vocab()) == 3
