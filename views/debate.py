"""議論トレーニング画面:お題と立場を決め、型に沿って主張・根拠・反論・再反論を組み立てる。

保存した議論は、作文トレーニングの「これまでの作文」に種類「議論」として並ぶ。
"""

import random
from html import escape

import streamlit as st

from vorge.debate import checker
from vorge.debate.templates import STANCE_HELP, STANCE_LABELS, TEMPLATES, opposite
from vorge.ui.components import html, set_flash, vocab_mini_cards
from vorge.ui.persist import clear_draft, load_draft, load_settings, save_draft, save_setting
from vorge.vocab.repository import VocabRepository
from vorge.writing import prompts as P
from vorge.writing.checker import count_chars
from vorge.writing.repository import WritingRepository, WritingWord

repo = WritingRepository()
vocab_repo = VocabRepository()
ss = st.session_state

TOPIC_RANDOM = "random"
TOPIC_CUSTOM = "custom"
TOPIC_LABELS = {TOPIC_RANDOM: "お題から選ぶ", TOPIC_CUSTOM: "自分で入力する"}

# ---------- 出題条件(前回の選択を DB から読み込み、変更したら保存する) ----------
load_settings({
    "db_template": "rebuttal",
    "db_topic": TOPIC_RANDOM,
    "db_vocab_mode": P.VOCAB_LOGIC,
    "db_vocab_count": 2,
})

# ---------- 組み立て中の状態 ----------
# 書きかけ(お題・立場・語彙・各欄)は DB にも下書き保存し、ブラウザを閉じても続きから書けるようにする
if "db_task" not in ss:
    draft = load_draft("debate") or {}
    ss.db_task = draft.get("task")  # {"prompt_id", "prompt_text", "stance", "template", "vocab_ids"}
    ss.db_sections = draft.get("sections", {})  # 欄 → 書きかけの文章
ss.setdefault("db_version", 0)  # 入力欄を作り直すための番号
ss.setdefault("db_saved_id", None)


def store_draft() -> None:
    save_draft("debate", {"task": ss.db_task, "sections": ss.db_sections})


def new_task(custom_topic: str = "") -> None:
    if ss.db_topic == TOPIC_CUSTOM:
        if not custom_topic.strip():  # 「次のお題へ」で自由入力のお題がまだ無いときは設定に戻る
            ss.db_task = None
            return
        prompt_id, prompt_text = None, custom_topic.strip()
    else:
        prompt = repo.random_prompt(P.KIND_OPINION)
        if prompt is None:
            set_flash("「意見・議論」のお題がありません。作文トレーニングの「お題の管理」で追加してください。",
                      "warning")
            return
        prompt_id, prompt_text = prompt.id, prompt.text
    vocab_ids = (
        [] if ss.db_vocab_mode == P.VOCAB_MANUAL
        else repo.pick_vocab(ss.db_vocab_mode, ss.db_vocab_count)
    )
    ss.db_task = {
        "prompt_id": prompt_id,
        "prompt_text": prompt_text,
        "stance": random.choice(list(STANCE_LABELS)),
        "template": ss.db_template,
        "vocab_ids": vocab_ids,
    }
    ss.db_sections = {}
    ss.db_version += 1
    ss.db_saved_id = None
    store_draft()


def change_prompt() -> None:
    prompt = repo.random_prompt(P.KIND_OPINION, exclude_id=ss.db_task["prompt_id"])
    if prompt:
        ss.db_task.update(prompt_id=prompt.id, prompt_text=prompt.text)
        store_draft()


def change_vocab() -> None:
    current = set(ss.db_task["vocab_ids"])
    ss.db_task["vocab_ids"] = repo.pick_vocab(ss.db_vocab_mode, ss.db_vocab_count, current)
    store_draft()


def flip_stance() -> None:
    ss.db_task["stance"] = opposite(ss.db_task["stance"])
    store_draft()


def keep_section(key: str) -> None:
    ss.db_sections[key] = ss[f"db_{key}_{ss.db_version}"]
    store_draft()


