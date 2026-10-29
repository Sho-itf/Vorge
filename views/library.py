"""語彙ライブラリ画面:検索・一覧・詳細・追加・編集・削除。"""

import pandas as pd
import streamlit as st

from vorge.flashcard.repository import ReviewRepository
from vorge.ui.components import set_flash, stars, vocab_card, vocab_form
from vorge.vocab.models import Vocab
from vorge.vocab.repository import SORT_OPTIONS, VocabRepository

repo = VocabRepository()
review_repo = ReviewRepository()

# session_state:画面を再描画しても値を覚えておくための入れ物
st.session_state.setdefault("selected_id", None)  # 詳細表示中の語彙ID
st.session_state.setdefault("editing", False)  # 編集モードかどうか
st.session_state.setdefault("add_form_version", 0)  # 追加フォームを空に戻すための番号


@st.dialog("語彙を削除")
def confirm_delete(vocab: Vocab) -> None:
    st.write(f"「**{vocab.word}**」(ID {vocab.id})を削除します。")
    st.warning("この語彙のフラッシュカードの学習記録も一緒に削除されます。この操作は取り消せません。")
    c1, c2 = st.columns(2)
    if c1.button("削除する", type="primary", width="stretch"):
        repo.delete(vocab.id)
        st.session_state.selected_id = None
        st.session_state.editing = False
        set_flash(f"「{vocab.word}」を削除しました")
        st.rerun()
    if c2.button("キャンセル", width="stretch"):
        st.rerun()


st.title("語彙ライブラリ")
categories = repo.list_categories()
total = repo.count()

tab_list, tab_add = st.tabs(["🔍 一覧・検索", "➕ 新規追加"])

# ============ 新規追加 ============
with tab_add:
    st.caption("* は必須項目です。同じ語彙でも意味が違えば別々に登録できます。")
    new_vocab = vocab_form(
        key=f"add_form_{st.session_state.add_form_version}",
        categories=categories,
        submit_label="追加する",
    )
    if new_vocab:
        new_id = repo.add(new_vocab)
        st.session_state.add_form_version += 1  # フォームのキーを変えて入力欄を空にする
        st.session_state.selected_id = new_id
        st.session_state.editing = False
        set_flash(f"「{new_vocab.word}」を追加しました(ID {new_id})")
        st.rerun()

# ============ 一覧・検索 ============
with tab_list:
    if total == 0:
        st.info(
            "まだ語彙が登録されていません。\n\n"
            "上の「➕ 新規追加」タブから登録するか、CSV からまとめて読み込んでください。"
        )
        st.page_link("views/csv_io.py", label="CSV入出力へ", icon=":material/upload:")
        st.stop()

    # ---- 絞り込み条件 ----
    c1, c2, c3, c4 = st.columns([3, 2.2, 1.6, 1.4])
    keyword = c1.text_input(
        "キーワード",
        placeholder="語彙・読み・意味・例文など(スペースで AND 検索)",
    )
    selected_categories = c2.multiselect("カテゴリ", categories, placeholder="すべて")
    difficulty_range = c3.select_slider("難易度", options=[1, 2, 3, 4, 5], value=(1, 5))
    sort = c4.selectbox("並び順", list(SORT_OPTIONS))

    results = repo.search(keyword, selected_categories, difficulty_range, sort)

    left, right = st.columns([3, 2], gap="large")

    with left:
        st.caption(f"{len(results)} 件 / 全 {total} 件 ・ 行をクリックすると詳細を表示します")
        if not results:
            st.info("条件に一致する語彙がありません。キーワードや絞り込み条件を変えてみてください。")
        else:
            table = pd.DataFrame(
                {
                    "ID": [v.id for v in results],
                    "語彙": [v.word for v in results],
                    "読み": [v.reading for v in results],
                    "意味": [v.meaning for v in results],
                    "カテゴリ": [v.category for v in results],
                    "難易度": [stars(v.difficulty) for v in results],
                }
            )
            # 絞り込み条件が変わったら表の選択状態もリセットされるよう、条件をキーに含める
            table_key = f"vocab_table_{keyword}_{selected_categories}_{difficulty_range}_{sort}"
            event = st.dataframe(
                table,
                hide_index=True,
                width="stretch",
                height=560,
                on_select="rerun",
                selection_mode="single-row",
                key=table_key,
                column_config={
                    "ID": st.column_config.NumberColumn(width="small"),
                    "意味": st.column_config.TextColumn(width="large"),
                },
            )
            # 表の選択が「新しく変わったとき」だけ詳細表示を切り替える
            # (追加直後などに古い選択で上書きされないようにするため)
            rows = event.selection.rows
            selection = (table_key, tuple(rows))
            if rows and rows[0] < len(results) and selection != st.session_state.get("last_selection"):
                st.session_state.last_selection = selection
                st.session_state.selected_id = results[rows[0]].id
                st.session_state.editing = False

    with right:
        selected = (
            repo.get(st.session_state.selected_id)
            if st.session_state.selected_id is not None
            else None
        )
        if selected is None:
            st.session_state.editing = False
            with st.container(border=True):
                st.markdown("#### 詳細")
                st.caption("左の一覧から語彙を選ぶと、ここに例文やニュアンスなどの詳細が表示されます。")

        elif st.session_state.editing:
            st.markdown(f"#### 「{selected.word}」を編集")
            edited = vocab_form(
                key=f"edit_form_{selected.id}",
                categories=categories,
                initial=selected,
                submit_label="変更を保存",
            )
            if st.button("キャンセル"):
                st.session_state.editing = False
                st.rerun()
            if edited:
                repo.update(edited)
                st.session_state.editing = False
                set_flash(f"「{edited.word}」を更新しました")
                st.rerun()

        else:
            vocab_card(selected, review_repo.get_state(selected.id))
            c1, c2 = st.columns(2)
            if c1.button("✏️ 編集", width="stretch"):
                st.session_state.editing = True
                st.rerun()
            if c2.button("🗑️ 削除", width="stretch"):
                confirm_delete(selected)
