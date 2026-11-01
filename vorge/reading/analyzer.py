"""貼り付けた文章の分析(登録済みの語彙を探す・まだ登録していない語の候補を出す)と、要約の添削依頼文。

辞書を使わない簡単なルールなので、候補には一般的な言葉も混ざる。画面で自分で選んでもらう前提。
"""

import re
from dataclasses import dataclass
from html import escape

from vorge.vocab.models import Vocab
from vorge.writing.checker import split_sentences, word_variants

# 漢字 2 文字以上の語、カタカナ 4 文字以上の語を「候補」とする
_KANJI_WORD = re.compile(r"[一-龥々]{2,}")
_KATAKANA_WORD = re.compile(r"[ァ-ヶー]{4,}")

# よく使われる言葉は候補から外す(語彙として覚える必要がほとんど無いもの)
COMMON_WORDS = set(
    "今日 明日 昨日 今年 去年 来年 毎日 時間 自分 日本 世界 社会 人間 問題 必要 場合 関係 今回 最近 以上 以下 "
    "方法 結果 意味 理由 部分 仕事 会社 学校 生活 気持 一番 一緒 大切 大事 簡単 本当 普通 全部 自身 他人 多く "
    "女性 男性 子供 子ども 家族 友人 年代 世代 地域 状況 情報 経済 政治 文化 教育 研究 調査 企業 国民 政府 "
    "大学 学生 先生 写真 映画 音楽 食事 電話 一方 一部 以前 以後 現在 将来 過去 今後 当時 毎年 半分 程度 "
    "可能 重要 確認 利用 使用 説明 理解 考え 意見 対応 実際 具体 特別 全体 自然 環境 技術 開発 経験 成長".split()
)


@dataclass
class Candidate:
    word: str
    count: int
    sentence: str  # その語が最初に出てくる文(例文として登録できる)


def _sentences(text: str) -> list[str]:
    return split_sentences(text) or [text]


def find_known(text: str, vocabs: list[Vocab]) -> list[tuple[Vocab, str]]:
    """文章に出てくる登録済みの語彙と、それが出てくる最初の文。"""
    sentences = _sentences(text)
    found = []
    for v in vocabs:
        variants = word_variants(v.word, v.reading if len(v.reading) >= 3 else "")
        sentence = next((s for s in sentences if any(x in s for x in variants)), None)
        if sentence:
            found.append((v, sentence))
    return found


def candidates(text: str, known_words: set[str], limit: int = 40) -> list[Candidate]:
    """まだ登録していない、覚えておきたいかもしれない語の候補(長い語・よく出る語ほど先)。"""
    counts: dict[str, int] = {}
    for pattern in (_KANJI_WORD, _KATAKANA_WORD):
        for term in pattern.findall(text):
            counts[term] = counts.get(term, 0) + 1
    sentences = _sentences(text)
    result = []
    for term, n in counts.items():
        if term in COMMON_WORDS or term in known_words or any(term in w for w in known_words):
            continue
        sentence = next((s for s in sentences if term in s), "")
        result.append(Candidate(term, n, sentence))
    result.sort(key=lambda c: (-len(c.word), -c.count, c.word))
    return result[:limit]


def highlight_known(text: str, vocabs: list[Vocab]) -> str:
    """文章の HTML。登録済みの語彙に印を付け、マウスを乗せると意味が出るようにする。"""
    html_text = escape(text)
    meanings = {escape(v.word): escape(v.meaning) for v in vocabs if v.word}
    if meanings:
        # 1 回の置き換えで全部に印を付ける。長い語を先に試すので、短い語が長い語の一部に付くことはない。
        # (1 語ずつ順に置き換えると、先に入れた意味の文字の中まで置き換えてしまうため)
        pattern = re.compile("|".join(re.escape(w) for w in sorted(meanings, key=len, reverse=True)))
        html_text = pattern.sub(
            lambda m: f'<mark class="vg-known" title="{meanings[m.group(0)]}">{m.group(0)}</mark>', html_text
        )
    return html_text.replace("\n", "<br>")


def build_summary_prompt(title: str, body: str, summary: str, target_chars: int) -> str:
    """要約を AI チャットで添削してもらうための依頼文。"""
    return (
        "あなたは国語の読解指導の専門家です。次の文章の要約を添削してください。\n\n"
        f"## 条件\n- 目安の文字数:{target_chars}字前後\n\n"
        "## 添削してほしい点\n"
        "1. 筆者の主張・要点を正しく捉えているか(取りこぼしや誤解があれば指摘)\n"
        "2. 重要でない部分を省けているか\n"
        "3. 文章として分かりやすいか\n"
        "最後に、模範となる要約の例を示してください。\n\n"
        f"## 元の文章({title})\n{body}\n\n"
        f"## 私の要約\n{summary}"
    )
