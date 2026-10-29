"""語彙ライブラリ画面:検索・一覧・詳細(ポップアップ)・追加・編集・削除。"""

import math
from html import escape

import streamlit as st

from vorge.flashcard.repository import ReviewRepository, ReviewState
from vorge.flashcard.scheduler import mastery_label
from vorge.ui.components import (
    highlight_html,
    ruby_html,
    set_flash,
    stars,
    vocab_card,
    vocab_form,
)
from vorge.vocab.models import Vocab
from vorge.vocab.repository import SORT_OPTIONS, VocabRepository

repo = VocabRepository()
review_repo = ReviewRepository()
ss = st.session_state

# session_state:画面を再描画しても値を覚えておくための入れ物
ss.setdefault("open_id", None)  # ポップアップで開く語彙ID
ss.setdefault("dialog_mode", "view")  # ポップアップの表示内容:view / edit / delete
ss.setdefault("add_form_version", 0)  # 追加フォームを空に戻すための番号
ss.setdefault("page", 0)  # 一覧の何ページ目か(0 始まり)
ss.setdefault("filter_signature", None)  # 絞り込み条件が変わったか判定するための記録
# 一覧に追加で表示する項目(「表示する項目」メニューで切り替え。初期値はすべて非表示)
ss.setdefault("show_category", False)
ss.setdefault("show_difficulty", True)  # 難易度だけは初期状態で表示
ss.setdefault("show_mastery", False)

MASTERY_LEVELS = ["未学習", "学習中", "定着中", "習得"]


def open_detail(vocab_id: int) -> None:
    ss.open_id = vocab_id
    ss.dialog_mode = "view"


# ---------- 一覧の表示 ----------


def list_columns() -> list[tuple[str, float]]:
    """一覧の列(見出し, 幅の比率)。「表示する項目」の設定で列が増える。"""
    columns = [("語彙", 1.4), ("意味", 2.6), ("例文", 3.6)]
    if ss.show_difficulty:
        columns.append(("難易度", 0.9))  # 例文のすぐ右
    if ss.show_category:
        columns.append(("カテゴリ", 1.3))
    if ss.show_mastery:
        columns.append(("習得状況", 0.8))
    columns.append(("", 0.7))  # 「詳細」ボタン
    return columns


def html(container, body: str) -> None:
    container.markdown(body, unsafe_allow_html=True)


def show_row(v: Vocab, state: ReviewState | None, columns: list[tuple[str, float]]) -> None:
    """語彙 1 件分の行。key を付けた container には CSS 用のクラス st-key-… が付く。"""
    with st.container(key=f"vrow-{v.id}"):
        cols = st.columns([w for _, w in columns], vertical_alignment="center")
        html(cols[0], f'<div class="vg-list-word">{ruby_html(v.word, v.reading)}</div>')
        html(cols[1], f'<div class="vg-list-text">{escape(v.meaning)}</div>')
        examples = [x for x in (v.example_1, v.example_2) if x]
        html(
            cols[2],
            "".join(f'<div class="vg-list-ex">{highlight_html(x, v.word)}</div>' for x in examples)
            or '<div class="vg-list-ex vg-muted">—</div>',
        )
        for col, (name, _) in zip(cols[3:-1], columns[3:-1]):
            if name == "カテゴリ":
                html(col, f'<span class="vg-badge">{escape(v.category)}</span>')
            elif name == "難易度":
                html(col, f'<span class="vg-stars">{stars(v.difficulty)}</span>')
            elif name == "習得状況":
                html(col, f'<div class="vg-list-ex">{state.mastery if state else "未学習"}</div>')
        cols[-1].button(
            "詳細", key=f"open-{v.id}", on_click=open_detail, args=(v.id,), type="tertiary"
        )


def pager(page_count: int, position: str) -> None:
    """« 前へ  n / N ページ  次へ » の切り替え。"""
    if page_count <= 1:
        return
    c1, c2, c3 = st.columns([1, 2, 1], vertical_alignment="center")
    if c1.button("« 前へ", key=f"prev-{position}", disabled=ss.page == 0, width="stretch"):
        ss.page -= 1
        st.rerun()
    html(c2, f'<div style="text-align:center">{ss.page + 1} / {page_count} ページ</div>')
    if c3.button(
        "次へ »", key=f"next-{position}", disabled=ss.page >= page_count - 1, width="stretch"
    ):
        ss.page += 1
        st.rerun()


def show_vocab_list(results: list[Vocab], states: dict[int, ReviewState], page_size: int) -> None:
    page_count = math.ceil(len(results) / page_size)
    ss.page = min(ss.page, page_count - 1)
    page_items = results[ss.page * page_size : (ss.page + 1) * page_size]
    columns = list_columns()

    pager(page_count, "top")
    with st.container(key="vlist"):
        # 見出し行
        with st.container(key="vlist-head"):
            for col, (name, _) in zip(st.columns([w for _, w in columns]), columns):
                html(col, f'<div class="vg-list-head">{name}</div>')
        for v in page_items:
            show_row(v, states.get(v.id), columns)
    st.write("")
    pager(page_count, "bottom")


