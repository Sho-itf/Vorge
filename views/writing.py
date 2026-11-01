"""作文トレーニング画面:お題と語彙を決めて書く → 自動チェック → 保存・添削依頼。

タブ:
  ✍️ 書く          … お題・語彙を決めて作文し、保存する
  📚 これまでの作文 … 保存した作文の一覧(添削メモの記入・削除)
  🗂 お題の管理     … お題の追加・編集・出題のオン/オフ・削除
"""

import random
from html import escape

import streamlit as st

from vorge.debate import checker as debate_checker
from vorge.debate.templates import KIND_DEBATE, STANCE_LABELS, TEMPLATES
from vorge.settings import get_setting, set_setting
from vorge.ui.components import set_flash, vocab_mini_cards
from vorge.vocab.repository import VocabRepository
from vorge.writing import checker
from vorge.writing import prompts as P
from vorge.writing.repository import Prompt, WritingRepository, WritingWord

repo = WritingRepository()
vocab_repo = VocabRepository()
ss = st.session_state

# ---------- 出題条件(前回の選択を DB から読み込み、変更したら保存する) ----------
SETTING_KEYS = {
    "wr_kind": P.AUTO,
    "wr_length": "standard",
    "wr_vocab_mode": P.AUTO,
    "wr_vocab_count": 2,
}
for key, default in SETTING_KEYS.items():
    if key not in ss:
        ss[key] = get_setting(key, default)
    # segmented_control は同じボタンをもう一度押すと選択が外れて None になるので、初期値に戻す
    if ss[key] is None:
        ss[key] = default


def save_setting(key: str) -> None:
    if ss[key] is not None:
        set_setting(key, ss[key])


# ---------- 書いている途中の状態 ----------
ss.setdefault("wr_task", None)  # {"prompt_id", "length", "min", "max", "vocab_ids"}
ss.setdefault("wr_draft", "")  # 書きかけの本文(画面を移動しても残す)
ss.setdefault("wr_version", 0)  # 入力欄を作り直すための番号
ss.setdefault("wr_saved_id", None)  # 保存済みの作文ID(保存後の画面を出すため)
ss.setdefault("wr_history_limit", 20)


def resolve_length(key: str) -> tuple[str, int, int]:
    """文字数の選択肢から (キー, 最小, 最大) を決める。おまかせならランダム。"""
    if key == P.AUTO:
        key = random.choice(list(P.LENGTH_OPTIONS))
    _, lo, hi = P.LENGTH_OPTIONS[key]
    return key, lo, hi


def new_task() -> None:
    """設定に従って、お題・文字数・語彙を決め直す。"""
    prompt = repo.random_prompt(ss.wr_kind)
    if prompt is None:
        ss.wr_task = None
        set_flash("出題できるお題がありません。「お題の管理」で追加するか、出題をオンにしてください。", "warning")
        return
    length, lo, hi = resolve_length(ss.wr_length)
    vocab_ids = (
        []
        if ss.wr_vocab_mode == P.VOCAB_MANUAL
        else repo.pick_vocab(ss.wr_vocab_mode, ss.wr_vocab_count)
    )
    ss.wr_task = {"prompt_id": prompt.id, "length": length, "min": lo, "max": hi,
                  "vocab_ids": vocab_ids}
    ss.wr_draft = ""
    ss.wr_version += 1
    ss.wr_saved_id = None


def change_prompt() -> None:
    prompt = repo.random_prompt(ss.wr_kind, exclude_id=ss.wr_task["prompt_id"])
    if prompt:
        ss.wr_task["prompt_id"] = prompt.id


def change_vocab() -> None:
    current = set(ss.wr_task["vocab_ids"])
    ss.wr_task["vocab_ids"] = repo.pick_vocab(ss.wr_vocab_mode, ss.wr_vocab_count, current)


def keep_draft() -> None:
    ss.wr_draft = ss[f"wr_body_{ss.wr_version}"]


def html(container, body: str) -> None:
    container.markdown(body, unsafe_allow_html=True)


