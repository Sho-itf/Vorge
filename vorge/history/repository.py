"""学習履歴の集計。データを書き換えることはなく、読み取りだけを行う。"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from vorge.db import get_connection
from vorge.flashcard import scheduler


@dataclass
class DailyCount:
    day: date
    correct: int = 0
    unsure: int = 0
    wrong: int = 0

    @property
    def total(self) -> int:
        return self.correct + self.unsure + self.wrong


@dataclass
class WeakVocab:
    vocab_id: int
    word: str
    meaning: str
    review_count: int
    correct_count: int
    unsure_count: int
    wrong_count: int
    last_result: str
    next_review: str

    @property
    def accuracy(self) -> float:
        """正答率(正解 ÷ 全回答)。「自信がない」は正解に含めない。"""
        return self.correct_count / self.review_count if self.review_count else 0.0


class HistoryRepository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    # ---------- 全体の数字 ----------

    def total_answers(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM study_log").fetchone()[0]

    def studied_vocab_count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM review_state").fetchone()[0]

    def accuracy_between(self, start: date, end: date) -> float | None:
        """start〜end(両端を含む)の正答率。回答が無ければ None。"""
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*), SUM(result = ?) FROM study_log
                WHERE date(studied_at) BETWEEN ? AND ?
                """,
                (scheduler.CORRECT, start.isoformat(), end.isoformat()),
            ).fetchone()
        total, correct = row[0], row[1] or 0
        return correct / total if total else None

    def streak(self, today: date) -> int:
        """今日(まだなら昨日)からさかのぼって、毎日学習が続いている日数。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT date(studied_at) FROM study_log WHERE date(studied_at) <= ?",
                (today.isoformat(),),
            ).fetchall()
        days = {date.fromisoformat(r[0]) for r in rows}
        day = today if today in days else today - timedelta(days=1)
        count = 0
        while day in days:
            count += 1
            day -= timedelta(days=1)
        return count

    # ---------- グラフ用 ----------

    def daily_counts(self, start: date, end: date) -> list[DailyCount]:
        """start〜end の日ごとの回答数。回答が無い日も 0 件として含める。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT date(studied_at) AS d, result, COUNT(*) AS n FROM study_log
                WHERE date(studied_at) BETWEEN ? AND ?
                GROUP BY d, result
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        days = {
            start + timedelta(days=i): DailyCount(start + timedelta(days=i))
            for i in range((end - start).days + 1)
        }
        for r in rows:
            setattr(days[date.fromisoformat(r["d"])], r["result"], r["n"])
        return list(days.values())

    def upcoming_reviews(self, today: date, days: int = 7) -> list[tuple[date, int]]:
        """今日から days 日分の復習予定数。今日の分には期限切れの語彙も含める。"""
        end = today + timedelta(days=days - 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT MAX(next_review, ?) AS d, COUNT(*) FROM review_state
                WHERE next_review <= ? GROUP BY d
                """,
                (today.isoformat(), end.isoformat()),
            ).fetchall()
        counts = {date.fromisoformat(r[0]): r[1] for r in rows}
        return [
            (today + timedelta(days=i), counts.get(today + timedelta(days=i), 0))
            for i in range(days)
        ]

    def mastery_distribution(self) -> dict[str, int]:
        """習得状況ごとの語彙数(未学習 / 学習中 / 定着中 / 習得)。"""
        result = {label: 0 for label in ("未学習", "学習中", "定着中", "習得")}
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT r.interval_days FROM vocab v
                LEFT JOIN review_state r ON r.vocab_id = v.id
                """
            ).fetchall()
        for (interval,) in rows:
            result[scheduler.mastery_label(interval)] += 1
        return result

    # ---------- 一覧 ----------

    def weak_vocab(self, limit: int = 20) -> list[WeakVocab]:
        """苦手な語彙:不正解か「自信がない」が 1 回以上あり、正答率の低い順。

        正答率が同じなら、不正解の回数が多いもの → 最後の回答が不正解のものを先にする。
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT v.id AS vocab_id, v.word, v.meaning,
                       r.review_count, r.correct_count, r.unsure_count, r.wrong_count,
                       r.last_result, r.next_review
                FROM review_state r JOIN vocab v ON v.id = r.vocab_id
                WHERE r.wrong_count + r.unsure_count > 0
                ORDER BY CAST(r.correct_count AS REAL) / r.review_count ASC,
                         r.wrong_count DESC,
                         r.last_result = 'wrong' DESC,
                         v.id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [WeakVocab(**dict(r)) for r in rows]

    def recent_logs(self, limit: int = 50) -> list[dict]:
        """最近の回答(新しい順)。語彙名つき。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT l.studied_at, v.word, l.mode, l.result, l.next_review
                FROM study_log l JOIN vocab v ON v.id = l.vocab_id
                ORDER BY l.studied_at DESC, l.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]
