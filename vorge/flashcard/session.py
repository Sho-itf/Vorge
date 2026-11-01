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
    state.setdefault("fc_first_count", 0)  # 最初に決めた出題数(これ以降は「もう一度」の分)
    state.setdefault("fc_retry_results", [])  # 「もう一度」の結果(記録には残さない)


def start(state: MutableMapping, queue: list[int], mode: str, label: str = "") -> None:
    """新しい出題を始める。"""
    state["fc_queue"] = list(queue)
    state["fc_pos"] = 0
    state["fc_revealed"] = False
    state["fc_mode"] = mode
    state["fc_results"] = []
    state["fc_label"] = label
    state["fc_first_count"] = len(queue)
    state["fc_retry_results"] = []


def is_retry(state: MutableMapping, pos: int) -> bool:
    """pos 枚目が、間違えた語彙の「もう一度」かどうか。"""
    return pos >= state["fc_first_count"]


def add_retry(state: MutableMapping, vocab_id: int) -> None:
    """不正解だった語彙を、今回の最後にもう一度出す(1 語につき 1 回まで)。"""
    retries = state["fc_queue"][state["fc_first_count"]:]
    if vocab_id not in retries:
        state["fc_queue"].append(vocab_id)


def reset(state: MutableMapping) -> None:
    """設定画面に戻る。"""
    state["fc_queue"] = None
