"""作文の自動チェックと、添削依頼文(プロンプト)の作成。

外部のライブラリや API を使わない、簡単なルールによるチェック。
完璧ではないので、画面では「目安」として表示する。
"""

import re
from collections import Counter
from dataclasses import dataclass, field

# 文字数を数えるときに除く空白(半角・全角スペース、改行、タブ)
_SPACES = re.compile(r"\s|　")
# 文の区切り
_SENTENCE_END = re.compile("(?<=[。!?！？])")  # ！=! ？=?(全角)
# 文末についていても無視する記号(句点・感嘆符・疑問符・閉じかっこ・空白)
_TRAILING = "。!?！？」』)） 　\n"
# 漢字 2 文字以上の語、カタカナ 3 文字以上の語(繰り返しの候補)
_KANJI_WORD = re.compile(r"[一-龥々]{2,}")
_KATAKANA_WORD = re.compile(r"[ァ-ヶー]{3,}")

# 作文で使いすぎやすい言葉(表示名 → 数える表記)
FILLERS = {
    "思う": ["思う", "思い", "思っ", "思わ", "思え"],
    "感じる": ["感じ"],
    "とても": ["とても"],
    "すごく・すごい": ["すごく", "すごい"],
    "やはり": ["やはり", "やっぱり"],
    "という": ["という"],
    "そして": ["そして"],
    "しかし": ["しかし"],
    "なので": ["なので"],
}

# です・ます調と判断する文末
POLITE_ENDINGS = ("です", "ます", "でした", "ました", "ません", "でしょう", "ましょう")

REPEAT_THRESHOLD = 3  # この回数以上で「繰り返し」として知らせる
MONOTONE_THRESHOLD = 3  # 同じ文末がこの回数以上続いたら知らせる


@dataclass
class CheckResult:
    char_count: int
    length_status: str  # "short" / "ok" / "long"
    vocab_used: dict[str, bool] = field(default_factory=dict)  # 語彙 → 使えたか
    repeated: list[tuple[str, int]] = field(default_factory=list)  # (言葉, 回数)
    monotone: tuple[str, int] | None = None  # (文末, 連続回数)
    style_mix: tuple[int, int] | None = None  # (です・ます調の文の数, だ・である調の文の数)


def count_chars(text: str) -> int:
    """空白と改行を除いた文字数。"""
    return len(_SPACES.sub("", text))


def word_variants(word: str, reading: str = "") -> list[str]:
    """本文中で「使えた」とみなす表記の一覧。

    活用する語(最後がひらがな)は最後の 1 文字を除いた形も認める。
    例:「腑に落ちる」→「腑に落ち」も OK(「腑に落ちた」に一致する)
    読み(ひらがな書き)で書いた場合も認める。
    """
    variants = {word}
    inflectable = bool(word) and "ぁ" <= word[-1] <= "ゖ"
    if inflectable and len(word) >= 3:
        variants.add(word[:-1])
    if reading and reading != word:
        variants.add(reading)
        if inflectable and len(reading) >= 4:
            variants.add(reading[:-1])
    return sorted(variants, key=len, reverse=True)


def check_vocab_usage(body: str, vocabs: list[tuple[str, str]]) -> dict[str, bool]:
    """(語彙, 読み) の一覧について、本文で使えたかどうか。"""
    return {
        word: any(v and v in body for v in word_variants(word, reading))
        for word, reading in vocabs
    }


def find_repeated_words(body: str, exclude: set[str] = frozenset()) -> list[tuple[str, int]]:
    """何度も使われている言葉(多い順、最大 5 個)。指定語彙(exclude)は除く。"""
    counts: Counter[str] = Counter()
    for label, forms in FILLERS.items():
        n = sum(body.count(f) for f in forms)
        if n:
            counts[label] = n
    for pattern in (_KANJI_WORD, _KATAKANA_WORD):
        for term in pattern.findall(body):
            if not any(term in w or w in term for w in exclude):
                counts[term] += 1
    repeated = [(t, n) for t, n in counts.items() if n >= REPEAT_THRESHOLD]
    return sorted(repeated, key=lambda x: -x[1])[:5]


def sentences_with(body: str, word: str, reading: str = "") -> list[str]:
    """本文のうち、その語彙(活用形・ひらがな書きを含む)が使われている文だけを返す。"""
    variants = [v for v in word_variants(word, reading) if v]
    return [s for s in split_sentences(body) if any(v in s for v in variants)]


def split_sentences(body: str) -> list[str]:
    parts = (s.strip() for s in _SENTENCE_END.split(body.replace("\n", "")))
    return [s for s in parts if s.strip(_TRAILING)]


def sentence_ending(sentence: str) -> str:
    """文末の 2 文字(句点やかっこを除く)。"""
    return sentence.rstrip(_TRAILING)[-2:]


def find_monotone_endings(sentences: list[str]) -> tuple[str, int] | None:
    """同じ文末がいちばん長く続いた箇所。MONOTONE_THRESHOLD 未満なら None。"""
    best: tuple[str, int] | None = None
    run_ending, run = "", 0
    for s in sentences:
        ending = sentence_ending(s)
        run = run + 1 if ending == run_ending else 1
        run_ending = ending
        if run >= MONOTONE_THRESHOLD and (best is None or run > best[1]):
            best = (ending, run)
    return best


def find_style_mix(sentences: list[str]) -> tuple[int, int] | None:
    """です・ます調とだ・である調が混ざっていれば (前者の数, 後者の数)。

    体言止めなどもあるので、どちらも 2 文以上あるときだけ知らせる。
    """
    polite = sum(1 for s in sentences if s.rstrip(_TRAILING).endswith(POLITE_ENDINGS))
    plain = len(sentences) - polite
    return (polite, plain) if polite >= 2 and plain >= 2 else None


def check(
    body: str, vocabs: list[tuple[str, str]], min_chars: int, max_chars: int
) -> CheckResult:
    n = count_chars(body)
    status = "short" if n < min_chars else "long" if n > max_chars else "ok"
    sentences = split_sentences(body)
    return CheckResult(
        char_count=n,
        length_status=status,
        vocab_used=check_vocab_usage(body, vocabs),
        repeated=find_repeated_words(body, {w for w, _ in vocabs}),
        monotone=find_monotone_endings(sentences),
        style_mix=find_style_mix(sentences),
    )


def build_review_prompt(
    prompt_text: str,
    words: list[tuple[str, str]],
    body: str,
    min_chars: int,
    max_chars: int,
) -> str:
    """claude.ai などに貼り付けて添削を頼むための文章。words は (語彙, 意味) の一覧。"""
    word_lines = "\n".join(f"- {w}:{m}" for w, m in words)
    return (
        "あなたは日本語の文章指導の専門家です。次の作文を添削してください。\n\n"
        "## 条件\n"
        f"- お題:{prompt_text}\n"
        f"- 目安の文字数:{min_chars}〜{max_chars}字\n"
        f"- 使うように指定した語彙:\n{word_lines}\n\n"
        "## 添削してほしい点\n"
        "1. 指定した語彙が、意味・文脈ともに正しく自然に使えているか(誤用があれば理由も)\n"
        "2. 文章の分かりやすさ・論理の流れ\n"
        "3. より適切な語彙や表現への言い換えの提案(3つまで)\n"
        "4. 良かった点\n"
        "最後に、直した後の文章の例を示してください。\n\n"
        f"## 作文\n{body}"
    )
