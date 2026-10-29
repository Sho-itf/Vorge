"""フラッシュカードの「今の出題状況」を session_state に出し入れする関数。

フラッシュカード画面だけでなく、学習履歴画面の「苦手な語彙を練習する」からも
出題を始められるよう、ここにまとめている。
"""

from typing import MutableMapping

from vorge.flashcard import scheduler


def init(state: MutableMapping) -> None:
    """まだ値が無ければ初期値を入れる。"""
    state.setdefault("fc_queue", None)  # 出題する語彙IDの並び(None なら設定画面)
    state.setdefault("fc_pos", 0)  # 今何枚目か(0 始まり)
    state.setdefault("fc_revealed", False)  # 答えを表示中か
    state.setdefault("fc_mode", scheduler.MODE_WORD_TO_MEANING)
    state.setdefault("fc_results", [])  # 回答の記録(結果画面用)
    state.setdefault("fc_label", "")  # 出題の種類(「苦手な語彙」など)


def start(state: MutableMapping, queue: list[int], mode: str, label: str = "") -> None:
    """新しい出題を始める。"""
    state["fc_queue"] = queue
    state["fc_pos"] = 0
    state["fc_revealed"] = False
    state["fc_mode"] = mode
    state["fc_results"] = []
    state["fc_label"] = label


def reset(state: MutableMapping) -> None:
    """設定画面に戻る。"""
    state["fc_queue"] = None
