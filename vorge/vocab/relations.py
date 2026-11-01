"""語彙どうしのつながり(類義語・対義語・同じ語の別の意味)を調べる。

類義語・対義語は文字列(「概観,鳥瞰」)で保存しているので、表示のたびに
「登録済みの語彙と一致する語」を探してつなぐ。DB に別のテーブルは作らない。
"""

from vorge.vocab.models import Vocab, split_terms


def word_index(vocabs: list[Vocab]) -> dict[str, list[int]]:
    """語 → その語の語彙ID の一覧(同じ語で意味違いが複数あるときは複数)。"""
    index: dict[str, list[int]] = {}
    for v in vocabs:
        index.setdefault(v.word, []).append(v.id)
    return index


def linked_terms(v: Vocab, index: dict[str, list[int]]) -> dict[str, int]:
    """類義語・対義語のうち、登録済みの語 → その語彙ID(意味違いが複数ある語は最初のもの)。"""
    terms = split_terms(v.synonyms) + split_terms(v.antonyms)
    return {t: index[t][0] for t in terms if t in index and t != v.word}


def synonym_ids(v: Vocab, vocabs: list[Vocab], index: dict[str, list[int]] | None = None) -> list[int]:
    """登録済みの類義語の語彙ID。

    片方にしか類義語として書いていなくても、つながっているものとして扱う
    (A の類義語に B がある、または B の類義語に A がある)。
    """
    index = index or word_index(vocabs)
    ids = [i for t in split_terms(v.synonyms) for i in index.get(t, [])]
    ids += [o.id for o in vocabs if v.word in split_terms(o.synonyms)]
    return [i for i in dict.fromkeys(ids) if i != v.id]


def other_senses(v: Vocab, index: dict[str, list[int]]) -> list[int]:
    """同じ語で、意味が違う別の登録(多義語・同音異義語)。"""
    return [i for i in index.get(v.word, []) if i != v.id]


def sense_number(v: Vocab, index: dict[str, list[int]]) -> int | None:
    """同じ語が複数登録されているとき、その中で何番目か(1 始まり、ID の小さい順)。1 つだけなら None。"""
    ids = sorted(index.get(v.word, []))
    return ids.index(v.id) + 1 if len(ids) > 1 and v.id in ids else None