# ============ ✍️ 書く ============
def show_settings() -> None:
    with st.container(border=True):
        c1, c2 = st.columns([3, 2])
        c1.segmented_control(
            "お題の種類",
            [P.AUTO, *P.KIND_LABELS],
            format_func=lambda k: "おまかせ" if k == P.AUTO else P.KIND_LABELS[k],
            key="wr_kind",
            on_change=save_setting,
            args=("wr_kind",),
        )
        c2.segmented_control(
            "文字数",
            [P.AUTO, *P.LENGTH_OPTIONS],
            format_func=lambda k: "おまかせ" if k == P.AUTO else P.LENGTH_OPTIONS[k][0],
            key="wr_length",
            on_change=save_setting,
            args=("wr_length",),
            help="短め:100〜200字 / 標準:200〜400字 / 長め:400〜800字",
        )
        c1, c2, c3 = st.columns([2, 1, 2], vertical_alignment="bottom")
        c1.selectbox(
            "語彙の選び方",
            list(P.VOCAB_MODE_LABELS),
            format_func=P.VOCAB_MODE_LABELS.get,
            key="wr_vocab_mode",
            on_change=save_setting,
            args=("wr_vocab_mode",),
            help="おまかせ:苦手・学習中・未学習の語彙から 1 つずつ順番に選びます。"
            "候補が足りないときは登録済みの全語彙から選びます。",
        )
        c2.segmented_control(
            "語彙の数", [1, 2, 3], key="wr_vocab_count", on_change=save_setting,
            args=("wr_vocab_count",),
        )
        label = "📝 新しいお題で書く" if ss.wr_task else "📝 お題を決めて書きはじめる"
        if c3.button(label, type="primary", width="stretch"):
            new_task()
            st.rerun()
        if ss.wr_task and ss.wr_draft and not ss.wr_saved_id:
            st.caption("※ 新しいお題にすると、保存していない書きかけの文章は消えます。")


def show_task_header(prompt: Prompt, task: dict) -> None:
    kind = P.KIND_LABELS.get(prompt.kind, prompt.kind)
    length_label = P.LENGTH_OPTIONS[task["length"]][0]
    html(
        st,
        '<div class="vg-card vg-prompt">'
        f'<span class="vg-badge">{escape(kind)}</span>'
        f'<span class="vg-badge vg-badge-sub">{length_label}:{task["min"]}〜{task["max"]}字</span>'
        f'<p class="vg-prompt-text">{escape(prompt.text)}</p>'
        "</div>",
    )
    if not ss.wr_saved_id:
        c1, c2, _ = st.columns([1, 1, 3])
        if c1.button("🔄 別のお題", width="stretch"):
            change_prompt()
            st.rerun()
        if ss.wr_vocab_mode != P.VOCAB_MANUAL and c2.button("🔄 別の語彙", width="stretch"):
            change_vocab()
            st.rerun()


def show_manual_picker(task: dict) -> None:
    all_vocab = vocab_repo.list_all()
    labels = {v.id: f"{v.word}({v.reading})" if v.reading else v.word for v in all_vocab}
    selected = st.multiselect(
        f"使う語彙を選ぶ(最大 {ss.wr_vocab_count} 語)",
        list(labels),
        default=[i for i in task["vocab_ids"] if i in labels],
        format_func=labels.get,
        max_selections=ss.wr_vocab_count,
        placeholder="語彙や読みを入力して検索",
        disabled=bool(ss.wr_saved_id),
    )
    task["vocab_ids"] = selected


def show_check(result: checker.CheckResult, task: dict, n_vocab: int) -> None:
    used = sum(result.vocab_used.values())
    status = {"short": "あと少し", "ok": "目安どおり", "long": "長め"}[result.length_status]
    c1, c2 = st.columns(2)
    c1.metric("文字数", f"{result.char_count} 字", f"目安 {task['min']}〜{task['max']}字:{status}",
              delta_color="normal" if result.length_status == "ok" else "off")
    c2.metric("指定語彙", f"{used} / {n_vocab} 語", "すべて使えました" if n_vocab and used == n_vocab
              else None)

    notes = []
    for term, n in result.repeated:
        notes.append(f"🔁 「{term}」が {n} 回使われています。言い換えられないか考えてみましょう。")
    if result.monotone:
        ending, run = result.monotone
        notes.append(f"📄 文末が「〜{ending}」で {run} 回続いています。文末に変化をつけると読みやすくなります。")
    if result.style_mix:
        polite, plain = result.style_mix
        notes.append(
            f"⚖️ です・ます調({polite}文)と、だ・である調({plain}文)が混ざっています。"
        )
    if notes:
        st.markdown("\n".join(f"- {n}" for n in notes))
    elif result.char_count:
        st.caption("✨ 自動チェックで気になる点はありません。")
    st.caption("※ 自動チェックは簡単なルールによる目安です。")


def show_after_save(prompt: Prompt, task: dict, vocabs: list, body: str) -> None:
    st.success("保存しました。添削してもらう場合は、下の依頼文をコピーして AI チャットに貼り付けてください。")
    review = checker.build_review_prompt(
        prompt.text, [(v.word, v.meaning) for v in vocabs], body, task["min"], task["max"]
    )
    st.caption("右上のアイコンでコピーできます")
    st.code(review, language=None, wrap_lines=True)
    st.link_button("claude.ai を開く ↗", "https://claude.ai/new")

    with st.form(f"feedback_{ss.wr_saved_id}"):
        feedback = st.text_area(
            "添削結果のメモ(任意)", height=160,
            placeholder="添削してもらった内容や、気づいたことを貼り付けて保存できます",
        )
        if st.form_submit_button("メモを保存"):
            repo.update_feedback(ss.wr_saved_id, feedback)
            set_flash("メモを保存しました")
            st.rerun()

    if st.button("✍️ 次のお題へ", type="primary"):
        new_task()
        st.rerun()


