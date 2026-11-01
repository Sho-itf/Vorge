"""Vorge の起動ファイル。

実行方法:  streamlit run app.py

ここでは「DB の準備」と「サイドバーのナビゲーション」だけを行い、
各画面の中身は views/ フォルダのファイルに書く。
"""

import streamlit as st

from vorge import backup, config, timeutil
from vorge.db import init_db
from vorge.settings import get_setting
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

# 「今日」の区切り時刻(設定画面で変更できる)
timeutil.set_day_start_hour(get_setting(timeutil.SETTING_KEY, timeutil.DEFAULT_DAY_START_HOUR))

# 自動バックアップ(1 日 1 回。ブラウザのセッションごとに 1 回だけ確認する)
if "auto_backup_checked" not in st.session_state:
    st.session_state.auto_backup_checked = True
    try:
        backup.auto_backup()
    except OSError as e:  # バックアップに失敗しても学習は続けられるようにする
        st.toast(f"自動バックアップに失敗しました: {e}", icon="⚠️")

# 新しい画面を追加するときは、ここに st.Page を 1 行足す
pages = {
    "学習": [
        st.Page("views/home.py", title="ホーム", icon=":material/home:", default=True),
        st.Page("views/flashcard.py", title="フラッシュカード", icon=":material/style:"),
        st.Page("views/quiz.py", title="穴埋めクイズ", icon=":material/quiz:"),
        st.Page("views/writing.py", title="作文トレーニング", icon=":material/edit_note:"),
        st.Page("views/debate.py", title="議論トレーニング", icon=":material/forum:"),
        st.Page("views/reading.py", title="読解トレーニング", icon=":material/chrome_reader_mode:"),
    ],
    "記録・データ": [
        st.Page("views/history.py", title="学習履歴", icon=":material/insights:"),
        st.Page("views/library.py", title="語彙ライブラリ", icon=":material/menu_book:"),
        st.Page("views/csv_io.py", title="データ管理", icon=":material/database:"),
        st.Page("views/settings.py", title="設定", icon=":material/settings:"),
    ],
}

navigation = st.navigation(pages)

show_flash()
navigation.run()
