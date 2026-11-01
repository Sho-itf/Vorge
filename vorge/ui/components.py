"""画面間で共通の UI 部品(語彙カード・入力フォーム・通知)。"""

from html import escape

import streamlit as st

from vorge.flashcard.repository import ReviewState
from vorge.flashcard.scheduler import mastery_label
from vorge.vocab.models import (
    DEFAULT_DIFFICULTY,
    DIFFICULTY_MAX,
    DIFFICULTY_MIN,
    FIELD_LABELS,
    UNCATEGORIZED,
    Vocab,
    split_terms,
)

# ---------- 画面をまたぐ通知 ----------
# st.rerun() で画面を再描画すると直前のメッセージが消えるため、
# session_state に一時保存して次の描画で表示する。


def set_flash(message: str, kind: str = "success") -> None:
    st.session_state["_flash"] = (message, kind)


def html(container, body: str) -> None:
    """HTML をそのまま表示する(container には st や列などを渡す)。

    ユーザーが入力した文字列を埋め込むときは、必ず html.escape() を通すこと。
    """
    container.markdown(body, unsafe_allow_html=True)


def show_flash() -> None:
    flash = st.session_state.pop("_flash", None)
    if flash:
        message, kind = flash
        icon = {"success": "✅", "warning": "⚠️", "error": "❌"}.get(kind, "ℹ️")
        st.toast(message, icon=icon)


# ---------- 表示用 ----------


def stars(level: int) -> str:
    return "★" * level + "☆" * (DIFFICULTY_MAX - level)


def ruby_html(word: str, reading: str) -> str:
    """語彙の上に読みをふりがなとして載せた HTML(<ruby> タグ)。読みが無ければ語彙だけ。"""
    if not reading:
        return escape(word)
    return f"<ruby>{escape(word)}<rt>{escape(reading)}</rt></ruby>"


def highlight_html(text: str, word: str) -> str:
    """文中に出てくる語彙を太字にした HTML(例文で使い方を見つけやすくする)。"""
    escaped = escape(text)
    if not word:
        return escaped
    return escaped.replace(escape(word), f"<b>{escape(word)}</b>")


