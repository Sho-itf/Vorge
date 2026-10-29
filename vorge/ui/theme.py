"""見た目(フォント・余白・カード)を整える CSS。

色は半透明(rgba)で指定しているため、ライトモードでもダークモードでも馴染む。
"""

import streamlit as st

_CSS = """
<style>
/* 日本語が読みやすいフォント。アイコン(Material Symbols)とコードは除外する */
.stApp, .stApp *:not([data-testid="stIconMaterial"]):not(code):not(pre) {
    font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Hiragino Sans",
                 "Yu Gothic UI", "Meiryo", sans-serif;
}
.stMarkdown p, .stMarkdown li { line-height: 1.8; }
.block-container { padding-top: 2.5rem; max-width: 1200px; }

/* 語彙カード */
.vg-card {
    border: 1px solid rgba(128, 128, 128, 0.25);
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 0.8rem;
}
.stApp .vg-card .vg-word { font-size: 2rem; font-weight: 700; line-height: 1.3; margin: 0; }
.stApp .vg-card .vg-reading { opacity: 0.65; font-size: 0.95rem; margin: 0.1rem 0 0.6rem; }
.stApp .vg-card .vg-meaning { font-size: 1.1rem; line-height: 1.8; margin: 0.4rem 0 0.8rem; }
.stApp .vg-card .vg-label {
    font-size: 0.78rem; font-weight: 600; opacity: 0.6;
    letter-spacing: 0.05em; margin: 0.9rem 0 0.2rem;
}
.stApp .vg-card .vg-text { line-height: 1.8; margin: 0; }
.vg-badge {
    display: inline-block; padding: 0.15rem 0.6rem; margin: 0 0.3rem 0.3rem 0;
    border-radius: 999px; font-size: 0.82rem;
    background: rgba(99, 102, 241, 0.14);
}
.vg-chip {
    display: inline-block; padding: 0.1rem 0.55rem; margin: 0 0.3rem 0.3rem 0;
    border-radius: 6px; font-size: 0.88rem;
    border: 1px solid rgba(128, 128, 128, 0.3);
}
.vg-stars { color: #f59e0b; letter-spacing: 0.05em; }
.stApp .vg-card .vg-meta { font-size: 0.78rem; opacity: 0.5; margin-top: 1rem; }

/* ホーム画面の機能カード */
.vg-feature-desc { opacity: 0.7; font-size: 0.9rem; min-height: 2.8em; }
</style>
"""


def apply_base_style() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
