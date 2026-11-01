"""見た目(フォント・余白・カード)を整える CSS。

色は半透明(rgba)で指定しているため、ライトモードでもダークモードでも馴染む。
"""

import streamlit as st

_CSS = """
<style>
/* 日本語が読みやすいフォント。アイコン(Material Symbols)とコードは除外する */
.stApp, .stApp *:not([data-testid="stIconMaterial"]):not(code):not(pre),
[role="dialog"] *:not([data-testid="stIconMaterial"]):not(code):not(pre) {
    font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Hiragino Sans",
                 "Yu Gothic UI", "Meiryo", sans-serif;
}
.stMarkdown p, .stMarkdown li { line-height: 1.8; }
.block-container { padding-top: 2.5rem; max-width: 1200px; }

/* 語彙カード(ポップアップは .stApp の外に描画されるので、.stApp を付けずに詳細度を上げている) */
.vg-card {
    border: 1px solid rgba(128, 128, 128, 0.25);
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 0.8rem;
}
div.vg-card p.vg-word { font-size: 2rem; font-weight: 700; line-height: 1.8; margin: 0 0 0.4rem; }
div.vg-card p.vg-word rt { font-size: 0.42em; font-weight: 400; opacity: 0.7; }
div.vg-card p.vg-reading { opacity: 0.65; font-size: 0.95rem; margin: 0.1rem 0 0.6rem; }
div.vg-card p.vg-meaning { font-size: 1.1rem; line-height: 1.8; margin: 0.4rem 0 0.8rem; }
div.vg-card p.vg-label {
    font-size: 0.78rem; font-weight: 600; opacity: 0.6;
    letter-spacing: 0.05em; margin: 0.9rem 0 0.2rem;
}
div.vg-card p.vg-text { line-height: 1.8; margin: 0; }
.vg-badge {
    display: inline-block; padding: 0.15rem 0.6rem; margin: 0 0.3rem 0.3rem 0;
    border-radius: 999px; font-size: 0.82rem; white-space: nowrap;
    background: rgba(99, 102, 241, 0.14);
}
.vg-chip {
    display: inline-block; padding: 0.1rem 0.55rem; margin: 0 0.3rem 0.3rem 0;
    border-radius: 6px; font-size: 0.88rem;
    border: 1px solid rgba(128, 128, 128, 0.3);
}
a.vg-chip-link { text-decoration: none; color: inherit; border-color: rgba(99, 102, 241, 0.6); }
a.vg-chip-link:hover { background: rgba(99, 102, 241, 0.14); }
a.vg-dict {
    display: inline-block; margin-right: 0.8rem; font-size: 0.82rem; text-decoration: none; opacity: 0.8;
}
a.vg-dict:hover { opacity: 1; text-decoration: underline; }
div.vg-card p.vg-dicts { margin: 0.9rem 0 0; }
.vg-sense { font-size: 0.8em; margin-left: 0.2em; opacity: 0.7; font-weight: 400; }
table.vg-compare { width: 100%; border-collapse: collapse; }
table.vg-compare th { text-align: left; font-size: 0.8rem; opacity: 0.6; font-weight: 600; }
table.vg-compare td, table.vg-compare th {
    padding: 0.45rem 0.5rem; border-bottom: 1px solid rgba(128, 128, 128, 0.2); vertical-align: top;
}
.vg-badge-sub { background: rgba(16, 185, 129, 0.16); }
.vg-stars { color: #f59e0b; letter-spacing: 0.05em; white-space: nowrap; }
.vg-list-stars { font-size: 0.8rem; letter-spacing: 0; }

/* フラッシュカードの問題面 */
div.vg-card.vg-flash {
    min-height: 220px; display: flex; flex-direction: column;
    justify-content: center; align-items: center; text-align: center;
}
div.vg-card p.vg-flash-text {
    font-size: 2.6rem; font-weight: 700; line-height: 1.4; margin: 0.4rem 0;
}
div.vg-card.vg-flash p.vg-flash-text.vg-long { font-size: 1.5rem; }
div.vg-card p.vg-meta { font-size: 0.78rem; opacity: 0.5; margin-top: 1rem; }

/* 語彙ライブラリの一覧(key="vlist" / "vrow-…" の container に付くクラスで装飾) */
.st-key-vlist { gap: 0 !important; }
div[class*="st-key-vrow-"], .st-key-vlist-head {
    border-bottom: 1px solid rgba(128, 128, 128, 0.2);
    padding: 0.7rem 0.2rem;
}
.st-key-vlist-head { border-bottom-width: 2px; padding-bottom: 0.35rem; }
div[class*="st-key-vrow-"]:hover { background: rgba(128, 128, 128, 0.06); }
/* 狭い画面でも 1 行に収め、一番右の列(「詳細」ボタンなど)は文字が切れないよう最小幅を確保する */
div[class*="st-key-vrow-"] [data-testid="stHorizontalBlock"],
.st-key-vlist-head [data-testid="stHorizontalBlock"] { flex-wrap: nowrap; }
div[class*="st-key-vrow-"] [data-testid="stColumn"]:last-child,
.st-key-vlist-head [data-testid="stColumn"]:last-child { min-width: 3.5em; flex: 0 0 3.5em; }
.vg-list-head { font-size: 0.8rem; font-weight: 600; opacity: 0.6; }
.vg-list-word { font-size: 1.3rem; font-weight: 700; line-height: 1.9; }
.vg-list-word rt { font-size: 0.55em; font-weight: 400; opacity: 0.7; }
.vg-list-text { line-height: 1.7; }
.vg-list-ex { font-size: 0.9rem; line-height: 1.7; opacity: 0.85; }
.vg-list-ex + .vg-list-ex { margin-top: 0.2rem; }
.vg-muted { opacity: 0.4; }

/* 作文トレーニング */
div.vg-card.vg-prompt p.vg-prompt-text {
    font-size: 1.45rem; font-weight: 700; line-height: 1.6; margin: 0.5rem 0 0;
}
div.vg-card.vg-wordcard { padding: 0.9rem 1.1rem; height: 100%; }
.vg-essay {
    white-space: pre-wrap; line-height: 1.9; padding: 0.8rem 1rem; margin: 0.4rem 0 0.8rem;
    border-left: 3px solid rgba(99, 102, 241, 0.5); background: rgba(128, 128, 128, 0.06);
    border-radius: 6px;
}

/* 穴埋めクイズ */
div.vg-card.vg-quiz p.vg-quiz-text { font-size: 1.5rem; line-height: 1.9; margin: 0.4rem 0 0; }
.vg-blank {
    display: inline-block; min-width: 5em; margin: 0 0.2em;
    border-bottom: 2px solid rgba(99, 102, 241, 0.8); background: rgba(99, 102, 241, 0.12);
}
.vg-choice-row {
    display: flex; align-items: baseline; gap: 1rem; padding: 0.45rem 0;
    border-bottom: 1px solid rgba(128, 128, 128, 0.15);
}
.vg-choice-row:last-child { border-bottom: none; }
.vg-choice-mark { width: 1.4em; flex: none; }
.vg-choice-row .vg-list-word { min-width: 6em; flex: none; }

.vg-record-item { padding: 0.35rem 0; border-bottom: 1px solid rgba(128, 128, 128, 0.15); }
.vg-record-item .vg-muted { font-size: 0.8rem; }

/* 読解トレーニング:登録済みの語彙の印 */
mark.vg-known { background: rgba(245, 158, 11, 0.28); color: inherit; padding: 0 0.1em; border-radius: 3px; }
.vg-reading-body { line-height: 2; }

/* ホーム画面の機能カード */
.vg-feature-desc { opacity: 0.7; font-size: 0.9rem; min-height: 2.8em; }

/* ---------- スマホなど幅の狭い画面(640px 以下) ---------- */
@media (max-width: 640px) {
    .block-container { padding: 1.2rem 0.8rem 3rem; }
    .stApp h1 { font-size: 1.9rem; }
    .stApp h3 { font-size: 1.25rem; }
    div.vg-card { padding: 1rem 1.1rem; }
    div.vg-card p.vg-word { font-size: 1.6rem; }
    div.vg-card p.vg-flash-text { font-size: 2rem; }
    div.vg-card.vg-flash { min-height: 160px; }
    div.vg-card.vg-flash p.vg-flash-text.vg-long,
    div.vg-card.vg-quiz p.vg-quiz-text,
    div.vg-card.vg-prompt p.vg-prompt-text { font-size: 1.2rem; }
    /* 一覧の行は折り返して縦に並べる(PC 用の「1 行に収める」指定を解除) */
    div[class*="st-key-vrow-"] [data-testid="stHorizontalBlock"],
    .st-key-vlist-head [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
    .st-key-vlist-head { display: none; }
    div[class*="st-key-vrow-"] [data-testid="stColumn"]:last-child { flex: 1 1 100%; }
    /* 指で押しやすいよう、ボタンを少し大きく */
    .stButton button, .stFormSubmitButton button { min-height: 2.75rem; }
    table.vg-compare td, table.vg-compare th { padding: 0.35rem 0.25rem; font-size: 0.9rem; }
}
</style>
"""


def apply_base_style() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
