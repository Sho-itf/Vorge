"""穴埋めクイズ画面:設定 → 出題(4択 / 入力式)→ 結果。

例文中の語彙を空欄にして出題する。結果はクイズ用の記録(quiz_log)に保存し、
フラッシュカードの復習日には影響させない。
"""

from html import escape

import streamlit as st

from vorge.quiz.builder import Question, is_correct_input
from vorge.quiz.repository import FORMAT_CHOICE, FORMAT_INPUT, FORMAT_LABELS, SCOPE_LABELS, QuizRepository
from vorge.ui.components import html, ruby_html
from vorge.ui.persist import load_settings, save_setting
from vorge.vocab.repository import VocabRepository

repo = QuizRepository()
vocab_repo = VocabRepository()
ss = st.session_state

# ---------- 出題条件(前回の選択を DB から読み込み、変更したら保存する) ----------
DEFAULT_DIFFICULTY = (1, 5)
load_settings({
    "qz_scope": "all",
    "qz_format": FORMAT_CHOICE,
    "qz_count": 10,
    "qz_categories": [],
    "qz_difficulty": DEFAULT_DIFFICULTY,
})
# 難易度は (下限, 上限) の 2 つの値。JSON から読むとリストになるのでタプルに直し、壊れていれば初期値に戻す
if not (isinstance(ss.qz_difficulty, (list, tuple)) and len(ss.qz_difficulty) == 2):
    ss.qz_difficulty = DEFAULT_DIFFICULTY
ss.qz_difficulty = tuple(ss.qz_difficulty)


def save_difficulty() -> None:
    # 範囲スライダーは value を明示しないと「1 つの値」のスライダーになってしまうため、
    # ウィジェット用のキー(qz_difficulty_widget)と設定用のキー(qz_difficulty)を分けている
    ss.qz_difficulty = tuple(ss.qz_difficulty_widget)
    save_setting("qz_difficulty")


# ---------- 出題中の状態 ----------
ss.setdefault("qz_questions", None)  # list[Question](None なら設定画面)
ss.setdefault("qz_pos", 0)
ss.setdefault("qz_answer", None)  # 今の問題の回答 {"given", "correct"}(未回答なら None)
ss.setdefault("qz_results", [])  # [{"vocab_id", "word", "correct", "given"}]


def start(questions: list[Question]) -> None:
    ss.qz_questions = questions
    ss.qz_pos = 0
    ss.qz_answer = None
    ss.qz_results = []


def answer(question: Question, given: str, correct: bool) -> None:
    log_id = repo.record(question.vocab_id, ss.qz_format, correct, given)
    ss.qz_answer = {"given": given, "correct": correct, "log_id": log_id}
    ss.qz_results.append(
        {"vocab_id": question.vocab_id, "word": question.word, "correct": correct, "given": given}
    )


def sentence_html(q: Question, filled: bool) -> str:
    """例文。filled=False なら空欄、True なら答えを太字で埋める。"""
    middle = f"<b>{escape(q.blank.answer)}</b>" if filled else '<span class="vg-blank">　　　</span>'
    return f"{escape(q.blank.before)}{middle}{escape(q.blank.after)}"


