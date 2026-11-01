"""穴埋めクイズの出題(問題セットの作成)と、回答記録の DB 操作。"""

import random
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

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
        """出題できる語彙(条件に合い、例文の中にその語彙が含まれているもの)。"""
        vocabs = self.vocab_repo.search(categories=categories, difficulty_range=difficulty_range)
        if scope != "all":
            in_scope = set(self.review_repo.ids_in_group(scope))
            vocabs = [v for v in vocabs if v.id in in_scope]
        return [v for v in vocabs if blanks_for(v)]

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
        if only_ids is not None:
            pool = [v for v in self.vocab_repo.get_many(only_ids).values() if blanks_for(v)]
        else:
            pool = self.eligible_vocab(scope, categories, difficulty_range)
        random.shuffle(pool)
        all_vocab = self.vocab_repo.list_all()
        return [
            make_question(v, random.choice(blanks_for(v)), pick_distractors(v, all_vocab))
            for v in pool[:count]
        ]

    # ---------- 記録 ----------

    def record(
        self, vocab_id: int, fmt: str, correct: bool, answer: str, now: datetime | None = None
    ) -> None:
        now = now or datetime.now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO quiz_log (vocab_id, answered_at, format, correct, answer) "
                "VALUES (?, ?, ?, ?, ?)",
                (vocab_id, now.strftime("%Y-%m-%d %H:%M:%S"), fmt, int(correct), answer),
            )

    # ---------- 集計 ----------

    def total_answers(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM quiz_log").fetchone()[0]

    def accuracy_between(self, start: date, end: date) -> float | None:
        with self._connect() as conn:
            total, correct = conn.execute(
                "SELECT COUNT(*), SUM(correct) FROM quiz_log "
                "WHERE date(answered_at) BETWEEN ? AND ?",
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
