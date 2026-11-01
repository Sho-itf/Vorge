"""フラッシュカード画面:設定 → 出題(答えを確認して自己採点)→ 結果。

画面の状態(今何枚目か、答えを表示中か など)は session_state に保存している。
項目の一覧は vorge/flashcard/session.py を参照。
"""


from datetime import datetime
from html import escape

import pandas as pd
import streamlit as st

from vorge import timeutil
from vorge.flashcard import scheduler, session
from vorge.flashcard.repository import ReviewRepository
from vorge.quiz.builder import blanks_for, matches_word
from vorge.ui.components import flash_front, html, vocab_card
from vorge.ui.persist import load_settings, save_setting
from vorge.ui.shortcuts import keyboard_shortcuts
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
    "fc_setting_input": False,
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
            help="「語彙 → 意味」は語彙を見て意味を思い出します。「意味 → 語彙」はその逆です。"
            "「例文の穴埋め」は、例文の空欄に入る語彙を思い出します。",
        )
        if mode != scheduler.MODE_WORD_TO_MEANING:
            st.toggle(
                "答えを入力してから確認する", key="fc_setting_input", on_change=save_setting,
                args=("fc_setting_input",),
                help="頭の中で思い出すだけでなく、実際に語彙を入力して答えます(読みのひらがなでも正解)。"
                "自分の手で答えを出すほうが、記憶に残りやすくなります。",
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
            session.start(ss, queue, mode, input_answer=bool(ss.fc_setting_input))
            st.rerun()

    with st.expander("復習のタイミングのしくみ"):
        st.markdown(
            "復習日は **FSRS** という方式で、語彙ごとに「思い出せる確率が 90% まで下がる頃」に決めます。\n\n"
            "- **簡単** → 間隔が大きく延びます\n"
            "- **正解** → 間隔が延びます(何度も正解している語彙ほど大きく延びる)\n"
            "- **自信がない** → 少しだけ延びます\n"
            "- **不正解** → すぐ(翌日〜数日後)にもう一度出題されます\n\n"
            "各ボタンには、押したときの次回の復習までの日数が表示されます。"
            "間隔が 7 日以上で「定着中」、21 日以上で「習得」になります。"
        )


# ============ 出題画面 ============
ANSWER_BUTTONS = [  # (回答, アイコン, キーボード)
    (scheduler.WRONG, "❌", "1"),
    (scheduler.UNSURE, "🤔", "2"),
    (scheduler.CORRECT, "✅", "3"),
    (scheduler.EASY, "🌟", "4"),
]


def cloze_blank(vocab, pos: int):
    """穴埋めモードで使う例文の空欄。例文が無ければ None(そのカードは「意味 → 語彙」で出す)。"""
    blanks = blanks_for(vocab)
    return blanks[pos % len(blanks)] if blanks else None


def answers_with_word() -> bool:
    """語彙を答える出題か(「意味 → 語彙」「例文の穴埋め」)。入力式はこのときだけ使える。"""
    return ss.fc_mode in (scheduler.MODE_MEANING_TO_WORD, scheduler.MODE_CLOZE)


def show_front(vocab, state, retry: bool, pos: int) -> None:
    """問題面:答えを隠して、語彙・意味・例文の空欄のどれかを大きく表示する。"""
    if retry:
        kind = "🔂 もう一度(さっき間違えた語彙)"
    else:
        kind = "🆕 新しい語彙" if state is None else f"🔁 復習({state.mastery})"
    blank = cloze_blank(vocab, pos) if ss.fc_mode == scheduler.MODE_CLOZE else None
    if ss.fc_mode == scheduler.MODE_WORD_TO_MEANING:
        flash_front(vocab.word, label=f"{kind} ・ この語彙の意味は?")
    elif blank:
        html(st, '<div class="vg-card vg-flash">'
                 f'<p class="vg-label">{escape(kind)} ・ 空欄に入る語彙は?</p>'
                 f'<p class="vg-flash-text vg-long">{escape(blank.before)}'
                 '<span class="vg-blank">\u3000\u3000\u3000</span>'
                 f'{escape(blank.after)}</p>'
                 f'<p class="vg-reading">意味:{escape(vocab.meaning)}</p></div>')
    else:
        flash_front(vocab.meaning, sub=f"カテゴリ:{vocab.category}", label=f"{kind} ・ この意味の語彙は?")


def check_typed(vocab, pos: int, typed: str) -> None:
    blank = cloze_blank(vocab, pos)
    ss.fc_typed = typed or "(わからない)"
    ss.fc_typed_ok = bool(typed) and matches_word(typed, vocab.word, vocab.reading,
                                                  [blank.answer] if blank else [])
    ss.fc_revealed = True


def answer(vocab, result: str, retry: bool) -> None:
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
    ss.fc_typed = None


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
        show_front(vocab, state, retry, pos)
        if ss.fc_input and answers_with_word():
            with st.form(f"typed_{pos}", border=False):
                typed = st.text_input("答え", placeholder="語彙を入力(読みのひらがなでもOK)")
                c1, c2, _ = st.columns([1, 1, 2])
                checked = c1.form_submit_button("答え合わせ", type="primary", width="stretch")
                gave_up = c2.form_submit_button("わからない", width="stretch")
            if checked or gave_up:
                check_typed(vocab, pos, "" if gave_up else typed.strip())
                st.rerun()
        else:
            if st.button("答えを見る(Space)", type="primary", width="stretch"):
                ss.fc_revealed = True
                st.rerun()
            keyboard_shortcuts({" ": "答えを見る", "Enter": "答えを見る"})
    else:
        # 答え面:スクロールせずに押せるよう、採点ボタンを詳細カードより上に置く
        if ss.fc_typed is not None:
            if ss.fc_typed_ok:
                st.success(f"✅ 入力した答え「{ss.fc_typed}」は正解です。")
            else:
                st.error(f"❌ 入力した答え:{ss.fc_typed} / 正解:{vocab.word}")
        st.markdown("**思い出せましたか?**(キーボードの 1〜4 でも選べます)")
        if retry:
            st.caption("この回答は記録しません(復習日は 1 回目の回答で決まっています)。")
        days = {} if retry else scheduler.preview(
            state.card() if state else scheduler.load_card(""), datetime.now()
        )
        # 入力式で間違えたときは「不正解」、それ以外は「正解」を目立たせる
        suggested = scheduler.WRONG if ss.fc_typed is not None and not ss.fc_typed_ok else scheduler.CORRECT
        cols = st.columns(len(ANSWER_BUTTONS))
        for col, (result, icon, _key) in zip(cols, ANSWER_BUTTONS):
            text = f"{icon} {scheduler.RESULT_LABELS[result]}"
            if result in days:
                text += f"({scheduler.interval_text(days[result])})"
            col.button(text, key=f"answer_{result}_{pos}", width="stretch",
                       type="primary" if result == suggested else "secondary",
                       on_click=answer, args=(vocab, result, retry))
        keyboard_shortcuts({key: f"{icon} {scheduler.RESULT_LABELS[result]}" for result, icon, key in ANSWER_BUTTONS})
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
        for col, result in zip(st.columns(len(scheduler.RESULTS)), scheduler.RESULTS):
            label = scheduler.RESULT_LABELS[result]
            with col.container(border=True):
                st.metric(label, f"{counts.get(label, 0)} 語")
        st.dataframe(pd.DataFrame(results), hide_index=True, width="stretch")
        retries = ss.fc_retry_results
        if retries:
            ok = sum(r in scheduler.CORRECT_RESULTS for r in retries)
            st.caption(f"🔂 間違えた語彙のもう一度:{ok} / {len(retries)} 語を思い出せました。")
        st.caption("不正解の語彙は、近いうちにまた出題されます。")

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
