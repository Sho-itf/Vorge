"""Vorge の起動ファイル。

実行方法:  streamlit run app.py

ここでは「DB の準備」と「サイドバーのナビゲーション」だけを行い、
各画面の中身は views/ フォルダのファイルに書く。
"""

import streamlit as st

from vorge import config
from vorge.db import init_db
from vorge.ui.components import show_flash
from vorge.ui.theme import apply_base_style

st.set_page_config(page_title="Vorge", page_icon="📚", layout="wide")
apply_base_style()

try:
    init_db()  # テーブルが無ければ作る(既存データは消さない)
except Exception as e:  # DB ファイルが壊れている・書き込めない場合など
    st.error(
        "データベースを開けませんでした。\n\n"
        f"- ファイル: `{config.DB_PATH}`\n- 詳細: {e}\n\n"
        "ファイルが他のアプリで開かれていないか、フォルダに書き込み権限があるか確認してください。"
    )
    st.stop()

# 新しい画面を追加するときは、ここに st.Page を 1 行足す
pages = {
    "メニュー": [
        st.Page("views/home.py", title="ホーム", icon=":material/home:", default=True),
        st.Page("views/flashcard.py", title="フラッシュカード", icon=":material/style:"),
        st.Page("views/history.py", title="学習履歴", icon=":material/insights:"),
        st.Page("views/library.py", title="語彙ライブラリ", icon=":material/menu_book:"),
        st.Page("views/csv_io.py", title="CSV入出力", icon=":material/swap_vert:"),
    ],
}

navigation = st.navigation(pages)

with st.sidebar:
    st.caption("準備中の機能")
    st.markdown(
        "<div style='opacity:0.5;line-height:2'>"
        "✍️ 文章トレーニング"
        "</div>",
        unsafe_allow_html=True,
    )

show_flash()
navigation.run()