# ============ 設定画面 ============
def show_settings() -> None:
    eligible = repo.eligible_vocab(ss.qz_scope, ss.qz_categories, ss.qz_difficulty)
    with st.container(border=True):
        st.markdown("#### 出題の設定")
        c1, c2 = st.columns(2)
        c1.segmented_control(
            "回答の形式", list(FORMAT_LABELS), format_func=FORMAT_LABELS.get, key="qz_format",
            on_change=save_setting, args=("qz_format",),
            help="入力式は、語彙を自分で書いて答えます(読みのひらがなでも正解)。",
        )
        c2.selectbox(
            "出題範囲", list(SCOPE_LABELS), format_func=SCOPE_LABELS.get, key="qz_scope",
            on_change=save_setting, args=("qz_scope",),
            help="苦手・学習中・未学習は、フラッシュカードの学習状況で決まります。",
        )
        c1, c2 = st.columns(2)
        c1.multiselect(
            "カテゴリ", vocab_repo.list_categories(), key="qz_categories", placeholder="すべて",
            on_change=save_setting, args=("qz_categories",),
        )
        c2.select_slider(
            "難易度", options=[1, 2, 3, 4, 5], value=ss.qz_difficulty,
            key="qz_difficulty_widget", on_change=save_difficulty,
        )
        st.slider(
            "問題数", min_value=5, max_value=30, step=1, key="qz_count",
            on_change=save_setting, args=("qz_count",),
        )
        n = min(ss.qz_count, len(eligible))
        st.write(f"この条件で出題できる語彙:**{len(eligible)}** 語 → 今回は **{n}** 問")
        if not eligible:
            st.warning(
                "この条件で出題できる語彙がありません。条件を広げてください"
                "(例文の中に語彙が含まれている語彙だけが出題されます)。"
            )
        excluded = repo.excluded_examples()
        if excluded:
            with st.expander(f"⚠️ 出題しない例文({len(excluded)} 件)"):
                for row in excluded:
                    c1, c2 = st.columns([5, 1], vertical_alignment="center")
                    c1.markdown(f"**{escape(row['word'])}**:{escape(row['sentence'])}")
                    if c2.button("元に戻す", key=f"restore_{row['id']}"):
                        repo.restore_example(row["id"])
                        st.rerun()
        if st.button("▶ クイズをはじめる", type="primary", disabled=not eligible):
            start(repo.build_questions(ss.qz_count, ss.qz_scope, ss.qz_categories,
                                       ss.qz_difficulty))
            st.rerun()


# ============ 出題画面 ============
def show_choices_result(q: Question, chosen: str) -> None:
    """4択の答え合わせ:選択肢それぞれの意味を並べ、使い分けを確認できるようにする。"""
    vocabs = vocab_repo.get_many(q.choices)
    rows = []
    for vid in q.choices:
        v = vocabs.get(vid)
        if v is None:
            continue
        mark = "✅" if vid == q.vocab_id else "❌" if v.word == chosen else "・"
        rows.append(
            f'<div class="vg-choice-row"><span class="vg-choice-mark">{mark}</span>'
            f'<span class="vg-list-word">{ruby_html(v.word, v.reading)}</span>'
            f'<span class="vg-list-text">{escape(v.meaning)}</span></div>'
        )
    html(st, '<div class="vg-card">' + "".join(rows) + "</div>")


def show_question() -> None:
    questions, pos = ss.qz_questions, ss.qz_pos
    q = questions[pos]
    st.progress(pos / len(questions), text=f"{pos + 1} / {len(questions)} 問目")
    html(
        st,
        '<div class="vg-card vg-quiz">'
        '<p class="vg-label">( )に入る語彙は?</p>'
        f'<p class="vg-quiz-text">{sentence_html(q, filled=ss.qz_answer is not None)}</p>'
        "</div>",
    )

    if ss.qz_answer is None:
        if ss.qz_format == FORMAT_CHOICE:
            vocabs = vocab_repo.get_many(q.choices)
            words = [vocabs[i].word for i in q.choices if i in vocabs]
            cols = st.columns(2)
            for i, word in enumerate(words):
                if cols[i % 2].button(word, key=f"choice_{pos}_{i}", width="stretch"):
                    answer(q, word, word == q.word)
                    st.rerun()
        else:
            with st.form(f"input_{pos}", border=False):
                given = st.text_input("答え", placeholder="語彙を入力(読みのひらがなでもOK)")
                c1, c2, _ = st.columns([1, 1, 2])
                submitted = c1.form_submit_button("回答する", type="primary", width="stretch")
                gave_up = c2.form_submit_button("わからない", width="stretch")
            if submitted and given.strip():
                answer(q, given.strip(), is_correct_input(given, q))
                st.rerun()
            if gave_up:
                answer(q, "(わからない)", False)
                st.rerun()
    else:
        result = ss.qz_answer
        vocab = vocab_repo.get(q.vocab_id)
        if result["correct"]:
            st.success(f"✅ 正解!「{q.word}」")
        else:
            st.error(f"❌ 不正解。正解は「{q.word}」(あなたの答え:{result['given']})")
        if ss.qz_format == FORMAT_CHOICE:
            show_choices_result(q, result["given"])
        elif vocab:
            html(st, f'<div class="vg-card"><div class="vg-list-word">{ruby_html(vocab.word, vocab.reading)}</div>'
                     f'<div class="vg-list-text">{escape(vocab.meaning)}</div></div>')
        if not result.get("excluded"):
            if st.button("⚠️ この問題はおかしい", type="tertiary",
                         help="はずれの選択肢でも文が成り立つなど、問題として不適切な場合に押します。"
                         "この例文は今後出題されず、この問題の回答も記録から外します。"):
                repo.exclude_example(q.vocab_id, q.blank.sentence, result["log_id"])
                result["excluded"] = True
                ss.qz_results.pop()  # 結果画面の集計からも外す
                st.rerun()
        else:
            st.caption("⚠️ この例文は今後出題しません(回答の記録も取り消しました)。")
        last = pos == len(questions) - 1
        if st.button("結果を見る" if last else "次の問題へ →", type="primary", width="stretch"):
            ss.qz_pos += 1
            ss.qz_answer = None
            st.rerun()

    st.write("")
    if st.button("中断して結果を見る", help="ここまでの回答は記録されています。"):
        ss.qz_questions = questions[: pos + (1 if ss.qz_answer else 0)]
        ss.qz_pos = len(ss.qz_questions)
        ss.qz_answer = None
        st.rerun()


