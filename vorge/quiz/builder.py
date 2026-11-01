"""穴埋め問題の作成と採点(DB にも画面にも依存しない部分)。"""

import random
import unicodedata
from dataclasses import dataclass

from vorge.vocab.models import Vocab, split_terms
from vorge.writing.checker import word_variants

CHOICE_COUNT = 4  # 4 択


@dataclass
class Blank:
    """例文を「空欄の前・空欄に入る文字列・空欄の後」に分けたもの。"""

    before: str
    answer: str  # 例文中の実際の表記(活用していればその形)
    after: str

    @property
    def sentence(self) -> str:
        return self.before + self.answer + self.after


@dataclass
class Question:
    vocab_id: int
    word: str
    reading: str
    blank: Blank
    choices: list[int]  # 選択肢の語彙ID(正解を含む、並びはランダム)


def find_blank(sentence: str, word: str) -> Blank | None:
    """例文の中から語彙(活用形を含む)を探して空欄にする。見つからなければ None。

    「煮詰まる」が例文で「煮詰まってきた」となっている場合は「煮詰ま」の部分を空欄にする。
    """
    for variant in word_variants(word):  # 長い表記から順に探す
        pos = sentence.find(variant)
        if pos >= 0:
            return Blank(sentence[:pos], variant, sentence[pos + len(variant):])
    return None


def blanks_for(vocab: Vocab, excluded: set[str] = frozenset()) -> list[Blank]:
    """その語彙の例文から作れる空欄の一覧(すべての例文のうち、語彙が含まれているもの)。

    excluded に入っている例文(「おかしい」と報告されたもの)は使わない。
    """
    result = []
    for sentence in vocab.all_examples:
        if sentence in excluded:
            continue
        blank = find_blank(sentence, vocab.word)
        if blank:
            result.append(blank)
    return result


def pick_distractors(
    answer: Vocab, others: list[Vocab], k: int = CHOICE_COUNT - 1, contrast: bool = False
) -> list[Vocab]:
    """はずれの選択肢を k 個選ぶ。

    通常:同じカテゴリで難易度の差が 1 以内 → 同じカテゴリ → その他、の順に選ぶ。
          「どちらも正解」になるのを防ぐため、正解と同じ語・類義語として登録された語は使わない。
    使い分け(contrast=True):登録済みの類義語を最優先で混ぜ、似た語の中から選び分ける練習にする。
    """
    synonyms = set(split_terms(answer.synonyms))

    def is_synonym(v: Vocab) -> bool:
        return v.word in synonyms or answer.word in split_terms(v.synonyms)

    usable = [
        v for v in others
        if v.id != answer.id and v.word != answer.word and (contrast or not is_synonym(v))
    ]
    random.shuffle(usable)
    tiers = [
        [v for v in usable if contrast and is_synonym(v)],
        [v for v in usable if v.category == answer.category
         and abs(v.difficulty - answer.difficulty) <= 1],
        [v for v in usable if v.category == answer.category],
        usable,
    ]
    picked: list[Vocab] = []
    seen_words = {answer.word}
    for tier in tiers:
        for v in tier:
            if len(picked) == k:
                return picked
            if v.word not in seen_words:  # 同じ語(多義語)が 2 つ並ばないように
                picked.append(v)
                seen_words.add(v.word)
    return picked


def make_question(vocab: Vocab, blank: Blank, distractors: list[Vocab]) -> Question:
    choices = [vocab.id, *(d.id for d in distractors)]
    random.shuffle(choices)
    return Question(vocab.id, vocab.word, vocab.reading, blank, choices)


def _normalize(text: str) -> str:
    """全角・半角の違いと空白を無視して比べるための正規化。"""
    return "".join(unicodedata.normalize("NFKC", text).split())


def is_correct_input(answer: str, question: Question) -> bool:
    """入力式の採点。語彙・読み(ひらがな)・例文中の表記のどれでも正解にする。"""
    given = _normalize(answer)
    if not given:
        return False
    accepted = {question.word, question.blank.answer, *word_variants(question.word)}
    if question.reading:
        accepted |= {question.reading, *word_variants(question.reading)}
    return given in {_normalize(a) for a in accepted}