# ============ 設定 ============
def show_settings() -> None:
    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.segmented_control(
            "構成の型", list(TEMPLATES), format_func=lambda k: TEMPLATES[k].label,
            key="db_template", on_change=save_setting, args=("db_template",),
        )
        c2.segmented_control(
            "お題", list(TOPIC_LABELS), format_func=TOPIC_LABELS.get,
            key="db_topic", on_change=save_setting, args=("db_topic",),
            help="「お題から選ぶ」は、作文トレーニングの「意見・議論」のお題から選びます。",
        )
        st.caption(TEMPLATES[ss.db_template].description)

        custom_topic = ""
        if ss.db_topic == TOPIC_CUSTOM:
            custom_topic = st.text_input("お題を入力", placeholder="例:大学の授業はすべてオンラインにすべきか")

        c1, c2, c3 = st.columns([2, 1, 2], vertical_alignment="bottom")
        c1.selectbox(
            "語彙の選び方", list(P.DEBATE_VOCAB_MODE_LABELS),
            format_func=P.DEBATE_VOCAB_MODE_LABELS.get, key="db_vocab_mode",
            on_change=save_setting, args=("db_vocab_mode",),
            help="「論理・議論の語彙を優先」は、カテゴリ「論理・議論」「判断・論理」から選びます。"
            "足りないときは他の語彙から補います。",
        )
        c2.segmented_control(
            "語彙の数", [1, 2, 3], key="db_vocab_count", on_change=save_setting,
            args=("db_vocab_count",),
        )
        label = "🗣 新しいお題で組み立てる" if ss.db_task else "🗣 はじめる"
        disabled = ss.db_topic == TOPIC_CUSTOM and not custom_topic.strip()
        if c3.button(label, type="primary", width="stretch", disabled=disabled):
            new_task(custom_topic)
            st.rerun()
        if ss.db_task and any(ss.db_sections.values()) and not ss.db_saved_id:
            st.caption("※ 新しいお題にすると、保存していない書きかけの文章は消えます。")


# ============ お題・立場・語彙 ============
def show_task_header(task: dict) -> None:
    template = TEMPLATES[task["template"]]
    html(
        st,
        '<div class="vg-card vg-prompt">'
        f'<span class="vg-badge">議論 ・ {escape(template.label)}</span>'
        f'<span class="vg-badge vg-badge-sub">{STANCE_LABELS[task["stance"]]}で書く</span>'
        f'<p class="vg-prompt-text">{escape(task["prompt_text"])}</p>'
        "</div>",
    )
    st.caption(STANCE_HELP)
    if ss.db_saved_id:
        return
    c1, c2, c3, _ = st.columns([1.3, 1, 1, 1.2])
    if c1.button(f"🔁 あえて{STANCE_LABELS[opposite(task['stance'])]}で書く", width="stretch",
                 help="自分と違う立場で組み立てると、相手の考えを理解する練習になります。"):
        flip_stance()
        st.rerun()
    if task["prompt_id"] is not None and c2.button("🔄 別のお題", width="stretch"):
        change_prompt()
        st.rerun()
    if ss.db_vocab_mode != P.VOCAB_MANUAL and c3.button("🔄 別の語彙", width="stretch"):
        change_vocab()
        st.rerun()


def show_manual_picker(task: dict) -> None:
    all_vocab = vocab_repo.list_all()
    labels = {v.id: f"{v.word}({v.reading})" if v.reading else v.word for v in all_vocab}
    selected = st.multiselect(
        f"使う語彙を選ぶ(最大 {ss.db_vocab_count} 語)", list(labels),
        default=[i for i in task["vocab_ids"] if i in labels], format_func=labels.get,
        max_selections=ss.db_vocab_count, placeholder="語彙や読みを入力して検索",
    )
    if selected != task["vocab_ids"]:
        task["vocab_ids"] = selected
        store_draft()


# ============ 欄ごとの入力とチェック ============
def show_sections(task: dict, result: checker.DebateCheck) -> None:
    template = TEMPLATES[task["template"]]
    for i, s in enumerate(template.sections, start=1):
        n = result.char_counts.get(s.key, 0)
        status = "" if s.min_chars <= n <= s.max_chars or n == 0 else (
            " ・ 少なめ" if n < s.min_chars else " ・ 多め")
        st.markdown(f"**{i}. {s.label}** <span class='vg-muted'>— {escape(s.hint)}</span>",
                    unsafe_allow_html=True)
        st.text_area(
            s.label, value=ss.db_sections.get(s.key, ""), key=f"db_{s.key}_{ss.db_version}",
            on_change=keep_section, args=(s.key,), placeholder=s.placeholder, height=90,
            label_visibility="collapsed",
        )
        st.caption(f"{n} 字(目安 {s.min_chars}〜{s.max_chars}字){status}")


