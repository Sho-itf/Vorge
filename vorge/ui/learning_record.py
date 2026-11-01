"""語彙 1 件の「学習の記録」:フラッシュカード・穴埋めクイズ・作文/議論での使用をまとめて表示する。"""

from html import escape

import streamlit as st

from vorge.flashcard import scheduler
from vorge.flashcard.repository import ReviewRepository
from vorge.quiz.repository import FORMAT_LABELS, QuizRepository
from vorge.ui.components import highlight_html, html
from vorge.vocab.models import Vocab
from vorge.writing.checker import sentences_with
from vorge.writing.repository import WritingRepository

SHOW_LIMIT = 10


def show_learning_record(vocab: Vocab) -> None:
    flash_logs = ReviewRepository().history(vocab.id)
    quiz_logs = QuizRepository().logs_for(vocab.id, SHOW_LIMIT)
    writings = [
        w for w in WritingRepository().list_writings(vocab_id=vocab.id)
        if any(x.vocab_id == vocab.id and x.used for x in w.words)
    ]
    if not (flash_logs or quiz_logs or writings):
        st.caption("まだ記録はありません。フラッシュカード・クイズ・作文で使うと、ここに記録が残ります。")
        return

    st.markdown(f"**🃏 フラッシュカード**({len(flash_logs)} 回)")
    if flash_logs:
        lines = [
            f"- {r['studied_at'][:16]} ・ {scheduler.MODE_LABELS.get(r['mode'], r['mode'])} ・ "
            f"{scheduler.RESULT_LABELS.get(r['result'], r['result'])} → 次回 {r['next_review']}"
            for r in flash_logs[:SHOW_LIMIT]
        ]
        st.markdown("\n".join(lines))
    else:
        st.caption("まだ学習していません。")

    st.markdown("**🧩 穴埋めクイズ**")
    if quiz_logs:
        lines = [
            f"- {r['answered_at'][:16]} ・ {FORMAT_LABELS.get(r['format'], r['format'])} ・ "
            f"{'✅ 正解' if r['correct'] else '❌ 不正解(答え:' + r['answer'] + ')'}"
            for r in quiz_logs
        ]
        st.markdown("\n".join(lines))
    else:
        st.caption("まだ出題されていません。")

    st.markdown(f"**✍️ 作文・議論で使った文**({len(writings)} 本)")
    if writings:
        for w in writings[:SHOW_LIMIT]:
            sentences = sentences_with(w.body, vocab.word, vocab.reading) or [w.body[:80]]
            quoted = "".join(
                f'<div class="vg-list-ex">「{highlight_html(s, vocab.word)}」</div>' for s in sentences
            )
            html(st, f'<div class="vg-record-item"><span class="vg-muted">{w.created_at[:10]} ・ '
                     f'{escape(w.prompt_text)}</span>{quoted}</div>')
    else:
        st.caption("まだ作文・議論で使っていません。")
