"""習得状況(review_state)と学習履歴(study_log)の DB 操作。"""

import random
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from vorge.db import get_connection
from vorge.flashcard import scheduler


@dataclass
class ReviewState:
    vocab_id: int
    interval_days: int
    next_review: str
    review_count: int
    correct_count: int
    unsure_count: int
    wrong_count: int
    last_result: str
    last_studied_at: str

    @property
    def mastery(self) -> str:
        return scheduler.mastery_label(self.interval_days)


def _filter_sql(
    categories: list[str] | None, difficulty_range: tuple[int, int]
) -> tuple[str, list]:
    """語彙のカテゴリ・難易度で絞り込む WHERE 句(v. は vocab テーブル)。"""
    where = "v.difficulty BETWEEN ? AND ?"
    params: list = [difficulty_range[0], difficulty_range[1]]
    if categories:
        where += f" AND v.category IN ({','.join('?' * len(categories))})"
        params.extend(categories)
    return where, params


class ReviewRepository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    # ---------- 回答の記録 ----------

    def record_answer(
        self,
        vocab_id: int,
        result: str,
        mode: str = scheduler.MODE_WORD_TO_MEANING,
        now: datetime | None = None,
    ) -> ReviewState:
        """回答を 1 件記録し、次回復習日を更新する。

        学習履歴への追加と習得状況の更新を 1 つのトランザクションで行うので、
        片方だけ保存されて食い違うことはない。
        """
        now = now or datetime.now()
        current = self.get_state(vocab_id)
        # next_interval は不明な result で ValueError を出すので、
        # 下の SQL に埋め込む {result}_count は必ず 3 種類の列名のどれかになる
        interval = scheduler.next_interval(current.interval_days if current else None, result)
        next_review = scheduler.next_review_date(now.date(), interval).isoformat()
        studied_at = now.strftime("%Y-%m-%d %H:%M:%S")

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO study_log
                    (vocab_id, studied_at, mode, result, interval_days, next_review)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (vocab_id, studied_at, mode, result, interval, next_review),
            )
            # ON CONFLICT … DO UPDATE は「行があれば更新、無ければ追加」。
            # INSERT OR REPLACE と違って行を削除しないので安全。
            conn.execute(
                f"""
                INSERT INTO review_state (
                    vocab_id, interval_days, next_review, review_count,
                    correct_count, unsure_count, wrong_count, last_result, last_studied_at
                ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(vocab_id) DO UPDATE SET
                    interval_days   = excluded.interval_days,
                    next_review     = excluded.next_review,
                    review_count    = review_count + 1,
                    {result}_count  = {result}_count + 1,
                    last_result     = excluded.last_result,
                    last_studied_at = excluded.last_studied_at
                """,
                (
                    vocab_id,
                    interval,
                    next_review,
                    int(result == scheduler.CORRECT),
                    int(result == scheduler.UNSURE),
                    int(result == scheduler.WRONG),
                    result,
                    studied_at,
                ),
            )
        return self.get_state(vocab_id)

    # ---------- 取得 ----------

    def get_state(self, vocab_id: int) -> ReviewState | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM review_state WHERE vocab_id = ?", (vocab_id,)
            ).fetchone()
        return ReviewState(**dict(row)) if row else None

    def all_states(self) -> dict[int, ReviewState]:
        """語彙ID → 習得状況 の辞書(一覧表示用。未学習の語彙は含まれない)。"""
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM review_state").fetchall()
        return {r["vocab_id"]: ReviewState(**dict(r)) for r in rows}

    def history(self, vocab_id: int) -> list[dict]:
        """1 語彙の学習履歴(新しい順)。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM study_log WHERE vocab_id = ? ORDER BY studied_at DESC, id DESC",
                (vocab_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------- 出題の選択 ----------

    def due_ids(
        self,
        today: date,
        categories: list[str] | None = None,
        difficulty_range: tuple[int, int] = (1, 5),
    ) -> list[int]:
        """復習日が今日以前の語彙(期限を過ぎた古いものから順)。"""
        where, params = _filter_sql(categories, difficulty_range)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT v.id FROM vocab v JOIN review_state r ON r.vocab_id = v.id
                WHERE r.next_review <= ? AND {where}
                ORDER BY r.next_review ASC, v.id ASC
                """,
                [today.isoformat(), *params],
            ).fetchall()
        return [r[0] for r in rows]

    def new_ids(
        self,
        categories: list[str] | None = None,
        difficulty_range: tuple[int, int] = (1, 5),
    ) -> list[int]:
        """まだ一度も学習していない語彙(登録順)。"""
        where, params = _filter_sql(categories, difficulty_range)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT v.id FROM vocab v
                WHERE NOT EXISTS (SELECT 1 FROM review_state r WHERE r.vocab_id = v.id)
                  AND {where}
                ORDER BY v.id ASC
                """,
                params,
            ).fetchall()
        return [r[0] for r in rows]

    def build_queue(
        self,
        today: date,
        new_limit: int,
        categories: list[str] | None = None,
        difficulty_range: tuple[int, int] = (1, 5),
        shuffle: bool = True,
    ) -> list[int]:
        """今回出題する語彙 ID の並び。復習予定の語彙を先に、その後に新しい語彙を出す。

        shuffle=True でも「復習 → 新規」の優先順は保ち、それぞれのグループ内だけ混ぜる。
        """
        due = self.due_ids(today, categories, difficulty_range)
        new = self.new_ids(categories, difficulty_range)
        if shuffle:
            random.shuffle(due)
            random.shuffle(new)
        return due + new[: max(new_limit, 0)]

    # ---------- 集計(ホーム画面用) ----------

    def count_due(self, today: date) -> int:
        with self._connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM review_state WHERE next_review <= ?", (today.isoformat(),)
            ).fetchone()[0]

    def count_new_studied_on(self, day: date) -> int:
        """指定日に「はじめて」学習した語彙の数。"""
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT vocab_id FROM study_log
                    GROUP BY vocab_id HAVING date(MIN(studied_at)) = ?
                )
                """,
                (day.isoformat(),),
            ).fetchone()[0]

    def count_answers_on(self, day: date) -> int:
        with self._connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM study_log WHERE date(studied_at) = ?", (day.isoformat(),)
            ).fetchone()[0]

    def count_unstudied(self) -> int:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT COUNT(*) FROM vocab v
                WHERE NOT EXISTS (SELECT 1 FROM review_state r WHERE r.vocab_id = v.id)
                """
            ).fetchone()[0]
