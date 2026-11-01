"""ホーム画面:学習状況のまとめと、各機能への入口。"""

from html import escape

import streamlit as st

from vorge import daily, timeutil
from vorge.flashcard import scheduler, session
from vorge.flashcard.repository import ReviewRepository
from vorge.history.repository import HistoryRepository
from vorge.settings import get_setting
from vorge.ui.components import html
from vorge.vocab.repository import VocabRepository

repo = VocabRepository()
review_repo = ReviewRepository()
total = repo.count()

st.title("📚 Vorge")
st.caption("語彙を増やし、考えを言葉にする力を鍛えるための個人用トレーニングアプリ")

# ---------- 初回起動時の案内 ----------
if total == 0:
    with st.container(border=True):
        st.subheader("ようこそ!まずは語彙を登録しましょう")
        st.markdown(
            "1. **データ管理** で同梱のサンプル語彙(200語)や手持ちの CSV を読み込む\n"
            "2. または **語彙ライブラリ** の「新規追加」から 1 語ずつ登録する"
        )
        c1, c2, _ = st.columns([1, 1, 2])
        c1.page_link("views/csv_io.py", label="CSVを読み込む", icon=":material/upload:")
        c2.page_link("views/library.py", label="語彙を追加する", icon=":material/add:")
    st.write("")

# ---------- 今日の学習 ----------
today = timeutil.today()


def start_next(task: daily.DailyTask) -> None:
    """次のメニューに取り組む。復習・新しい語彙はフラッシュカードをすぐ始める。"""
    if task.key in ("review", "new"):
        goal_new = daily.goals()["daily_new"]
        remaining_new = max(goal_new - review_repo.count_new_studied_on(today), 0)
        queue = review_repo.build_queue(today, remaining_new)
        session.init(st.session_state)
        session.start(
            st.session_state, queue,
            get_setting("fc_setting_mode", scheduler.MODE_WORD_TO_MEANING),
            label="今日の学習", input_answer=bool(get_setting("fc_setting_input", False)),
        )
    st.switch_page(task.page)


if total > 0:
    tasks = daily.today_tasks(today)
    done = sum(t.done for t in tasks)
    streak = HistoryRepository().streak(today)
    st.subheader("今日の学習")
    with st.container(border=True):
        st.progress(done / len(tasks), text=f"{done} / {len(tasks)} 完了 ・ 🔥 連続 {streak} 日")
        for task in tasks:
            c1, c2, c3 = st.columns([3, 2, 1.2], vertical_alignment="center")
            html(c1, f'<div class="vg-list-text">{"✅" if task.done else "⬜"} {task.label}</div>')
            html(c2, f'<div class="vg-list-ex">{task.progress_text}</div>')
            if not task.done:
                c3.page_link(task.page, label="やる", icon=":material/arrow_forward:")
        nxt = daily.next_task(tasks)
        if nxt is None:
            st.success("🎉 今日のメニューはすべて完了です。おつかれさまでした!")
        elif st.button(f"▶ 続きから:{nxt.label}", type="primary"):
            start_next(nxt)
        st.caption("1 日の目標は「設定」で変えられます。")

st.write("")
c1, c2 = st.columns(2)
with c1.container(border=True):
    st.metric("登録語彙数", f"{total} 語")
with c2.container(border=True):
    st.metric("今日追加した語彙", f"{repo.count_added_on(today)} 語", help="今日ライブラリに登録した語彙の数です。")

st.write("")

# ---------- 機能メニュー ----------
st.subheader("機能")
features = [
    ("views/flashcard.py", "フラッシュカード", ":material/style:",
     "意味を隠して覚えているか確認し、復習日を自動で決める"),
    ("views/quiz.py", "穴埋めクイズ", ":material/quiz:",
     "例文の空欄に入る語彙を選び、文脈での使い分けを確かめる"),
    ("views/writing.py", "作文トレーニング", ":material/edit_note:",
     "お題と指定の語彙で文章を書き、使い方を身につける"),
    ("views/reading.py", "読解トレーニング", ":material/chrome_reader_mode:",
     "読んだ文章から語彙を拾って登録し、要約で理解を深める"),
    ("views/debate.py", "議論トレーニング", ":material/forum:",
     "型に沿って主張・根拠・反論・再反論を組み立てる"),
    ("views/history.py", "学習履歴", ":material/insights:",
     "回答数・正答率の推移と、苦手な語彙を確認する"),
    ("views/library.py", "語彙ライブラリ", ":material/menu_book:",
     "語彙の検索・閲覧・追加・編集・削除"),
    ("views/csv_io.py", "データ管理", ":material/database:",
     "CSV の取り込み・書き出しと、バックアップ・復元"),
]
PER_ROW = 3
for start in range(0, len(features), PER_ROW):
    for col, (page, label, icon, desc) in zip(st.columns(PER_ROW), features[start:start + PER_ROW]):
        with col.container(border=True):
            st.page_link(page, label=label, icon=icon)
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
