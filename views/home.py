"""ホーム画面:学習状況のまとめと、各機能への入口。"""

from datetime import date
from html import escape

import streamlit as st

from vorge.vocab.repository import VocabRepository

repo = VocabRepository()
total = repo.count()

st.title("📚 Vorge")
st.caption("語彙を増やし、考えを言葉にする力を鍛えるための個人用トレーニングアプリ")

# ---------- 初回起動時の案内 ----------
if total == 0:
    with st.container(border=True):
        st.subheader("ようこそ!まずは語彙を登録しましょう")
        st.markdown(
            "1. **CSV入出力** で同梱のサンプル語彙(99語)や手持ちの CSV を読み込む\n"
            "2. または **語彙ライブラリ** の「新規追加」から 1 語ずつ登録する"
        )
        c1, c2, _ = st.columns([1, 1, 2])
        c1.page_link("views/csv_io.py", label="CSVを読み込む", icon=":material/upload:")
        c2.page_link("views/library.py", label="語彙を追加する", icon=":material/add:")
    st.write("")

# ---------- 今日の状況 ----------
st.subheader("今日の状況")
c1, c2, c3 = st.columns(3)
with c1.container(border=True):
    st.metric("登録語彙数", f"{total} 語")
with c2.container(border=True):
    st.metric(
        "今日追加した語彙",
        f"{repo.count_added_on(date.today())} 語",
        help="今日ライブラリに登録した語彙の数です。",
    )
with c3.container(border=True):
    st.metric(
        "今日の復習予定",
        "—",
        help="フラッシュカード機能を実装すると表示されます。",
    )

st.write("")

# ---------- 機能メニュー ----------
st.subheader("機能")
features = [
    ("views/library.py", "語彙ライブラリ", ":material/menu_book:",
     "語彙の検索・閲覧・追加・編集・削除", True),
    ("views/csv_io.py", "CSV入出力", ":material/swap_vert:",
     "CSV からの一括登録と、バックアップ用の書き出し", True),
    ("views/home.py", "フラッシュカード(準備中)", ":material/style:",
     "意味を隠して覚えているか確認する", False),
    ("views/home.py", "学習履歴(準備中)", ":material/insights:",
     "回答記録と次回の復習日を確認する", False),
]
cols = st.columns(len(features))
for col, (page, label, icon, desc, enabled) in zip(cols, features):
    with col.container(border=True):
        st.page_link(page, label=label, icon=icon, disabled=not enabled)
        st.markdown(f"<div class='vg-feature-desc'>{desc}</div>", unsafe_allow_html=True)

# ---------- 最近追加した語彙 ----------
if total > 0:
    st.write("")
    st.subheader("最近追加した語彙")
    for v in repo.recent(5):
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            c1.markdown(
                f"<b>{escape(v.word)}</b><br><small>{escape(v.reading)}</small>",
                unsafe_allow_html=True,
            )
            c2.markdown(escape(v.meaning), unsafe_allow_html=True)
