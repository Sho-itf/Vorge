"""画面間で共通の UI 部品(語彙カード・入力フォーム・通知)。"""

from html import escape

import streamlit as st

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


def show_flash() -> None:
    flash = st.session_state.pop("_flash", None)
    if flash:
        message, kind = flash
        icon = {"success": "✅", "warning": "⚠️", "error": "❌"}.get(kind, "ℹ️")
        st.toast(message, icon=icon)


# ---------- 表示用 ----------


def stars(level: int) -> str:
    return "★" * level + "☆" * (DIFFICULTY_MAX - level)


def vocab_card(v: Vocab) -> None:
    """語彙 1 件の詳細をカードとして表示する。空の項目は表示しない。"""
    e = lambda s: escape(str(s))  # noqa: E731  ユーザー入力を安全に HTML に埋め込む

    parts = [
        '<div class="vg-card">',
        f'<span class="vg-badge">{e(v.category)}</span>'
        f'<span class="vg-stars" title="難易度 {v.difficulty}">{stars(v.difficulty)}</span>',
        f'<p class="vg-word">{e(v.word)}</p>',
        f'<p class="vg-reading">{e(v.reading)}</p>' if v.reading else "",
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
