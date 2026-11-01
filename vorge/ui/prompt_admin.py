"""「お題の管理」タブ:作文・議論のお題の追加・編集・出題のオン/オフ・削除。"""

from html import escape

import streamlit as st

from vorge.ui.components import html, set_flash
from vorge.writing import prompts as P
from vorge.writing.repository import Prompt, WritingRepository


def show_prompt_admin(repo: WritingRepository) -> None:
    ss = st.session_state

    def toggle_prompt(p: Prompt) -> None:
        repo.update_prompt(p.id, p.kind, p.text, ss[f"active_{p.id}"])

    with st.form("add_prompt", clear_on_submit=True, border=True):
        st.markdown("**お題を追加**")
        c1, c2, c3 = st.columns([1, 3, 1], vertical_alignment="bottom")
        kind = c1.selectbox("種類", list(P.KIND_LABELS), format_func=P.KIND_LABELS.get)
        text = c2.text_input("お題", placeholder="例:最近見た映画について")
        if c3.form_submit_button("追加", type="primary", width="stretch"):
            if text.strip():
                repo.add_prompt(kind, text)
                set_flash("お題を追加しました")
                st.rerun()
            else:
                st.error("お題を入力してください。")

    kind_filter = st.segmented_control(
        "表示する種類", ["all", *P.KIND_LABELS],
        format_func=lambda k: "すべて" if k == "all" else P.KIND_LABELS[k],
        default="all",
    )
    prompts = repo.list_prompts(None if kind_filter in (None, "all") else kind_filter)
    active = sum(p.active for p in prompts)
    st.caption(f"{len(prompts)} 件(出題中 {active} 件)・ スイッチをオフにすると出題されなくなります"
               "(「意見・議論」のお題は議論トレーニングでも使われます)")

    with st.container(key="vlist"):
        for p in prompts:
            with st.container(key=f"vrow-prompt-{p.id}"):
                c1, c2, c3, c4 = st.columns([0.6, 5, 1.4, 0.9], vertical_alignment="center")
                c1.toggle("出題", value=p.active, key=f"active_{p.id}", on_change=toggle_prompt,
                          args=(p,), label_visibility="collapsed")
                muted = "" if p.active else " vg-muted"
                html(c2, f'<div class="vg-list-text{muted}">{escape(p.text)}</div>')
                html(c3, f'<span class="vg-badge">{escape(P.KIND_LABELS.get(p.kind, p.kind))}</span>')
                with c4.popover("編集"):
                    new_kind = st.selectbox(
                        "種類", list(P.KIND_LABELS), index=list(P.KIND_LABELS).index(p.kind),
                        format_func=P.KIND_LABELS.get, key=f"kind_{p.id}",
                    )
                    new_text = st.text_area("お題", value=p.text, key=f"text_{p.id}")
                    b1, b2 = st.columns(2)
                    if b1.button("保存", key=f"save_{p.id}", type="primary", width="stretch"):
                        if new_text.strip():
                            repo.update_prompt(p.id, new_kind, new_text, p.active)
                            set_flash("お題を更新しました")
                            st.rerun()
                        else:
                            st.error("お題を入力してください。")
                    if b2.button("削除", key=f"delp_{p.id}", width="stretch"):
                        repo.delete_prompt(p.id)
                        set_flash("お題を削除しました(このお題で書いた作文は残ります)")
                        st.rerun()
