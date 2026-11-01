"""フラッシュカード画面:設定 → 出題(答えを確認して自己採点)→ 結果。

画面の状態(今何枚目か、答えを表示中か など)は session_state に保存している。
項目の一覧は vorge/flashcard/session.py を参照。
"""


import pandas as pd
import streamlit as st

from vorge import timeutil
from vorge.flashcard import scheduler, session
from vorge.flashcard.repository import ReviewRepository
from vorge.ui.components import flash_front, vocab_card
from vorge.ui.persist import load_settings, save_setting
from vorge.vocab.repository import VocabRepository

vocab_repo = VocabRepository()
review_repo = ReviewRepository()
ss = st.session_state
session.init(ss)

# ---------- 出題の設定(前回の選択を DB から読み込み、変更したら保存する) ----------
DEFAULT_DIFFICULTY = (1, 5)
load_settings({
    "fc_setting_mode": scheduler.MODE_WORD_TO_MEANING,
    "fc_setting_categories": [],
    "fc_setting_difficulty": DEFAULT_DIFFICULTY,
    "fc_setting_new_limit": 10,
    "fc_setting_shuffle": True,
})
if not (isinstance(ss.fc_setting_difficulty, (list, tuple)) and len(ss.fc_setting_difficulty) == 2):
    ss.fc_setting_difficulty = DEFAULT_DIFFICULTY
ss.fc_setting_difficulty = tuple(ss.fc_setting_difficulty)


def save_difficulty() -> None:
    # 範囲スライダーは value を明示しないと 1 つの値のスライダーになるため、ウィジェット用のキーを分けている
    ss.fc_setting_difficulty = tuple(ss.fc_difficulty_widget)
    save_setting("fc_setting_difficulty")


# ============ 設定画面 ============
def show_settings() -> None:
    today = timeutil.today()
    if vocab_repo.count() == 0:
        st.info("出題できる語彙がありません。先に語彙を登録してください。")
        st.page_link("views/csv_io.py", label="CSVから読み込む", icon=":material/upload:")
        return

    c1, c2, c3 = st.columns(3)
    with c1.container(border=True):
        st.metric("今日の復習予定", f"{review_repo.count_due(today)} 語")
    with c2.container(border=True):
        st.metric("まだ学習していない語彙", f"{review_repo.count_unstudied()} 語")
    with c3.container(border=True):
        st.metric("今日の回答数", f"{review_repo.count_answers_on(today)} 回")

    with st.container(border=True):
        st.markdown("#### 出題の設定")
        mode = st.radio(
            "出題モード",
            list(scheduler.MODE_LABELS),
            format_func=scheduler.MODE_LABELS.get,
            horizontal=True,
            key="fc_setting_mode",
            on_change=save_setting,
            args=("fc_setting_mode",),
            help="「語彙 → 意味」は語彙を見て意味を思い出します。「意味 → 語彙」はその逆です。",
        )
        c1, c2 = st.columns(2)
        all_categories = vocab_repo.list_categories()
        # 保存したカテゴリが削除されている場合に備えて、今あるものだけに絞る
        valid = [c for c in ss.fc_setting_categories if c in all_categories]
        if valid != ss.fc_setting_categories:
            ss.fc_setting_categories = valid
        categories = c1.multiselect(
            "カテゴリ", all_categories, placeholder="すべて", key="fc_setting_categories",
            on_change=save_setting, args=("fc_setting_categories",),
        )
        difficulty = c2.select_slider(
            "難易度", options=[1, 2, 3, 4, 5], value=ss.fc_setting_difficulty,
            key="fc_difficulty_widget", on_change=save_difficulty,
        )
        c1, c2 = st.columns(2)
        new_limit = c1.number_input(
            "新しく覚える語彙の数",
            min_value=0,
            max_value=100,
            step=5,
            key="fc_setting_new_limit",
            on_change=save_setting,
            args=("fc_setting_new_limit",),
            help="復習予定の語彙はすべて出題され、そのあとにこの数だけ未学習の語彙が出ます。",
        )
        shuffle = c2.toggle(
            "出題順をシャッフル", key="fc_setting_shuffle", on_change=save_setting,
            args=("fc_setting_shuffle",),
        )

        due = review_repo.due_ids(today, categories, difficulty)
        n_new = min(int(new_limit), len(review_repo.new_ids(categories, difficulty)))
        total = len(due) + n_new

        st.write(f"今回の出題:復習 **{len(due)}** 枚 + 新規 **{n_new}** 枚 = **{total}** 枚")
        if total == 0:
            st.success(
                "🎉 この条件で今日出題する語彙はありません。"
                "新しい語彙を覚える場合は「新しく覚える語彙の数」を増やすか、条件を変えてください。"
            )
        if st.button("▶ 学習をはじめる", type="primary", disabled=total == 0):
            queue = review_repo.build_queue(today, int(new_limit), categories, difficulty, shuffle)
            session.start(ss, queue, mode)
            st.rerun()

    with st.expander("復習のタイミングのしくみ"):
        st.markdown(
            "- **正解** → 次の復習までの間隔が約 2.5 倍に延びます(1日 → 3日 → 8日 → 20日 …)\n"
            "- **自信がない** → 間隔はそのまま\n"
            "- **不正解** → 翌日にもう一度出題されます\n\n"
            "間隔が 7 日以上で「定着中」、21 日以上で「習得」になります。"
        )