def flash_front(text: str, sub: str = "", label: str = "") -> None:
    """フラッシュカードの問題面(大きな文字で 1 つだけ表示する)。"""
    size = " vg-long" if len(text) > 12 else ""  # 意味のような長い文は少し小さく
    st.markdown(
        '<div class="vg-card vg-flash">'
        + (f'<p class="vg-label">{escape(label)}</p>' if label else "")
        + f'<p class="vg-flash-text{size}">{escape(text)}</p>'
        + (f'<p class="vg-reading">{escape(sub)}</p>' if sub else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def vocab_mini_cards(vocabs: list[Vocab], used: dict[str, bool]) -> None:
    """作文・議論で使う語彙を横並びの小さなカードで表示する(使えた語彙には ✅)。"""
    if not vocabs:
        st.info("使う語彙を選んでください。")
        return
    for col, v in zip(st.columns(len(vocabs)), vocabs):
        mark = "✅" if used.get(v.word) else "⬜"
        example = f'<div class="vg-list-ex">例:{escape(v.example_1)}</div>' if v.example_1 else ""
        col.markdown(
            '<div class="vg-card vg-wordcard">'
            f'<div class="vg-list-word">{mark} {ruby_html(v.word, v.reading)}</div>'
            f'<div class="vg-list-text">{escape(v.meaning)}</div>{example}</div>',
            unsafe_allow_html=True,
        )


def vocab_card(v: Vocab, review: ReviewState | None = None, show_meta: bool = True) -> None:
    """語彙 1 件の詳細をカードとして表示する。空の項目は表示しない。

    review を渡すと、習得状況と次回復習日も表示する。
    """
    e = lambda s: escape(str(s))  # noqa: E731  ユーザー入力を安全に HTML に埋め込む

    mastery = review.mastery if review else mastery_label(None)
    parts = [
        '<div class="vg-card">',
        f'<span class="vg-badge">{e(v.category)}</span>'
        f'<span class="vg-badge vg-badge-sub">{mastery}</span>'
        f'<span class="vg-stars" title="難易度 {v.difficulty}">{stars(v.difficulty)}</span>',
        f'<p class="vg-word">{ruby_html(v.word, v.reading)}</p>',
        f'<p class="vg-meaning">{e(v.meaning)}</p>',
    ]

    examples = [x for x in (v.example_1, v.example_2) if x]
    if examples:
        parts.append('<p class="vg-label">例文</p>')
        parts.extend(f'<p class="vg-text">・{e(x)}</p>' for x in examples)

    if v.nuance:
        parts.append(f'<p class="vg-label">{FIELD_LABELS["nuance"]}</p>')
        parts.append(f'<p class="vg-text">{e(v.nuance)}</p>')

    for name in ("synonyms", "antonyms", "collocations"):
        terms = split_terms(getattr(v, name))
        if terms:
            parts.append(f'<p class="vg-label">{FIELD_LABELS[name]}</p>')
            parts.append("".join(f'<span class="vg-chip">{e(t)}</span>' for t in terms))

    if v.source:
        parts.append(f'<p class="vg-label">{FIELD_LABELS["source"]}</p>')
        parts.append(f'<p class="vg-text">{e(v.source)}</p>')

    if review:
        parts.append('<p class="vg-label">学習状況</p>')
        parts.append(
            f'<p class="vg-text">次回復習 {e(review.next_review)}(間隔 {review.interval_days}日)'
            f" ・ 正解 {review.correct_count} / 自信なし {review.unsure_count}"
            f" / 不正解 {review.wrong_count}</p>"
        )

    if show_meta:
        parts.append(
            f'<p class="vg-meta">ID {v.id} ・ 登録 {e(v.created_at or "-")}'
            f" ・ 更新 {e(v.updated_at or '-')}</p>"
        )
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


# ---------- 入力フォーム(追加・編集で共通) ----------


def vocab_form(
    key: str,
    categories: list[str],
    initial: Vocab | None = None,
    submit_label: str = "保存",
) -> Vocab | None:
    """語彙の入力フォームを表示する。送信されて入力に問題が無ければ Vocab を返す。

    問題がある場合はフォーム内にエラーを表示して None を返す(入力内容は残る)。
    """
    v = initial or Vocab(word="", meaning="")
    options = categories if categories else [UNCATEGORIZED]
    cat_index = options.index(v.category) if v.category in options else 0

    with st.form(key, border=True):
        c1, c2 = st.columns(2)
        word = c1.text_input("語彙 *", v.word, placeholder="例:俯瞰")
        reading = c2.text_input("読み", v.reading, placeholder="例:ふかん")
        meaning = st.text_area("意味 *", v.meaning, height=80)

        c1, c2 = st.columns(2)
        example_1 = c1.text_input("例文1", v.example_1)
        example_2 = c2.text_input("例文2", v.example_2)
        nuance = st.text_area(
            "ニュアンス", v.nuance, height=68, placeholder="似た言葉との違い、使う場面など"
        )

        c1, c2, c3 = st.columns(3)
        help_terms = "複数ある場合はカンマ(,)または読点(、)で区切ります"
        synonyms = c1.text_input("類義語", v.synonyms, help=help_terms)
        antonyms = c2.text_input("対義語", v.antonyms, help=help_terms)
        collocations = c3.text_input("コロケーション", v.collocations, help=help_terms)

        c1, c2, c3 = st.columns([1, 1, 1])
        category = c1.selectbox("カテゴリ", options, index=cat_index)
        new_category = c2.text_input(
            "新しいカテゴリ(任意)",
            placeholder="入力するとこちらが優先されます",
            help="候補に無いカテゴリを使いたいときに入力します。次回から候補に表示されます。",
        )
        difficulty = c3.slider(
            "難易度",
            DIFFICULTY_MIN,
            DIFFICULTY_MAX,
            v.difficulty or DEFAULT_DIFFICULTY,
            help="1 = やさしい 〜 5 = むずかしい",
        )
        source = st.text_input("出典", v.source, placeholder="本のタイトル、記事のURLなど")

        submitted = st.form_submit_button(submit_label, type="primary")

    if not submitted:
        return None

    result = Vocab(
        id=v.id,
        word=word,
        reading=reading,
        meaning=meaning,
        example_1=example_1,
        example_2=example_2,
        nuance=nuance,
        synonyms=synonyms,
        antonyms=antonyms,
        collocations=collocations,
        category=new_category.strip() or category,
        difficulty=difficulty,
        source=source,
    ).normalized()

    errors = result.validate()
    if errors:
        st.error("入力内容を確認してください。\n\n" + "\n".join(f"- {m}" for m in errors))
        return None
    return result
