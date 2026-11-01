"""学習履歴の集計。データを書き換えることはなく、読み取りだけを行う。"""

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from vorge import timeutil
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
    """苦手な語彙。フラッシュカードと穴埋めクイズの結果を合わせて判定する。"""

    vocab_id: int
    word: str
    meaning: str
    correct_count: int  # フラッシュカード:正解
    unsure_count: int  # フラッシュカード:自信がない
    wrong_count: int  # フラッシュカード:不正解
    quiz_correct: int
    quiz_wrong: int
    last_result: str | None  # フラッシュカードの前回の結果(未学習なら None)
    next_review: str | None
    accuracy: float  # 合計の正答率(「自信がない」は 0.5 回の正解として数える)


# この正答率を下回り、かつ間違えたことのある語彙を「苦手」とする
WEAK_ACCURACY = 0.8

_WEAK_SQL = """
WITH q AS (
    SELECT vocab_id, SUM(correct) AS qc, SUM(1 - correct) AS qw FROM quiz_log GROUP BY vocab_id
),
s AS (
    SELECT v.id AS vocab_id, v.word, v.meaning,
           COALESCE(r.correct_count + r.easy_count, 0) AS fc, COALESCE(r.unsure_count, 0) AS fu,
           COALESCE(r.wrong_count, 0) AS fw, COALESCE(q.qc, 0) AS qc, COALESCE(q.qw, 0) AS qw,
           r.last_result, r.next_review
    FROM vocab v
    LEFT JOIN review_state r ON r.vocab_id = v.id
    LEFT JOIN q ON q.vocab_id = v.id
)
SELECT *, (fc + 0.5 * fu + qc) * 1.0 / (fc + fu + fw + qc + qw) AS acc
FROM s
WHERE fw + fu + qw > 0 AND (fc + 0.5 * fu + qc) * 1.0 / (fc + fu + fw + qc + qw) < ?
ORDER BY acc ASC, fw + qw DESC, vocab_id ASC
"""


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
                f"""
                SELECT COUNT(*), SUM(result IN (?, ?)) FROM study_log
                WHERE {timeutil.sql_date('studied_at')} BETWEEN ? AND ?
                """,
                (*scheduler.CORRECT_RESULTS, start.isoformat(), end.isoformat()),
            ).fetchone()
        total, correct = row[0], row[1] or 0
        return correct / total if total else None

    def streak(self, today: date) -> int:
        """今日(まだなら昨日)からさかのぼって、毎日学習が続いている日数。"""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT {timeutil.sql_date('studied_at')} AS d FROM study_log WHERE d <= ?",
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
                f"""
                SELECT {timeutil.sql_date('studied_at')} AS d, result, COUNT(*) AS n FROM study_log
                WHERE d BETWEEN ? AND ?
                GROUP BY d, result
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        days = {
            start + timedelta(days=i): DailyCount(start + timedelta(days=i))
            for i in range((end - start).days + 1)
        }
        for r in rows:
            day = days[date.fromisoformat(r["d"])]
            name = "correct" if r["result"] in scheduler.CORRECT_RESULTS else r["result"]  # 「簡単」は正解に含める
            setattr(day, name, getattr(day, name) + r["n"])
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

    def weak_vocab(self, limit: int | None = 20) -> list[WeakVocab]:
        """苦手な語彙(正答率の低い順)。全機能の「苦手」はこの判定を共通で使う。

        フラッシュカードと穴埋めクイズの回答を合わせた正答率が WEAK_ACCURACY 未満で、
        不正解か「自信がない」が 1 回以上ある語彙。
        正答率が同じなら、間違えた回数(フラッシュカード+クイズ)の多いものを先にする。
        """
        sql = _WEAK_SQL + (" LIMIT ?" if limit is not None else "")
        params = (WEAK_ACCURACY, limit) if limit is not None else (WEAK_ACCURACY,)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            WeakVocab(r["vocab_id"], r["word"], r["meaning"], r["fc"], r["fu"], r["fw"],
                      r["qc"], r["qw"], r["last_result"], r["next_review"], r["acc"])
            for r in rows
        ]

    def weak_ids(self) -> list[int]:
        return [w.vocab_id for w in self.weak_vocab(limit=None)]

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
