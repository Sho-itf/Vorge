"""間隔反復(次にいつ復習するか)の計算ルール。

DB にも画面にも依存しない純粋な計算だけを置いているので、ルールの調整やテストが簡単。

ルール:
  - 正解        → 間隔を 2.5 倍に延ばす(切り上げ)。例: 1日 → 3日 → 8日 → 20日 …
  - 自信がない  → 間隔はそのまま
  - 不正解      → 間隔を最短(1日 = 翌日)に戻す
はじめて学習する語彙は、間隔 1 日の状態から計算する。
"""

import math
from datetime import date, timedelta

CORRECT = "correct"
UNSURE = "unsure"
WRONG = "wrong"
RESULTS = (CORRECT, UNSURE, WRONG)

RESULT_LABELS = {CORRECT: "正解", UNSURE: "自信がない", WRONG: "不正解"}

MODE_WORD_TO_MEANING = "word_to_meaning"
MODE_MEANING_TO_WORD = "meaning_to_word"
MODE_LABELS = {
    MODE_WORD_TO_MEANING: "語彙 → 意味",
    MODE_MEANING_TO_WORD: "意味 → 語彙",
}

MIN_INTERVAL = 1
MAX_INTERVAL = 365
CORRECT_MULTIPLIER = 2.5


def next_interval(current: int | None, result: str) -> int:
    """今の間隔(日数)と回答結果から、次の間隔(日数)を返す。"""
    if result not in RESULTS:
        raise ValueError(f"不明な回答結果です: {result}")
    base = max(current or MIN_INTERVAL, MIN_INTERVAL)
    if result == CORRECT:
        return min(math.ceil(base * CORRECT_MULTIPLIER), MAX_INTERVAL)
    if result == UNSURE:
        return base
    return MIN_INTERVAL


def next_review_date(today: date, interval_days: int) -> date:
    return today + timedelta(days=interval_days)


def mastery_label(interval_days: int | None) -> str:
    """復習間隔の長さから、習得状況を 4 段階の言葉で表す。"""
    if interval_days is None:
        return "未学習"
    if interval_days < 7:
        return "学習中"
    if interval_days < 21:
        return "定着中"
    return "習得"


def interval_text(days: int) -> str:
    """ボタンなどに出す「次はいつか」の表示。"""
    return "明日" if days == 1 else f"{days}日後"