@st.dialog("語彙の詳細", width="large")
def detail_dialog(vocab_id: int, categories: list[str]) -> None:
    """語彙の詳細ポップアップ。中で「編集」「削除」に切り替えられる。

    ポップアップ内のボタン操作はポップアップだけが再描画される。
    保存・削除したときは st.rerun() で画面全体を更新し、ポップアップを閉じる。
    """
    vocab = repo.get(vocab_id)
    if vocab is None:
        st.warning("この語彙は見つかりませんでした(削除された可能性があります)。")
        return

    if ss.dialog_mode == "edit":
        edited = vocab_form(
            key=f"edit_form_{vocab.id}",
            categories=categories,
            initial=vocab,
            submit_label="変更を保存",
        )
        if edited:
            repo.update(edited)
            set_flash(f"「{edited.word}」を更新しました")
            st.rerun()
        if st.button("← 編集をやめる"):
            ss.dialog_mode = "view"
            st.rerun(scope="fragment")

    elif ss.dialog_mode == "delete":
        st.write(f"「**{vocab.word}**」(ID {vocab.id})を削除します。")
        st.warning("この語彙のフラッシュカードの学習記録も一緒に削除されます。この操作は取り消せません。")
        c1, c2 = st.columns(2)
        if c1.button("削除する", type="primary", width="stretch"):
            repo.delete(vocab.id)
            set_flash(f"「{vocab.word}」を削除しました")
            st.rerun()
        if c2.button("キャンセル", width="stretch"):
            ss.dialog_mode = "view"
            st.rerun(scope="fragment")

    else:
        vocab_card(vocab, review_repo.get_state(vocab.id))
        c1, c2, _ = st.columns([1, 1, 2])
        if c1.button("✏️ 編集", type="primary", width="stretch"):
            ss.dialog_mode = "edit"
            st.rerun(scope="fragment")
        if c2.button("🗑️ 削除", width="stretch"):
            ss.dialog_mode = "delete"
            st.rerun(scope="fragment")


st.title("語彙ライブラリ")
categories = repo.list_categories()
total = repo.count()

# ポップアップを開く(画面全体の再描画で呼ばれなくなると、ポップアップは閉じる)
if ss.open_id is not None:
    detail_dialog(ss.open_id, categories)
    ss.open_id = None

tab_list, tab_add = st.tabs(["🔍 一覧・検索", "➕ 新規追加"])

# ============ 新規追加 ============
with tab_add:
    st.caption("* は必須項目です。同じ語彙でも意味が違えば別々に登録できます。")
    new_vocab = vocab_form(
        key=f"add_form_{ss.add_form_version}",
        categories=categories,
        submit_label="追加する",
    )
    if new_vocab:
        new_id = repo.add(new_vocab)
        ss.add_form_version += 1  # フォームのキーを変えて入力欄を空にする
        open_detail(new_id)  # 追加した語彙をポップアップで表示する
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
    c1, c2, c3, c4, c5 = st.columns([3, 2, 1.6, 1.6, 1.4])
    keyword = c1.text_input(
        "キーワード",
        placeholder="語彙・読み・意味・例文など(スペースで AND 検索)",
    )
    selected_categories = c2.multiselect("カテゴリ", categories, placeholder="すべて")
    selected_mastery = c3.multiselect("習得状況", MASTERY_LEVELS, placeholder="すべて")
    difficulty_range = c4.select_slider("難易度", options=[1, 2, 3, 4, 5], value=(1, 5))
    sort = c5.selectbox("並び順", list(SORT_OPTIONS))

    states = review_repo.all_states()
    results = repo.search(keyword, selected_categories, difficulty_range, sort)
    if selected_mastery:
        results = [
            v
            for v in results
            if mastery_label(states[v.id].interval_days if v.id in states else None)
            in selected_mastery
        ]

    # 絞り込み条件が変わったら 1 ページ目に戻す
    signature = (keyword, tuple(selected_categories), tuple(selected_mastery), difficulty_range, sort)
    if signature != ss.filter_signature:
        ss.filter_signature = signature
        ss.page = 0

    # ---- 件数表示と「表示する項目」メニュー ----
    info, settings = st.columns([4, 1], vertical_alignment="center")
    info.caption(f"{len(results)} 件 / 全 {total} 件 ・ 「詳細」で例文以外の情報や編集・削除ができます")
    with settings.popover("⚙️ 表示する項目", width="stretch"):
        st.caption("一覧に追加で表示する項目")
        st.checkbox("難易度", key="show_difficulty")
        st.checkbox("カテゴリ", key="show_category")
        st.checkbox("習得状況", key="show_mastery")
        page_size = st.slider("1 ページの件数", min_value=1, max_value=100, value=25, key="page_size")

    if not results:
        st.info("条件に一致する語彙がありません。キーワードや絞り込み条件を変えてみてください。")
        st.stop()

    show_vocab_list(results, states, page_size)