def show_write_tab() -> None:
    if vocab_repo.count() == 0:
        st.info("作文で使う語彙がありません。先に語彙を登録してください。")
        st.page_link("views/csv_io.py", label="CSVから読み込む", icon=":material/upload:")
        return

    show_settings()
    task = ss.wr_task
    if task is None:
        st.info("条件を選んで「お題を決めて書きはじめる」を押してください。")
        return

    prompt = next((p for p in repo.list_prompts() if p.id == task["prompt_id"]), None)
    if prompt is None:  # お題が削除された場合
        ss.wr_task = None
        st.rerun()

    show_task_header(prompt, task)
    if ss.wr_vocab_mode == P.VOCAB_MANUAL and not ss.wr_saved_id:
        show_manual_picker(task)
    vocab_map = vocab_repo.get_many(task["vocab_ids"])
    vocabs = [vocab_map[i] for i in task["vocab_ids"] if i in vocab_map]

    body = ss.wr_draft
    result = checker.check(body, [(v.word, v.reading) for v in vocabs], task["min"], task["max"])
    vocab_mini_cards(vocabs, result.vocab_used)

    if ss.wr_saved_id:
        html(st, f'<div class="vg-essay">{escape(body)}</div>')
        show_after_save(prompt, task, vocabs, body)
        return

    st.text_area(
        "本文",
        value=ss.wr_draft,
        key=f"wr_body_{ss.wr_version}",
        on_change=keep_draft,
        height=320,
        placeholder="ここに書きます。指定の語彙を使ってみましょう。",
    )
    st.caption("入力欄の外をクリックするか Ctrl+Enter を押すと、文字数とチェックが更新されます。")
    show_check(result, task, len(vocabs))

    if st.button("💾 保存する", type="primary", disabled=not body.strip() or not vocabs):
        ss.wr_saved_id = repo.save_writing(
            prompt, task["min"], task["max"], body, result.char_count,
            [WritingWord(v.id, v.word, result.vocab_used.get(v.word, False)) for v in vocabs],
        )
        st.rerun()


# ============ 📚 これまでの作文 ============
# 一覧の「種類」:作文のお題の種類 + 議論トレーニングで保存したもの
HISTORY_KIND_LABELS = {**P.KIND_LABELS, KIND_DEBATE: "議論"}


def show_writing_body(w) -> None:
    """保存した作文・議論の本文。議論は欄ごとに見出しを付けて表示する。"""
    if w.kind == KIND_DEBATE and w.template in TEMPLATES:
        template = TEMPLATES[w.template]
        html(st, f'<span class="vg-badge">議論 ・ {escape(template.label)}</span>'
                 f'<span class="vg-badge vg-badge-sub">{STANCE_LABELS.get(w.stance, w.stance)}</span>')
        texts = w.section_texts
        for s in template.sections:
            html(st, f'<p class="vg-label">{escape(s.label)}</p>'
                     f'<div class="vg-essay">{escape(texts.get(s.key, ""))}</div>')
        return
    html(st, f'<span class="vg-badge">{escape(HISTORY_KIND_LABELS.get(w.kind, w.kind))}</span>'
             f'<span class="vg-badge vg-badge-sub">目安 {w.min_chars}〜{w.max_chars}字</span>')
    html(st, f'<div class="vg-essay">{escape(w.body)}</div>')