# ============ 結果画面 ============
def show_summary() -> None:
    results = ss.qz_results
    if not results:
        st.info("回答した問題はありませんでした。")
    else:
        correct = sum(r["correct"] for r in results)
        st.subheader("🎉 おつかれさまでした!")
        c1, c2 = st.columns(2)
        with c1.container(border=True):
            st.metric("正解数", f"{correct} / {len(results)} 問")
        with c2.container(border=True):
            st.metric("正答率", f"{correct / len(results):.0%}")

        missed = [r for r in results if not r["correct"]]
        if missed:
            st.markdown("**間違えた語彙**")
            vocabs = vocab_repo.get_many([r["vocab_id"] for r in missed])
            for r in missed:
                v = vocabs.get(r["vocab_id"])
                if v:
                    html(st, f'<div class="vg-choice-row"><span class="vg-list-word">'
                             f'{ruby_html(v.word, v.reading)}</span>'
                             f'<span class="vg-list-text">{escape(v.meaning)}</span>'
                             f'<span class="vg-list-ex">あなたの答え:{escape(r["given"])}</span></div>')
        else:
            st.success("全問正解です!")

    c1, c2, c3 = st.columns(3)
    missed_ids = list(dict.fromkeys(r["vocab_id"] for r in results if not r["correct"]))
    if c1.button("間違えた語彙だけもう一度", type="primary", width="stretch", disabled=not missed_ids):
        start(repo.build_questions(len(missed_ids), only_ids=missed_ids))
        st.rerun()
    if c2.button("同じ条件でもう一度", width="stretch"):
        start(repo.build_questions(ss.qz_count, ss.qz_scope, ss.qz_categories, ss.qz_difficulty))
        st.rerun()
    if c3.button("設定に戻る", width="stretch"):
        ss.qz_questions = None
        st.rerun()


# ============ 画面の切り替え ============
_, center, _ = st.columns([1, 4, 1])
with center:
    st.title("穴埋めクイズ")
    if vocab_repo.count() == 0:
        st.info("出題できる語彙がありません。先に語彙を登録してください。")
        st.page_link("views/csv_io.py", label="CSVから読み込む", icon=":material/upload:")
    elif ss.qz_questions is None:
        st.caption("例文の空欄に入る語彙を答えます。文脈の中で正しく使い分けられるかを確かめましょう。")
        show_settings()
    elif ss.qz_pos >= len(ss.qz_questions):
        show_summary()
    else:
        show_question()