# ============ 出題画面 ============
def show_card() -> None:
    queue, pos = ss.fc_queue, ss.fc_pos
    vocab = vocab_repo.get(queue[pos])
    if vocab is None:  # 学習中に別の画面で削除された場合は飛ばす
        ss.fc_pos += 1
        st.rerun()

    state = review_repo.get_state(vocab.id)
    retry = session.is_retry(ss, pos)
    label = f"{ss.fc_label} ・ " if ss.fc_label else ""
    st.progress(pos / len(queue), text=f"{label}{pos + 1} / {len(queue)} 枚目")

    if not ss.fc_revealed:
        # 問題面:答えを隠して、語彙(または意味)だけを大きく表示する
        if retry:
            kind = "🔂 もう一度(さっき間違えた語彙)"
        else:
            kind = "🆕 新しい語彙" if state is None else f"🔁 復習({state.mastery})"
        if ss.fc_mode == scheduler.MODE_WORD_TO_MEANING:
            flash_front(vocab.word, label=f"{kind} ・ この語彙の意味は?")
        else:
            flash_front(
                vocab.meaning, sub=f"カテゴリ:{vocab.category}", label=f"{kind} ・ この意味の語彙は?"
            )
        if st.button("答えを見る", type="primary", width="stretch"):
            ss.fc_revealed = True
            st.rerun()
    else:
        # 答え面:スクロールせずに押せるよう、採点ボタンを詳細カードより上に置く
        st.markdown("**思い出せましたか?**")
        if retry:
            st.caption("この回答は記録しません(復習日は 1 回目の回答で決まっています)。")
        current = state.interval_days if state else None
        cols = st.columns(3)
        buttons = [
            (scheduler.CORRECT, "✅", "primary"),
            (scheduler.UNSURE, "🤔", "secondary"),
            (scheduler.WRONG, "❌", "secondary"),
        ]
        for col, (result, icon, btn_type) in zip(cols, buttons):
            days = scheduler.next_interval(current, result)
            label = f"{icon} {scheduler.RESULT_LABELS[result]}"
            if not retry:
                label += f"({scheduler.interval_text(days)})"
            if col.button(label, key=f"answer_{result}_{pos}", type=btn_type, width="stretch"):
                if retry:
                    ss.fc_retry_results.append(result)
                else:
                    new_state = review_repo.record_answer(vocab.id, result, ss.fc_mode)
                    ss.fc_results.append(
                        {
                            "語彙": vocab.word,
                            "結果": scheduler.RESULT_LABELS[result],
                            "次回復習": new_state.next_review,
                            "習得状況": new_state.mastery,
                        }
                    )
                    if result == scheduler.WRONG:
                        session.add_retry(ss, vocab.id)
                ss.fc_pos += 1
                ss.fc_revealed = False
                st.rerun()
        vocab_card(vocab, state, show_meta=False)

    st.write("")
    if st.button("中断して結果を見る", help="ここまでの回答は保存されています。"):
        ss.fc_queue = queue[:pos]
        st.rerun()


# ============ 結果画面 ============
def show_summary() -> None:
    results = ss.fc_results
    if not results:
        st.info("回答した語彙はありませんでした。")
    else:
        st.subheader("🎉 おつかれさまでした!")
        counts = pd.Series([r["結果"] for r in results]).value_counts()
        c1, c2, c3 = st.columns(3)
        for col, result in zip((c1, c2, c3), scheduler.RESULTS):
            label = scheduler.RESULT_LABELS[result]
            with col.container(border=True):
                st.metric(label, f"{counts.get(label, 0)} 語")
        st.dataframe(pd.DataFrame(results), hide_index=True, width="stretch")
        retries = ss.fc_retry_results
        if retries:
            ok = retries.count(scheduler.CORRECT)
            st.caption(f"🔂 間違えた語彙のもう一度:{ok} / {len(retries)} 語を思い出せました。")
        st.caption("不正解の語彙は明日また出題されます。")

    c1, c2, _ = st.columns([1, 1, 2])
    if c1.button("設定に戻る", type="primary", width="stretch"):
        session.reset(ss)
        st.rerun()
    c2.page_link("views/home.py", label="ホームへ", icon=":material/home:")


# ============ 画面の切り替え ============
_, center, _ = st.columns([1, 4, 1])
with center:
    st.title("フラッシュカード")
    if ss.fc_queue is None:
        show_settings()
    elif ss.fc_pos >= len(ss.fc_queue):
        show_summary()
    else:
        show_card()
