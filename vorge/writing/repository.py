"""作文トレーニングの DB 操作(お題・作文の保存)と、使う語彙の選択。"""

import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from vorge.db import get_connection
from vorge.flashcard.repository import ReviewRepository
from vorge.writing import prompts as P


@dataclass
class Prompt:
    id: int
    kind: str
    text: str
    active: bool


@dataclass
class WritingWord:
    vocab_id: int
    word: str
    used: bool


@dataclass
class Writing:
    id: int
    prompt_id: int | None
    prompt_text: str
    kind: str
    min_chars: int
    max_chars: int
    body: str
    char_count: int
    feedback: str
    created_at: str
    updated_at: str
    words: list[WritingWord]


class WritingRepository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    # ---------- お題 ----------

    def list_prompts(self, kind: str | None = None, active_only: bool = False) -> list[Prompt]:
        where, params = [], []
        if kind:
            where.append("kind = ?")
            params.append(kind)
        if active_only:
            where.append("active = 1")
        sql = "SELECT id, kind, text, active FROM writing_prompts"
        if where:
            sql += " WHERE " + " AND ".join(where)
        with self._connect() as conn:
            rows = conn.execute(sql + " ORDER BY kind, id", params).fetchall()
        return [Prompt(r["id"], r["kind"], r["text"], bool(r["active"])) for r in rows]

    def random_prompt(self, kind: str, exclude_id: int | None = None) -> Prompt | None:
        """指定した種類(AUTO ならすべて)から、出題中のお題をランダムに 1 つ選ぶ。"""
        candidates = self.list_prompts(None if kind == P.AUTO else kind, active_only=True)
        others = [p for p in candidates if p.id != exclude_id]
        pool = others or candidates
        return random.choice(pool) if pool else None

    def add_prompt(self, kind: str, text: str) -> int:
        text = text.strip()
        if not text:
            raise ValueError("お題を入力してください。")
        if kind not in P.KIND_LABELS:
            raise ValueError(f"不明なお題の種類です: {kind}")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO writing_prompts (kind, text) VALUES (?, ?)", (kind, text)
            )
            return cur.lastrowid

    def update_prompt(self, prompt_id: int, kind: str, text: str, active: bool) -> None:
        text = text.strip()
        if not text:
            raise ValueError("お題を入力してください。")
        with self._connect() as conn:
            conn.execute(
                "UPDATE writing_prompts SET kind = ?, text = ?, active = ? WHERE id = ?",
                (kind, text, int(active), prompt_id),
            )

    def delete_prompt(self, prompt_id: int) -> None:
        """お題を削除する。そのお題で書いた作文は、お題の文面ごと残る。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM writing_prompts WHERE id = ?", (prompt_id,))

    # ---------- 作文 ----------

    def save_writing(
        self,
        prompt: Prompt,
        min_chars: int,
        max_chars: int,
        body: str,
        char_count: int,
        words: list[WritingWord],
    ) -> int:
        """作文と、指定した語彙(使えたかどうか)を 1 つのトランザクションで保存する。"""
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO writings
                    (prompt_id, prompt_text, kind, min_chars, max_chars, body, char_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (prompt.id, prompt.text, prompt.kind, min_chars, max_chars, body, char_count),
            )
            writing_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO writing_vocab (writing_id, vocab_id, word, used) VALUES (?, ?, ?, ?)",
                [(writing_id, w.vocab_id, w.word, int(w.used)) for w in words],
            )
        return writing_id

    def update_feedback(self, writing_id: int, feedback: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE writings SET feedback = ?, updated_at = datetime('now', 'localtime') "
                "WHERE id = ?",
                (feedback, writing_id),
            )

    def delete_writing(self, writing_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM writings WHERE id = ?", (writing_id,))

    def list_writings(self, vocab_id: int | None = None, kind: str | None = None) -> list[Writing]:
        """作文の一覧(新しい順)。vocab_id を指定すると、その語彙を使った作文だけ。"""
        where, params = [], []
        if vocab_id is not None:
            where.append("id IN (SELECT writing_id FROM writing_vocab WHERE vocab_id = ?)")
            params.append(vocab_id)
        if kind:
            where.append("kind = ?")
            params.append(kind)
        sql = "SELECT * FROM writings"
        if where:
            sql += " WHERE " + " AND ".join(where)
        with self._connect() as conn:
            rows = conn.execute(sql + " ORDER BY created_at DESC, id DESC", params).fetchall()
            links = conn.execute(
                "SELECT writing_id, vocab_id, word, used FROM writing_vocab ORDER BY rowid"
            ).fetchall()
        words: dict[int, list[WritingWord]] = {}
        for link in links:
            words.setdefault(link["writing_id"], []).append(
                WritingWord(link["vocab_id"], link["word"], bool(link["used"]))
            )
        return [Writing(**dict(r), words=words.get(r["id"], [])) for r in rows]

    def get_writing(self, writing_id: int) -> Writing | None:
        return next((w for w in self.list_writings() if w.id == writing_id), None)

    # ---------- 集計 ----------

    def usage_count(self, vocab_id: int) -> int:
        """その語彙を作文で実際に使えた回数。"""
        with self._connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM writing_vocab WHERE vocab_id = ? AND used = 1", (vocab_id,)
            ).fetchone()[0]

    def written_vocab(self) -> list[tuple[int, str]]:
        """作文で指定したことのある語彙 (id, 語彙)。一覧の絞り込み用。"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT vocab_id, word FROM writing_vocab ORDER BY word"
            ).fetchall()
        return [(r[0], r[1]) for r in rows]

    def count_writings(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM writings").fetchone()[0]

    def count_writing_days(self) -> int:
        with self._connect() as conn:
            return conn.execute(
                "SELECT COUNT(DISTINCT date(created_at)) FROM writings"
            ).fetchone()[0]

    def count_writings_on(self, day: date) -> int:
        with self._connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM writings WHERE date(created_at) = ?", (day.isoformat(),)
            ).fetchone()[0]

    # ---------- 使う語彙の選択 ----------

    def candidate_ids(self, mode: str) -> list[int]:
        """語彙の選び方ごとの候補(苦手 / 学習中 / 未学習 / それ以外は全語彙)。"""
        return ReviewRepository(self.db_path).ids_in_group(mode)

    def pick_vocab(self, mode: str, count: int, exclude: set[int] = frozenset()) -> list[int]:
        """作文で使う語彙を count 個選ぶ。

        おまかせは「苦手 → 学習中 → 未学習」から 1 つずつ順番に選ぶ。
        候補が足りないときは、登録済みの全語彙から補う。exclude の語彙はなるべく避ける。
        """
        modes = (
            [P.VOCAB_WEAK, P.VOCAB_LEARNING, P.VOCAB_NEW] if mode == P.AUTO else [mode]
        )
        pools = []
        for m in modes:
            ids = [i for i in self.candidate_ids(m) if i not in exclude]
            random.shuffle(ids)
            pools.append(ids)

        picked: list[int] = []
        while len(picked) < count and any(pools):
            for pool in pools:
                while pool and pool[0] in picked:
                    pool.pop(0)
                if pool and len(picked) < count:
                    picked.append(pool.pop(0))

        if len(picked) < count:  # 候補が足りなければ全語彙から補う
            rest = [i for i in self.candidate_ids("all") if i not in picked and i not in exclude]
            random.shuffle(rest)
            picked += rest[: count - len(picked)]
        if len(picked) < count:  # それでも足りなければ exclude も使う
            rest = [i for i in self.candidate_ids("all") if i not in picked]
            random.shuffle(rest)
            picked += rest[: count - len(picked)]
        return picked
