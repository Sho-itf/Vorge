"""「今日の学習」メニュー:1 日の目標と、今日の進み具合をまとめる。

目標は設定画面で変えられる(app_settings に保存)。
- 復習:復習日が来ている語彙をすべて
- 新しい語彙:1 日に覚える数
- 穴埋めクイズ:1 日に解く問題数
- 作文・議論:1 日に書く本数
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from vorge.flashcard.repository import ReviewRepository
from vorge.quiz.repository import QuizRepository
from vorge.settings import get_setting
from vorge.writing.repository import WritingRepository

GOAL_DEFAULTS = {"daily_new": 10, "daily_quiz": 10, "daily_writing": 1}
GOAL_LABELS = {
    "daily_new": "1 日に覚える新しい語彙の数",
    "daily_quiz": "1 日に解く穴埋めクイズの問題数",
    "daily_writing": "1 日に書く作文・議論の本数",
}


@dataclass
class DailyTask:
    key: str
    label: str
    page: str  # 取り組む画面
    current: int
    target: int
    unit: str

    @property
    def done(self) -> bool:
        return self.current >= self.target

    @property
    def progress_text(self) -> str:
        if self.key == "review":
            return "完了" if self.done else f"残り {self.target - self.current} 語"
        return f"{min(self.current, self.target)} / {self.target} {self.unit}"


def goals(db_path: Path | None = None) -> dict[str, int]:
    return {k: int(get_setting(k, v, db_path)) for k, v in GOAL_DEFAULTS.items()}


def today_tasks(today: date, db_path: Path | None = None) -> list[DailyTask]:
    """今日のメニュー。目標が 0 の項目は出さない。"""
    review = ReviewRepository(db_path)
    g = goals(db_path)
    due = review.count_due(today)
    tasks = [
        # 復習は「残り 0 語」で完了。target に残りの数を入れ、current は 0 か target にする
        DailyTask("review", "復習", "views/flashcard.py", 0 if due else 1, due or 1, "語"),
        DailyTask("new", "新しい語彙", "views/flashcard.py", review.count_new_studied_on(today),
                  g["daily_new"], "語"),
        DailyTask("quiz", "穴埋めクイズ", "views/quiz.py", QuizRepository(db_path).count_answers_on(today),
                  g["daily_quiz"], "問"),
        DailyTask("writing", "作文・議論", "views/writing.py",
                  WritingRepository(db_path).count_writings_on(today), g["daily_writing"], "本"),
    ]
    return [t for t in tasks if t.key == "review" or t.target > 0]


def next_task(tasks: list[DailyTask]) -> DailyTask | None:
    return next((t for t in tasks if not t.done), None)
