"""読解トレーニング画面:文章を読んで、知っている語彙を確かめ、新しい語を拾い、要約する。

タブ:
  📖 読む          … 文章を貼り付ける → 登録済みの語彙に印 → 気になる語を登録候補に → 要約
  📝 登録候補       … 拾った語・メモした語を、意味を調べて語彙ライブラリに登録する
  📚 これまでの読解 … 読んだ文章と要約の一覧
"""

from html import escape

import streamlit as st

from vorge.reading.analyzer import build_summary_prompt, candidates, find_known, highlight_known
from vorge.reading.repository import STATUS_REGISTERED, ReadingRepository
from vorge.ui.components import dictionary_links_html, highlight_html, html, set_flash, vocab_form, vocab_link_html
from vorge.vocab.models import Vocab
from vorge.vocab.repository import VocabRepository
from vorge.writing.checker import count_chars

repo = ReadingRepository()
vocab_repo = VocabRepository()
ss = st.session_state
ss.setdefault("rd_note_id", None)  # 「読む」タブで開いている文章
SUMMARY_TARGETS = [50, 100, 200]


def note_source(note) -> str:
    return " ・ ".join(x for x in (note.title, note.source) if x)


# ============ 📖 読む ============
def show_new_note_form() -> None:
    st.write("新聞・本・記事など、読んだ文章を貼り付けてください。"
             "登録済みの語彙に印が付き、まだ登録していない語の候補が出ます。")
    with st.form("rd_new"):
        c1, c2 = st.columns(2)
        title = c1.text_input("タイトル", placeholder="例:〇〇新聞 社説")
        source = c2.text_input("出典(任意)", placeholder="URL や本の名前など")
        body = st.text_area("文章", height=260, placeholder="ここに文章を貼り付けます")
        if st.form_submit_button("保存して読む", type="primary"):
            if body.strip():
                ss.rd_note_id = repo.add_note(title, source, body)
                st.rerun()
            st.error("文章を入力してください。")


def show_reading(note) -> None:
    all_vocab = vocab_repo.list_all()
    known = find_known(note.body, all_vocab)
    c1, c2 = st.columns([4, 1], vertical_alignment="center")
    c1.markdown(f"### {escape(note.title)}")
    if c2.button("別の文章を読む", width="stretch"):
        ss.rd_note_id = None
        st.rerun()
    if note.source:
        st.caption(f"出典:{note.source}")

    html(st, f'<div class="vg-essay vg-reading-body">{highlight_known(note.body, [v for v, _ in known])}</div>')
    st.caption("黄色の印は登録済みの語彙です(マウスを乗せると意味が出ます)。")
    if known:
        links = "".join(vocab_link_html(v.word, v.id) for v, _ in known)
        html(st, f'<p class="vg-label">この文章に出てきた登録済みの語彙({len(known)} 語)</p>{links}')

    # ---- 気になる語を登録候補に ----
    st.markdown("#### 気になる語を登録候補に")
    pending = {c.word for c in repo.list_candidates()}
    found = candidates(note.body, {v.word for v in all_vocab} | pending)
    sentence_of = {c.word: c.sentence for c in found}
    with st.form(f"rd_pick_{note.id}"):
        picked = st.multiselect(
            "候補(長い語から順)", [c.word for c in found], placeholder="覚えたい語を選ぶ",
            format_func=lambda w: w,
        )
        extra = st.text_input("候補に無い語(カンマ区切りで追加)", placeholder="例:忖度, 杞憂")
        st.caption("選んだ語は「📝 登録候補」タブに入ります。そこで意味を調べて語彙ライブラリに登録できます。")
        if st.form_submit_button("登録候補に追加"):
            words = picked + [w.strip() for w in extra.replace("、", ",").split(",") if w.strip()]
            items = [(w, sentence_of.get(w) or next((s for s in note.body.split("。") if w in s), "")) for w in words]
            added = repo.add_candidates(note.id, items, source=note_source(note))
            set_flash(f"{added} 語を登録候補に追加しました")
            st.rerun()

    # ---- 要約 ----
    st.markdown("#### 要約する")
    target = st.segmented_control("目安の文字数", SUMMARY_TARGETS, default=100, format_func=lambda n: f"{n}字",
                                  key=f"rd_target_{note.id}") or 100
    with st.form(f"rd_summary_{note.id}"):
        summary = st.text_area("要約", value=note.summary, height=120,
                               placeholder="筆者がいちばん伝えたいことを、自分の言葉でまとめます")
        feedback = st.text_area("添削結果のメモ(任意)", value=note.feedback, height=90)
        if st.form_submit_button("要約を保存", type="primary"):
            repo.update_summary(note.id, summary, feedback)
            set_flash("要約を保存しました")
            st.rerun()
    if note.summary:
        st.caption(f"保存した要約:{count_chars(note.summary)} 字(目安 {target} 字)")
        with st.expander("要約の添削依頼文(AI チャットに貼り付けて使います)"):
            st.code(build_summary_prompt(note.title, note.body, note.summary, target), language=None,
                    wrap_lines=True)