def show_check(task: dict, result: checker.DebateCheck, n_vocab: int) -> None:
    template = TEMPLATES[task["template"]]
    st.markdown("#### 自動チェック")
    used = sum(result.vocab_used.values())
    c1, c2, c3 = st.columns(3)
    filled = len(template.sections) - len(result.empty_sections)
    c1.metric("書けた欄", f"{filled} / {len(template.sections)}")
    c2.metric("指定語彙", f"{used} / {n_vocab} 語")
    c3.metric("合計", f"{result.total_chars} 字",
              f"目安 {template.min_chars}〜{template.max_chars}字", delta_color="off")

    notes = []
    if result.empty_sections:
        notes.append(f"✏️ まだ書いていない欄:{'、'.join(result.empty_sections)}")
    for label in result.missing_evidence:
        notes.append(f"📊 「{label}」に具体例やデータが見当たりません(「例えば」「実際に」、数字など)。")
    if task["template"] == "rebuttal":
        for group in checker.REBUTTAL_CONNECTORS:
            if not result.connectors.get(group):
                example = "「確かに〜」" if group == "譲歩する" else "「しかし〜」"
                notes.append(f"🔗 反論・再反論で{example}のような「{group}」言葉を使うと、流れが明確になります。")
    if not result.connectors.get("結論を示す"):
        notes.append("🔗 結論の前に「したがって」「つまり」などを使うと、まとめであることが伝わります。")
    used_connectors = [w for words in result.connectors.values() for w in words]
    if used_connectors:
        notes.append(f"👍 使えたつなぎ言葉:{'、'.join(used_connectors)}")
    st.markdown("\n".join(f"- {n}" for n in notes) if notes else "✨ 気になる点はありません。")
    st.caption("※ 自動チェックは簡単なルールによる目安です。")


# ============ 保存後 ============
def show_after_save(task: dict, vocabs: list) -> None:
    template = TEMPLATES[task["template"]]
    st.success("保存しました。添削と「相手側からの反論」をもらう場合は、下の依頼文を AI チャットに貼り付けてください。")
    review = checker.build_review_prompt(
        task["prompt_text"], task["stance"], template,
        [(v.word, v.meaning) for v in vocabs], ss.db_sections,
    )
    st.caption("右上のアイコンでコピーできます")
    st.code(review, language=None, wrap_lines=True)
    st.link_button("claude.ai を開く ↗", "https://claude.ai/new")

    with st.form(f"db_feedback_{ss.db_saved_id}"):
        feedback = st.text_area(
            "添削結果のメモ(任意)", height=160,
            placeholder="添削や、AI から出された反論・それへの再反論などをメモできます",
        )
        if st.form_submit_button("メモを保存"):
            repo.update_feedback(ss.db_saved_id, feedback)
            set_flash("メモを保存しました")
            st.rerun()
    c1, c2, _ = st.columns([1, 1.3, 2])
    if c1.button("🗣 次のお題へ", type="primary", width="stretch"):
        new_task()
        st.rerun()
    c2.page_link("views/writing.py", label="これまでの作文・議論を見る", icon=":material/history:")


# ============ 画面 ============
st.title("議論トレーニング")
st.caption("型に沿って意見を組み立て、反論にも答えられる説得力のある議論を練習しましょう。")

if vocab_repo.count() == 0:
    st.info("議論で使う語彙がありません。先に語彙を登録してください。")
    st.page_link("views/csv_io.py", label="CSVから読み込む", icon=":material/upload:")
    st.stop()

show_settings()
task = ss.db_task
if task is None:
    st.info("条件を選んで「はじめる」を押してください。立場(肯定側・否定側)はランダムに決まり、あとから入れ替えられます。")
    st.stop()

show_task_header(task)
if ss.db_vocab_mode == P.VOCAB_MANUAL and not ss.db_saved_id:
    show_manual_picker(task)
vocab_map = vocab_repo.get_many(task["vocab_ids"])
vocabs = [vocab_map[i] for i in task["vocab_ids"] if i in vocab_map]
template = TEMPLATES[task["template"]]
result = checker.check(template, ss.db_sections, [(v.word, v.reading) for v in vocabs])
vocab_mini_cards(vocabs, result.vocab_used)

if ss.db_saved_id:
    for s in template.sections:
        html(st, f'<p class="vg-label">{escape(s.label)}</p>'
                 f'<div class="vg-essay">{escape(ss.db_sections.get(s.key, ""))}</div>')
    show_after_save(task, vocabs)
    st.stop()

st.write("")
show_sections(task, result)
st.caption("入力欄の外をクリックするか Ctrl+Enter を押すと、文字数とチェックが更新されます"
           "(書きかけは自動で下書き保存されます)。")
show_check(task, result, len(vocabs))

with st.expander("1 つの文章として読む"):
    composed = checker.compose(template, ss.db_sections)
    html(st, f'<div class="vg-essay">{escape(composed) or "(まだ何も書いていません)"}</div>')

if st.button("💾 保存する", type="primary", disabled=bool(result.empty_sections) or not vocabs,
             help="すべての欄を書くと保存できます。"):
    body = checker.compose(template, ss.db_sections)
    ss.db_saved_id = repo.save_debate(
        task["prompt_id"], task["prompt_text"], task["stance"], task["template"],
        dict(ss.db_sections), body, count_chars(body), template.min_chars, template.max_chars,
        [WritingWord(v.id, v.word, result.vocab_used.get(v.word, False)) for v in vocabs],
    )
    clear_draft("debate")
    st.rerun()