def show_history_tab() -> None:
    if repo.count_writings() == 0:
        st.info("まだ保存した作文はありません。「✍️ 書く」タブから書いてみましょう。")
        return

    c1, c2, c3 = st.columns([2, 2, 1])
    words = repo.written_vocab()
    vocab_filter = c1.selectbox(
        "語彙で絞り込む", [None, *[i for i, _ in words]],
        format_func=lambda i: "すべて" if i is None else dict(words)[i],
    )
    kind_filter = c2.selectbox(
        "種類", [None, *HISTORY_KIND_LABELS],
        format_func=lambda k: "すべて" if k is None else HISTORY_KIND_LABELS[k],
    )
    writings = repo.list_writings(vocab_filter, kind_filter)
    c3.metric("件数", f"{len(writings)} 件")

    for w in writings[: ss.wr_history_limit]:
        marks = " ".join(f"{'✅' if x.used else '⬜'}{x.word}" for x in w.words)
        title = f"{w.created_at[:10]} ・ {w.prompt_text} ・ {w.char_count}字 ・ {marks}"
        with st.expander(title):
            show_writing_body(w)

            with st.form(f"fb_{w.id}"):
                feedback = st.text_area("添削結果のメモ", value=w.feedback, height=120)
                if st.form_submit_button("メモを保存"):
                    repo.update_feedback(w.id, feedback)
                    set_flash("メモを保存しました")
                    st.rerun()

            c1, c2, _ = st.columns([1.3, 1, 2])
            if c1.toggle("添削依頼文を表示", key=f"show_review_{w.id}"):
                vocab_map = vocab_repo.get_many([x.vocab_id for x in w.words])
                pairs = [(x.word, vocab_map[x.vocab_id].meaning if x.vocab_id in vocab_map else "")
                         for x in w.words]
                if w.kind == KIND_DEBATE:
                    review = debate_checker.build_review_prompt(
                        w.prompt_text, w.stance, TEMPLATES[w.template], pairs, w.section_texts)
                else:
                    review = checker.build_review_prompt(w.prompt_text, pairs, w.body,
                                                         w.min_chars, w.max_chars)
                st.code(review, language=None, wrap_lines=True)
            with c2.popover("🗑️ 削除"):
                st.write("この作文を削除します。取り消せません。")
                if st.button("削除する", key=f"del_{w.id}", type="primary"):
                    repo.delete_writing(w.id)
                    set_flash("作文を削除しました")
                    st.rerun()

    if len(writings) > ss.wr_history_limit:
        if st.button(f"さらに表示(残り {len(writings) - ss.wr_history_limit} 件)"):
            ss.wr_history_limit += 20
            st.rerun()


# ============ 🗂 お題の管理 ============
def toggle_prompt(p: Prompt) -> None:
    repo.update_prompt(p.id, p.kind, p.text, ss[f"active_{p.id}"])


def show_prompts_tab() -> None:
    with st.form("add_prompt", clear_on_submit=True, border=True):
        st.markdown("**お題を追加**")
        c1, c2, c3 = st.columns([1, 3, 1], vertical_alignment="bottom")
        kind = c1.selectbox("種類", list(P.KIND_LABELS), format_func=P.KIND_LABELS.get)
        text = c2.text_input("お題", placeholder="例:最近見た映画について")
        if c3.form_submit_button("追加", type="primary", width="stretch"):
            if text.strip():
                repo.add_prompt(kind, text)
                set_flash("お題を追加しました")
                st.rerun()
            else:
                st.error("お題を入力してください。")

    kind_filter = st.segmented_control(
        "表示する種類", ["all", *P.KIND_LABELS],
        format_func=lambda k: "すべて" if k == "all" else P.KIND_LABELS[k],
        default="all",
    )
    prompts = repo.list_prompts(None if kind_filter in (None, "all") else kind_filter)
    active = sum(p.active for p in prompts)
    st.caption(f"{len(prompts)} 件(出題中 {active} 件)・ スイッチをオフにすると出題されなくなります")

    with st.container(key="vlist"):
        for p in prompts:
            with st.container(key=f"vrow-prompt-{p.id}"):
                c1, c2, c3, c4 = st.columns([0.6, 5, 1.4, 0.9], vertical_alignment="center")
                c1.toggle("出題", value=p.active, key=f"active_{p.id}", on_change=toggle_prompt,
                          args=(p,), label_visibility="collapsed")
                muted = "" if p.active else " vg-muted"
                html(c2, f'<div class="vg-list-text{muted}">{escape(p.text)}</div>')
                html(c3, f'<span class="vg-badge">{escape(P.KIND_LABELS.get(p.kind, p.kind))}</span>')
                with c4.popover("編集"):
                    new_kind = st.selectbox(
                        "種類", list(P.KIND_LABELS), index=list(P.KIND_LABELS).index(p.kind),
                        format_func=P.KIND_LABELS.get, key=f"kind_{p.id}",
                    )
                    new_text = st.text_area("お題", value=p.text, key=f"text_{p.id}")
                    b1, b2 = st.columns(2)
                    if b1.button("保存", key=f"save_{p.id}", type="primary", width="stretch"):
                        if new_text.strip():
                            repo.update_prompt(p.id, new_kind, new_text, p.active)
                            set_flash("お題を更新しました")
                            st.rerun()
                        else:
                            st.error("お題を入力してください。")
                    if b2.button("削除", key=f"delp_{p.id}", width="stretch"):
                        repo.delete_prompt(p.id)
                        set_flash("お題を削除しました(このお題で書いた作文は残ります)")
                        st.rerun()


# ============ 画面 ============
st.title("作文トレーニング")
st.caption("覚えた語彙を、実際に文章の中で使ってみましょう。")
tab_write, tab_history, tab_prompts = st.tabs(["✍️ 書く", "📚 これまでの作文・議論", "🗂 お題の管理"])
with tab_write:
    show_write_tab()
with tab_history:
    show_history_tab()
with tab_prompts:
    show_prompts_tab()
