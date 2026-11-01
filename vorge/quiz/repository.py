"""穴埋めクイズの出題(問題セットの作成)と、回答記録の DB 操作。"""

import random
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from vorge import timeutil
from vorge.db import get_connection
from vorge.flashcard.repository import ReviewRepository
from vorge.quiz.builder import Question, blanks_for, make_question, pick_distractors
from vorge.vocab.repository import VocabRepository

FORMAT_CHOICE = "choice"
FORMAT_INPUT = "input"
FORMAT_LABELS = {FORMAT_CHOICE: "4択", FORMAT_INPUT: "入力式"}

# 出題範囲("all" 以外は ReviewRepository.ids_in_group のグループ名)
SCOPE_LABELS = {
    "all": "おまかせ(全語彙)",
    "weak": "苦手な語彙",
    "learning": "学習中の語彙",
    "new": "未学習の語彙",
}


@dataclass
class MissedVocab:
    vocab_id: int
    word: str
    meaning: str
    total: int
    wrong: int


class QuizRepository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path
        self.vocab_repo = VocabRepository(db_path)
        self.review_repo = ReviewRepository(db_path)

    def _connect(self):
        return get_connection(self.db_path)

    # ---------- 出題 ----------

    def eligible_vocab(
        self,
        scope: str = "all",
        categories: list[str] | None = None,
        difficulty_range: tuple[int, int] = (1, 5),
    ) -> list:
        """出題できる語彙(条件に合い、除外していない例文の中にその語彙が含まれているもの)。"""
        vocabs = self.vocab_repo.search(categories=categories, difficulty_range=difficulty_range)
        if scope != "all":
            in_scope = set(self.review_repo.ids_in_group(scope))
            vocabs = [v for v in vocabs if v.id in in_scope]
        excluded = self.excluded_map()
        return [v for v in vocabs if blanks_for(v, excluded.get(v.id, set()))]

    def build_questions(
        self,
        count: int,
        scope: str = "all",
        categories: list[str] | None = None,
        difficulty_range: tuple[int, int] = (1, 5),
        only_ids: list[int] | None = None,
    ) -> list[Question]:
        """問題を count 問作る。only_ids を渡すとその語彙だけで作る(間違えた語彙の復習用)。

        はずれの選択肢は、出題範囲に関係なく登録済みの全語彙から選ぶ。
        """
        excluded = self.excluded_map()
        if only_ids is not None:
            pool = [v for v in self.vocab_repo.get_many(only_ids).values()
                    if blanks_for(v, excluded.get(v.id, set()))]
        else:
            pool = self.eligible_vocab(scope, categories, difficulty_range)
        random.shuffle(pool)
        all_vocab = self.vocab_repo.list_all()
        return [
            make_question(v, random.choice(blanks_for(v, excluded.get(v.id, set()))),
                          pick_distractors(v, all_vocab))
            for v in pool[:count]
        ]

    # ---------- 記録 ----------

    def record(
        self, vocab_id: int, fmt: str, correct: bool, answer: str, now: datetime | None = None
    ) -> int:
        """回答を記録し、その記録の ID を返す。"""
        now = now or datetime.now()
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO quiz_log (vocab_id, answered_at, format, correct, answer) "
                "VALUES (?, ?, ?, ?, ?)",
                (vocab_id, now.strftime("%Y-%m-%d %H:%M:%S"), fmt, int(correct), answer),
            )
            return cur.lastrowid

    # ---------- 「この問題はおかしい」 ----------

    def exclude_example(self, vocab_id: int, sentence: str, log_id: int | None = None) -> None:
        """例文を今後の出題から外す。log_id を渡すと、その問題の回答記録も取り消す。"""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO quiz_excluded (vocab_id, sentence) VALUES (?, ?)",
                (vocab_id, sentence),
            )
            if log_id is not None:
                conn.execute("DELETE FROM quiz_log WHERE id = ?", (log_id,))

    def restore_example(self, excluded_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM quiz_excluded WHERE id = ?", (excluded_id,))

    def excluded_examples(self) -> list[dict]:
        """除外した例文の一覧(新しい順)。語彙名つき。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT e.id, e.vocab_id, v.word, e.sentence, e.created_at "
                "FROM quiz_excluded e JOIN vocab v ON v.id = e.vocab_id "
                "ORDER BY e.created_at DESC, e.id DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def excluded_map(self) -> dict[int, set[str]]:
        """語彙ID → 除外した例文の集合。"""
        result: dict[int, set[str]] = {}
        for row in self.excluded_examples():
            result.setdefault(row["vocab_id"], set()).add(row["sentence"])
        return result

    def logs_for(self, vocab_id: int, limit: int = 10) -> list[dict]:
        """1 語彙のクイズの回答記録(新しい順)。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT answered_at, format, correct, answer FROM quiz_log WHERE vocab_id = ? "
                "ORDER BY answered_at DESC, id DESC LIMIT ?",
                (vocab_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ---------- 集計 ----------

    def total_answers(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM quiz_log").fetchone()[0]

    def accuracy_between(self, start: date, end: date) -> float | None:
        with self._connect() as conn:
            total, correct = conn.execute(
                "SELECT COUNT(*), SUM(correct) FROM quiz_log "
                f"WHERE {timeutil.sql_date('answered_at')} BETWEEN ? AND ?",
                (start.isoformat(), end.isoformat()),
            ).fetchone()
        return (correct or 0) / total if total else None

    def most_missed(self, limit: int = 10) -> list[MissedVocab]:
        """クイズでよく間違える語彙(間違えた回数の多い順)。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT v.id, v.word, v.meaning, COUNT(*) AS total,
                       SUM(1 - q.correct) AS wrong
                FROM quiz_log q JOIN vocab v ON v.id = q.vocab_id
                GROUP BY v.id HAVING wrong > 0
                ORDER BY wrong DESC, CAST(wrong AS REAL) / total DESC, v.id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [MissedVocab(*r) for r in rows]
