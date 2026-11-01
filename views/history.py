"""学習履歴画面:学習の続き具合、正答率、苦手な語彙、今後の復習予定。"""

from datetime import timedelta

import altair as alt
import pandas as pd
import streamlit as st

from vorge import timeutil
from vorge.flashcard import scheduler, session
from vorge.history.repository import HistoryRepository
from vorge.quiz.repository import QuizRepository
from vorge.writing.repository import WritingRepository

repo = HistoryRepository()
writing_repo = WritingRepository()
quiz_repo = QuizRepository()
today = timeutil.today()

# 回答結果の色(状態を表す色。正解=緑、自信がない=黄、不正解=赤)。凡例とツールチップで文字でも区別できる
RESULT_COLORS = {"正解": "#0ca30c", "自信がない": "#fab219", "不正解": "#d03b3b"}

# 日付の軸は「10/29」の形で、棒の真下に表示する(sort=None でデータの並び = 日付順のまま)
DATE_AXIS = alt.X(
    "ラベル:O", sort=None, title=None, axis=alt.Axis(labelAngle=0, labelOverlap=True)
)
DATE_TOOLTIP = alt.Tooltip("日付:N", title="日付")


def with_labels(df: pd.DataFrame) -> pd.DataFrame:
    """日付列(date)から、軸用「10/29」とツールチップ用「2026-10-29」の文字列を作る。"""
    days = pd.to_datetime(df["日付"])
    return df.assign(ラベル=days.dt.strftime("%m/%d"), 日付=days.dt.strftime("%Y-%m-%d"))


def daily_chart(wide: pd.DataFrame) -> alt.Chart:
    """日ごとの回答数の積み上げ棒グラフ(下から 正解 → 自信がない → 不正解)。"""
    long = with_labels(wide).melt(["日付", "ラベル"], var_name="結果", value_name="回答数")
    long["順"] = long["結果"].map({name: i for i, name in enumerate(RESULT_COLORS)})
    return (
        alt.Chart(long, height=280)
        .mark_bar()
        .encode(
            x=DATE_AXIS,
            y=alt.Y("回答数:Q", title="回答数", stack=True, axis=alt.Axis(tickMinStep=1)),
            color=alt.Color(
                "結果:N",
                scale=alt.Scale(domain=list(RESULT_COLORS), range=list(RESULT_COLORS.values())),
                legend=alt.Legend(title=None, orient="top"),
            ),
            order=alt.Order("順:Q"),
            tooltip=[DATE_TOOLTIP, "結果:N", "回答数:Q"],
        )
    )

st.title("学習履歴")

if repo.total_answers() == 0:
    st.info(
        "まだ学習の記録がありません。\n\n"
        "フラッシュカードで回答すると、ここに日ごとの回答数や苦手な語彙が表示されます。"
    )
    st.page_link("views/flashcard.py", label="フラッシュカードを始める", icon=":material/play_arrow:")
    st.stop()

# ---------- 全体の数字 ----------
week_start = today - timedelta(days=6)
recent = repo.accuracy_between(week_start, today)
previous = repo.accuracy_between(week_start - timedelta(days=7), week_start - timedelta(days=1))

c1, c2, c3, c4, c5 = st.columns(5)
with c1.container(border=True):
    st.metric("連続学習日数", f"{repo.streak(today)} 日", help="今日(まだなら昨日)まで毎日続いている日数")
with c2.container(border=True):
    st.metric(
        "直近7日の正答率",
        f"{recent:.0%}" if recent is not None else "—",
        delta=(
            f"{(recent - previous) * 100:+.0f}ポイント"
            if recent is not None and previous is not None
            else None
        ),
        help="正解 ÷ 全回答(「自信がない」は正解に含めません)。矢印はその前の7日との比較です。",
    )
with c3.container(border=True):
    st.metric("学習した語彙", f"{repo.studied_vocab_count()} 語")
with c4.container(border=True):
    st.metric("総回答数", f"{repo.total_answers()} 回")
with c5.container(border=True):
    st.metric(
        "作文・議論",
        f"{writing_repo.count_writings()} 本",
        help="作文トレーニング・議論トレーニングで保存した数"
        f"(書いた日数:{writing_repo.count_writing_days()} 日)",
    )

# ---------- 日ごとの回答数 ----------
st.write("")
head, control = st.columns([3, 2])
head.subheader("日ごとの回答数")
period = control.segmented_control(
    "期間", ["7日", "30日", "90日"], default="30日", label_visibility="collapsed"
) or "30日"
days = int(period.removesuffix("日"))

daily = repo.daily_counts(today - timedelta(days=days - 1), today)
chart = pd.DataFrame(
    {
        "日付": [pd.Timestamp(d.day) for d in daily],
        "正解": [d.correct for d in daily],
        "自信がない": [d.unsure for d in daily],
        "不正解": [d.wrong for d in daily],
    }
)
st.altair_chart(daily_chart(chart), width="stretch")
with st.expander("表で見る"):
    table = chart.assign(日付=chart["日付"].dt.strftime("%Y-%m-%d"))
    table["合計"] = table[list(RESULT_COLORS)].sum(axis=1)
    st.dataframe(table[table["合計"] > 0].iloc[::-1], hide_index=True, width="stretch")

