"""「これまでの作文・議論」タブ:保存した作文・議論の一覧(添削メモ・添削依頼文・削除)。"""

from html import escape

import streamlit as st

from vorge.debate import checker as debate_checker
from vorge.debate.templates import KIND_DEBATE, STANCE_LABELS, TEMPLATES
from vorge.ui.components import html, set_flash
from vorge.vocab.repository import VocabRepository
from vorge.writing import checker
from vorge.writing import prompts as P
from vorge.writing.repository import Writing, WritingRepository

# 一覧の「種類」:作文のお題の種類 + 議論トレーニングで保存したもの
HISTORY_KIND_LABELS = {**P.KIND_LABELS, KIND_DEBATE: "議論"}
PAGE_STEP = 20


def show_writing_body(w: Writing) -> None:
    """保存した作文・議論の本文。議論は欄ごとに見出しを付けて表示する。"""
    if w.kind == KIND_DEBATE and w.template in TEMPLATES:
        template = TEMPLATES[w.template]
        html(st, f'<span class="vg-badge">議論 ・ {escape(template.label)}</span>'
                 f'<span class="vg-badge vg-badge-sub">{STANCE_LABELS.get(w.stance, w.stance)}</span>')
        texts = w.section_texts
        for s in template.sections:
            html(st, f'<p class="vg-label">{escape(s.label)}</p>'
                     f'<div class="vg-essay">{escape(texts.get(s.key, ""))}</div>')
        return
    html(st, f'<span class="vg-badge">{escape(HISTORY_KIND_LABELS.get(w.kind, w.kind))}</span>'
             f'<span class="vg-badge vg-badge-sub">目安 {w.min_chars}〜{w.max_chars}字</span>')
    html(st, f'<div class="vg-essay">{escape(w.body)}</div>')


def review_prompt_for(w: Writing, vocab_repo: VocabRepository) -> str:
    """保存した作文・議論から、添削依頼文を作り直す。"""
    vocab_map = vocab_repo.get_many([x.vocab_id for x in w.words])
    pairs = [(x.word, vocab_map[x.vocab_id].meaning if x.vocab_id in vocab_map else "")
             for x in w.words]
    if w.kind == KIND_DEBATE and w.template in TEMPLATES:
        return debate_checker.build_review_prompt(
            w.prompt_text, w.stance, TEMPLATES[w.template], pairs, w.section_texts)
    return checker.build_review_prompt(w.prompt_text, pairs, w.body, w.min_chars, w.max_chars)


def show_saved_list(repo: WritingRepository, vocab_repo: VocabRepository) -> None:
    ss = st.session_state
    ss.setdefault("wr_history_limit", PAGE_STEP)
    if repo.count_writings() == 0:
        st.info("まだ保存した作文・議論はありません。")
        return

    c1, c2, c3 = st.columns([2, 2, 1])
    words = repo.written_vocab()
    vocab_filter = c1.selectbox(
        "語彙で絞り込む", [None, *[i for i, _ in words]],
        format_func=lambda i: "すべて" if i is None else dict(words)[i],
    )
    kind_filter = c2.selectbox(
        "種類", [None, *HISTORY_KIND_LABELS],
        format_func=lambda k: "すべて" if k is None else HISTORY_KIND_LABELS[k],
    )
    writings = repo.list_writings(vocab_filter, kind_filter)
    c3.metric("件数", f"{len(writings)} 件")

    for w in writings[: ss.wr_history_limit]:
        marks = " ".join(f"{'✅' if x.used else '⬜'}{x.word}" for x in w.words)
        title = f"{w.created_at[:10]} ・ {w.prompt_text} ・ {w.char_count}字 ・ {marks}"
        with st.expander(title):
            show_writing_body(w)

            with st.form(f"fb_{w.id}"):
                feedback = st.text_area("添削結果のメモ", value=w.feedback, height=120)
                if st.form_submit_button("メモを保存"):
                    repo.update_feedback(w.id, feedback)
                    set_flash("メモを保存しました")
                    st.rerun()

            c1, c2, _ = st.columns([1.3, 1, 2])
            if c1.toggle("添削依頼文を表示", key=f"show_review_{w.id}"):
                st.code(review_prompt_for(w, vocab_repo), language=None, wrap_lines=True)
            with c2.popover("🗑️ 削除"):
                st.write("この作文を削除します。取り消せません。")
                if st.button("削除する", key=f"del_{w.id}", type="primary"):
                    repo.delete_writing(w.id)
                    set_flash("作文を削除しました")
                    st.rerun()

    if len(writings) > ss.wr_history_limit:
        if st.button(f"さらに表示(残り {len(writings) - ss.wr_history_limit} 件)"):
            ss.wr_history_limit += PAGE_STEP
            st.rerun()
