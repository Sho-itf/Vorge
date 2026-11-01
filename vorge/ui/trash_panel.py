"""「データ管理」画面の「🗑 ゴミ箱」タブ:削除した語彙・作文を元に戻す、または完全に削除する。"""

from html import escape

import streamlit as st

from vorge.ui.components import html, set_flash
from vorge.vocab.repository import VocabRepository
from vorge.writing.repository import WritingRepository


def _confirm_purge(label: str, key: str) -> bool:
    """「完全に削除」の確認(ポップオーバーの中でもう一度押してもらう)。"""
    with st.popover(label):
        st.write("完全に削除すると、学習記録なども一緒に消え、元に戻せません。")
        return st.button("完全に削除する", key=key, type="primary")


def show_trash_panel() -> None:
    vocab_repo = VocabRepository()
    writing_repo = WritingRepository()
    vocabs = vocab_repo.list_trash()
    writings = writing_repo.list_trash()

    if not vocabs and not writings:
        st.info("ゴミ箱は空です。語彙や作文を削除すると、ここに入ります(自分で空にするまで残ります)。")
        return

    st.markdown(f"#### 語彙({len(vocabs)} 件)")
    if not vocabs:
        st.caption("ゴミ箱に語彙はありません。")
    for v in vocabs:
        c1, c2, c3 = st.columns([5, 1.2, 1.4], vertical_alignment="center")
        html(c1, f"<b>{escape(v.word)}</b> <span class='vg-muted'>— {escape(v.meaning)}"
                 f" ・ 削除 {escape(v.deleted_at or '')[:16]}</span>")
        if c2.button("元に戻す", key=f"restore_vocab_{v.id}"):
            vocab_repo.restore(v.id)
            set_flash(f"「{v.word}」を元に戻しました")
            st.rerun()
        with c3:
            if _confirm_purge("完全に削除", f"purge_vocab_{v.id}"):
                vocab_repo.purge(v.id)
                set_flash(f"「{v.word}」を完全に削除しました")
                st.rerun()

    st.markdown(f"#### 作文・議論({len(writings)} 件)")
    if not writings:
        st.caption("ゴミ箱に作文はありません。")
    for w in writings:
        c1, c2, c3 = st.columns([5, 1.2, 1.4], vertical_alignment="center")
        html(c1, f"<b>{escape(w.prompt_text)}</b> <span class='vg-muted'>— {w.created_at[:10]} ・ "
                 f"{w.char_count}字 ・ 削除 {escape(w.deleted_at or '')[:16]}</span>")
        if c2.button("元に戻す", key=f"restore_writing_{w.id}"):
            writing_repo.restore_writing(w.id)
            set_flash("作文を元に戻しました")
            st.rerun()
        with c3:
            if _confirm_purge("完全に削除", f"purge_writing_{w.id}"):
                writing_repo.purge_writing(w.id)
                set_flash("作文を完全に削除しました")
                st.rerun()

    st.divider()
    with st.popover("🗑 ゴミ箱を空にする"):
        st.write(f"語彙 {len(vocabs)} 件・作文 {len(writings)} 件を完全に削除します。元に戻せません。")
        if st.button("すべて完全に削除する", type="primary", key="empty_trash"):
            vocab_repo.empty_trash()
            writing_repo.empty_trash()
            set_flash("ゴミ箱を空にしました")
            st.rerun()
