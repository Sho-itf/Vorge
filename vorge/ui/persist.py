"""画面の設定や書きかけの文章を、ブラウザを閉じても残るように DB に保存するための共通処理。

使い方(画面ファイルの先頭で):
    load_settings({"qz_count": 10, ...})          # 前回の値を session_state に読み込む
    st.slider(..., key="qz_count", on_change=save_setting, args=("qz_count",))
"""

from typing import Any

import streamlit as st

from vorge.settings import delete_setting, get_setting, set_setting

_DRAFT_PREFIX = "draft_"


def load_settings(defaults: dict[str, Any]) -> None:
    """まだ session_state に無い設定を DB(無ければ初期値)から読み込む。

    ウィジェットに結びついた値は、そのウィジェットを表示しないページに移ると
    Streamlit が消してしまうので、毎回このチェックで読み込み直す。
    segmented_control は同じボタンをもう一度押すと None になるので、そのときは初期値に戻す。
    """
    ss = st.session_state
    for key, default in defaults.items():
        if key not in ss:
            ss[key] = get_setting(key, default)
        if ss[key] is None:
            ss[key] = default


def save_setting(key: str) -> None:
    """session_state の値を DB に保存する(ウィジェットの on_change に渡す)。"""
    value = st.session_state.get(key)
    if value is not None:
        set_setting(key, list(value) if isinstance(value, tuple) else value)


# ---------- 書きかけの文章(作文・議論) ----------


def save_draft(name: str, value: Any) -> None:
    set_setting(_DRAFT_PREFIX + name, value)


def load_draft(name: str) -> Any:
    return get_setting(_DRAFT_PREFIX + name, None)


def clear_draft(name: str) -> None:
    delete_setting(_DRAFT_PREFIX + name)
