"""間隔反復(次にいつ復習するか)の計算。FSRS という方式を fsrs ライブラリで使う。

FSRS は語彙ごとに「覚えやすさ(難しさ)」と「記憶の安定度」を記録し、
「次に出題したとき 90% の確率で思い出せる日」を復習日にする。
同じ「正解」でも、覚えやすい語彙ほど・何度も正解している語彙ほど間隔が大きく延びる。

回答の 4 段階と FSRS の評価の対応:
  不正解 → Again / 自信がない → Hard / 正解 → Good / 簡単 → Easy

Vorge は「日」単位で復習するので、分単位の学習ステップは使わない(learning_steps を空にする)。
"""

from datetime import UTC, date, datetime, timedelta

from fsrs import Card, Rating, Scheduler, State

from vorge import timeutil

WRONG = "wrong"
UNSURE = "unsure"
CORRECT = "correct"
EASY = "easy"
RESULTS = (WRONG, UNSURE, CORRECT, EASY)  # ボタンの並び順(キーボードの 1〜4 に対応)
RESULT_LABELS = {WRONG: "不正解", UNSURE: "自信がない", CORRECT: "正解", EASY: "簡単"}
CORRECT_RESULTS = (CORRECT, EASY)  # 正答率で「正解」として数えるもの
_RATINGS = {WRONG: Rating.Again, UNSURE: Rating.Hard, CORRECT: Rating.Good, EASY: Rating.Easy}

MODE_WORD_TO_MEANING = "word_to_meaning"
MODE_MEANING_TO_WORD = "meaning_to_word"
MODE_CLOZE = "cloze"
MODE_LABELS = {
    MODE_WORD_TO_MEANING: "語彙 → 意味",
    MODE_MEANING_TO_WORD: "意味 → 語彙",
    MODE_CLOZE: "例文の穴埋め → 語彙",
}

_scheduler = Scheduler(learning_steps=(), relearning_steps=(), maximum_interval=3650, enable_fuzzing=True)


def configure(enable_fuzzing: bool) -> None:
    """間隔の「ゆらぎ」(同じ日に復習が集中しないよう少しずらす)の有無。テストでは切って結果を固定する。"""
    global _scheduler
    _scheduler = Scheduler(
        learning_steps=(), relearning_steps=(), maximum_interval=3650, enable_fuzzing=enable_fuzzing
    )


def _utc(moment: datetime) -> datetime:
    """FSRS はタイムゾーン付きの日時(UTC)を使うので変換する。"""
    return moment.astimezone(UTC)


def load_card(card_json: str) -> Card:
    return Card.from_json(card_json) if card_json else Card()


def legacy_card(interval_days: int, next_review: str, last_studied_at: str) -> Card:
    """以前の方式(固定倍率)で学習済みの語彙を、FSRS のカードに変換する。

    今の復習間隔をそのまま「記憶の安定度」とみなし、難しさは標準(5)から始める。
    """
    last = datetime.fromisoformat(last_studied_at).astimezone()
    due = datetime.combine(date.fromisoformat(next_review), last.timetz())
    return Card(
        state=State.Review,
        stability=float(max(interval_days, 1)),
        difficulty=5.0,
        due=_utc(due),
        last_review=_utc(last),
    )


def review(card: Card, result: str, now: datetime) -> tuple[Card, date, int]:
    """回答を反映した新しいカードと、次回復習日(「今日」の区切りで数えた日付)・間隔(日数)を返す。"""
    if result not in _RATINGS:
        raise ValueError(f"不明な回答結果です: {result}")
    new_card, _ = _scheduler.review_card(card, _RATINGS[result], _utc(now))
    due_day = timeutil.logical_date(new_card.due.astimezone().replace(tzinfo=None))
    today = timeutil.logical_date(now)
    due_day = max(due_day, today + timedelta(days=1))  # 少なくとも翌日以降
    return new_card, due_day, (due_day - today).days


def preview(card: Card, now: datetime) -> dict[str, int]:
    """それぞれの回答をしたら、次の復習まで何日になるか(ボタンに表示する)。"""
    return {result: review(card, result, now)[2] for result in RESULTS}


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
    if days == 1:
        return "明日"
    if days < 60:
        return f"{days}日後"
    if days < 365:
        return f"約{round(days / 30)}か月後"
    return f"約{days / 365:.1f}年後"