# ---------- 習得状況 / 今後の復習予定 ----------
st.write("")
left, right = st.columns(2, gap="large")
with left:
    st.subheader("習得状況")
    dist = repo.mastery_distribution()
    cols = st.columns(4)
    for col, (label, count) in zip(cols, dist.items()):
        with col.container(border=True):
            st.metric(label, f"{count}")
    st.caption("学習中:復習間隔 7日未満 / 定着中:7〜20日 / 習得:21日以上")

with right:
    st.subheader("今後7日の復習予定")
    upcoming = repo.upcoming_reviews(today, 7)
    upcoming_df = pd.DataFrame(
        {"日付": [pd.Timestamp(d) for d, _ in upcoming], "語彙数": [n for _, n in upcoming]}
    )
    st.altair_chart(
        alt.Chart(with_labels(upcoming_df), height=200)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=DATE_AXIS,
            y=alt.Y("語彙数:Q", title="語彙数", axis=alt.Axis(tickMinStep=1)),
            tooltip=[DATE_TOOLTIP, alt.Tooltip("語彙数:Q", title="復習予定")],
        ),
        width="stretch",
    )
    st.caption("今日の分には、期限を過ぎた語彙も含みます。")

# ---------- 苦手な語彙 ----------
st.write("")
st.subheader("苦手な語彙")
st.caption(
    "フラッシュカードと穴埋めクイズの結果を合わせた正答率が 80% 未満で、間違えたことのある語彙です"
    "(「自信がない」は 0.5 回の正解として数えます)。作文・議論・クイズの「苦手な語彙から」も同じ判定です。"
)
weak = repo.weak_vocab(limit=20)
if not weak:
    st.success("今のところ苦手な語彙はありません。")
else:
    st.dataframe(
        pd.DataFrame(
            {
                "語彙": [w.word for w in weak],
                "意味": [w.meaning for w in weak],
                "正答率": [w.accuracy * 100 for w in weak],
                "カード 正/?/×": [f"{w.correct_count} / {w.unsure_count} / {w.wrong_count}"
                                 for w in weak],
                "クイズ 正/×": [f"{w.quiz_correct} / {w.quiz_wrong}" for w in weak],
                "次回復習": [w.next_review or "未学習" for w in weak],
            }
        ),
        hide_index=True,
        width="stretch",
        column_config={
            "意味": st.column_config.TextColumn(width="medium"),
            "正答率": st.column_config.ProgressColumn(
                format="%.0f%%", min_value=0, max_value=100, width="small"
            ),
        },
    )
    c1, c2, _ = st.columns([1.2, 1.4, 2])
    mode = c1.selectbox(
        "出題モード",
        list(scheduler.MODE_LABELS),
        format_func=scheduler.MODE_LABELS.get,
        label_visibility="collapsed",
    )
    if c2.button(f"🃏 苦手な語彙を練習する({len(weak)}語)", type="primary", width="stretch"):
        session.start(st.session_state, [w.vocab_id for w in weak], mode, label="苦手な語彙")
        st.switch_page("views/flashcard.py")
    st.caption(
        "練習の回答も通常どおり記録され、次回復習日が更新されます。"
        "正答率が上がると、このリストから外れていきます。"
    )

# ---------- 穴埋めクイズ ----------
st.write("")
st.subheader("穴埋めクイズ")
if quiz_repo.total_answers() == 0:
    st.caption("まだクイズの記録はありません。")
else:
    quiz_recent = quiz_repo.accuracy_between(week_start, today)
    c1, c2, _ = st.columns([1, 1, 2])
    with c1.container(border=True):
        st.metric("総回答数", f"{quiz_repo.total_answers()} 問")
    with c2.container(border=True):
        st.metric("直近7日の正答率", f"{quiz_recent:.0%}" if quiz_recent is not None else "—")
    missed = quiz_repo.most_missed(10)
    if missed:
        st.caption("クイズでよく間違える語彙")
        st.dataframe(
            pd.DataFrame(
                {
                    "語彙": [m.word for m in missed],
                    "意味": [m.meaning for m in missed],
                    "間違えた回数": [m.wrong for m in missed],
                    "出題回数": [m.total for m in missed],
                }
            ),
            hide_index=True,
            width="stretch",
        )

# ---------- 最近の回答 ----------
st.write("")
with st.expander("最近の回答(50件)"):
    logs = repo.recent_logs(50)
    st.dataframe(
        pd.DataFrame(
            {
                "日時": [r["studied_at"] for r in logs],
                "語彙": [r["word"] for r in logs],
                "モード": [scheduler.MODE_LABELS.get(r["mode"], r["mode"]) for r in logs],
                "結果": [scheduler.RESULT_LABELS[r["result"]] for r in logs],
                "次回復習": [r["next_review"] for r in logs],
            }
        ),
        hide_index=True,
        width="stretch",
    )