def show_read_tab() -> None:
    note = repo.get_note(ss.rd_note_id) if ss.rd_note_id else None
    if note is None:
        show_new_note_form()
    else:
        show_reading(note)


# ============ 📝 登録候補 ============
def show_candidates_tab() -> None:
    with st.expander("✏️ 出会った言葉をメモする(文章なしで、言葉だけ)"):
        with st.form("rd_memo", clear_on_submit=True):
            c1, c2 = st.columns([1, 2])
            word = c1.text_input("言葉 *")
            source = c2.text_input("出典(任意)", placeholder="本の名前、会話の場面など")
            sentence = st.text_input("その言葉が使われていた文(任意)")
            if st.form_submit_button("メモする"):
                if word.strip():
                    repo.add_candidates(None, [(word, sentence)], source=source)
                    set_flash(f"「{word.strip()}」をメモしました")
                    st.rerun()
                st.error("言葉を入力してください。")

    pending = repo.list_candidates()
    registered = len(repo.list_candidates(STATUS_REGISTERED))
    st.caption(f"登録候補 {len(pending)} 語 ・ これまでに登録した語 {registered} 語")
    if not pending:
        st.info("登録候補はありません。「📖 読む」で文章から拾うか、上のメモから追加できます。")
        return

    categories = vocab_repo.list_categories()
    for c in pending:
        with st.expander(f"{c.word}" + (f" ・ {c.source}" if c.source else "")):
            if c.sentence:
                html(st, f'<div class="vg-list-ex">「{highlight_html(c.sentence, c.word)}」</div>')
            html(st, f'<p class="vg-dicts">{dictionary_links_html(c.word)}</p>')
            st.caption("辞書で意味を調べて、語彙ライブラリに登録しましょう(使われていた文は例文 1 に入っています)。")
            initial = Vocab(word=c.word, meaning="", example_1=c.sentence, source=c.source)
            new_vocab = vocab_form(f"rd_cand_{c.id}", categories, initial, submit_label="語彙ライブラリに登録")
            if new_vocab:
                vocab_id = vocab_repo.add(new_vocab)
                repo.mark_registered(c.id, vocab_id)
                set_flash(f"「{new_vocab.word}」を語彙ライブラリに登録しました")
                st.rerun()
            if st.button("登録しない", key=f"rd_ignore_{c.id}"):
                repo.ignore(c.id)
                st.rerun()


# ============ 📚 これまでの読解 ============
def show_history_tab() -> None:
    notes = repo.list_notes()
    if not notes:
        st.info("まだ読んだ文章はありません。")
        return
    all_vocab = vocab_repo.list_all()
    for note in notes:
        title = f"{note.created_at[:10]} ・ {note.title}" + (" ・ 要約あり" if note.summary else "")
        with st.expander(title):
            if note.source:
                st.caption(f"出典:{note.source}")
            known = [v for v, _ in find_known(note.body, all_vocab)]
            html(st, f'<div class="vg-essay vg-reading-body">{highlight_known(note.body, known)}</div>')
            if note.summary:
                html(st, f'<p class="vg-label">要約</p><div class="vg-essay">{escape(note.summary)}</div>')
            if note.feedback:
                html(st, f'<p class="vg-label">添削結果のメモ</p><div class="vg-essay">{escape(note.feedback)}</div>')
            c1, c2, _ = st.columns([1.2, 1, 3])
            if c1.button("この文章を開く", key=f"rd_open_{note.id}"):
                ss.rd_note_id = note.id
                set_flash("「📖 読む」タブで開きました")
                st.rerun()
            with c2.popover("🗑️ 削除"):
                st.write("この文章と要約を削除します(登録済みの語彙は残ります)。取り消せません。")
                if st.button("削除する", key=f"rd_del_{note.id}", type="primary"):
                    repo.delete_note(note.id)
                    if ss.rd_note_id == note.id:
                        ss.rd_note_id = None
                    st.rerun()


# ============ 画面 ============
st.title("読解トレーニング")
st.caption("読んだ文章から、知っている語彙を確かめ、新しい語を拾い、要約で理解を深めましょう。")
tab_read, tab_candidates, tab_history = st.tabs(["📖 読む", "📝 登録候補", "📚 これまでの読解"])
with tab_read:
    show_read_tab()
with tab_candidates:
    show_candidates_tab()
with tab_history:
    show_history_tab()
