"""議論の自動チェック、1 つの文章へのまとめ、添削依頼文の作成。

外部のライブラリや API を使わない簡単なルールによるチェックなので、画面では「目安」として表示する。
"""

import re
from dataclasses import dataclass, field

from vorge.debate.templates import STANCE_LABELS, Template
from vorge.writing.checker import check_vocab_usage, count_chars

# つなぎ言葉(議論の筋道を示す言葉)のグループ → 表記の例
CONNECTORS = {
    "理由を示す": ["なぜなら", "というのも", "からだ", "からである", "ためだ", "ためである"],
    "譲歩する": ["確かに", "たしかに", "もちろん", "一理ある"],
    "逆接で返す": ["しかし", "だが", "とはいえ", "それでも", "ところが"],
    # 「だから」は「〜だから問題ない」のように理由にも使われるので入れない
    "結論を示す": ["したがって", "よって", "つまり", "以上から", "以上のことから", "このように"],
}
# 反論つきの型で、特に使ってほしいグループ
REBUTTAL_CONNECTORS = ("譲歩する", "逆接で返す")

# 具体例・データがあるとみなす手がかり
EVIDENCE_WORDS = ["例えば", "たとえば", "実際", "具体的", "調査", "データ", "統計", "経験", "%", "％"]
# 「3割」「2時間」「100人」のような数字+単位(０-９ は全角数字、％ は全角の%)
_NUMBER = re.compile(
    "[0-9０-９一二三四五六七八九十百千万]+(人|割|倍|年|時間|分|円|日|回|件|%|％)"
)


@dataclass
class DebateCheck:
    char_counts: dict[str, int] = field(default_factory=dict)  # 欄 → 文字数
    empty_sections: list[str] = field(default_factory=list)  # 空の欄の見出し
    vocab_used: dict[str, bool] = field(default_factory=dict)
    connectors: dict[str, list[str]] = field(default_factory=dict)  # グループ → 使えた表記
    missing_evidence: list[str] = field(default_factory=list)  # 具体例が見当たらない欄の見出し
    total_chars: int = 0


def has_evidence(text: str) -> bool:
    return any(w in text for w in EVIDENCE_WORDS) or bool(_NUMBER.search(text))


def find_connectors(text: str) -> dict[str, list[str]]:
    return {group: [w for w in words if w in text] for group, words in CONNECTORS.items()}


def compose(template: Template, sections: dict[str, str]) -> str:
    """欄ごとの文章を、1 つの文章(欄ごとに段落)にまとめる。空の欄は飛ばす。"""
    return "\n".join(
        sections.get(s.key, "").strip() for s in template.sections if sections.get(s.key, "").strip()
    )


def check(template: Template, sections: dict[str, str], vocabs: list[tuple[str, str]]) -> DebateCheck:
    whole = compose(template, sections)
    result = DebateCheck(total_chars=count_chars(whole))
    for s in template.sections:
        text = sections.get(s.key, "")
        result.char_counts[s.key] = count_chars(text)
        if not text.strip():
            result.empty_sections.append(s.label)
        elif s.needs_evidence and not has_evidence(text):
            result.missing_evidence.append(s.label)
    result.vocab_used = check_vocab_usage(whole, vocabs)
    result.connectors = find_connectors(whole)
    return result


def build_review_prompt(
    prompt_text: str,
    stance: str,
    template: Template,
    words: list[tuple[str, str]],
    sections: dict[str, str],
) -> str:
    """AI チャットに貼り付けて、議論の添削と「相手側からの反論」を頼むための文章。"""
    word_lines = "\n".join(f"- {w}:{m}" for w, m in words) or "- (なし)"
    body = "\n".join(
        f"【{s.label}】{sections.get(s.key, '').strip()}" for s in template.sections
    )
    return (
        "あなたは議論・ディベートの指導者です。次の意見文を評価してください。\n\n"
        "## 条件\n"
        f"- お題:{prompt_text}\n"
        f"- 立場:{STANCE_LABELS.get(stance, stance)}\n"
        f"- 構成の型:{template.label}({' → '.join(s.label for s in template.sections)})\n"
        f"- 使うように指定した語彙:\n{word_lines}\n\n"
        "## 評価してほしい点\n"
        "1. 主張・根拠・結論が論理的につながっているか(飛躍や矛盾があれば指摘)\n"
        "2. 根拠の説得力(具体例やデータは十分か)\n"
        "3. 予想した反論と再反論は的確か(反論つきの型の場合)\n"
        "4. 指定した語彙が正しく自然に使えているか\n"
        "5. 良かった点\n\n"
        "最後に、反対の立場からもっとも強い反論を 1 つ示してください。私はそれに再反論する練習をします。\n\n"
        f"## 意見文\n{body}"
    )
