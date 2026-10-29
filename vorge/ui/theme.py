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
.vg-badge-sub { background: rgba(16, 185, 129, 0.16); }
.vg-stars { color: #f59e0b; letter-spacing: 0.05em; }

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
.vg-list-head { font-size: 0.8rem; font-weight: 600; opacity: 0.6; }
.vg-list-word { font-size: 1.3rem; font-weight: 700; line-height: 1.9; }
.vg-list-word rt { font-size: 0.55em; font-weight: 400; opacity: 0.7; }
.vg-list-text { line-height: 1.7; }
.vg-list-ex { font-size: 0.9rem; line-height: 1.7; opacity: 0.85; }
.vg-list-ex + .vg-list-ex { margin-top: 0.2rem; }
.vg-muted { opacity: 0.4; }

/* ホーム画面の機能カード */
.vg-feature-desc { opacity: 0.7; font-size: 0.9rem; min-height: 2.8em; }
</style>
"""


def apply_base_style() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
