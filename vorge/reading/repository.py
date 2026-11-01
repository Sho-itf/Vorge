"""読解トレーニングの DB 操作(読んだ文章・要約・登録候補の語)。"""

from dataclasses import dataclass
from pathlib import Path

from vorge.db import get_connection

STATUS_PENDING = "pending"  # まだ登録していない
STATUS_REGISTERED = "registered"  # 語彙ライブラリに登録した
STATUS_IGNORED = "ignored"  # 登録しないことにした


@dataclass
class ReadingNote:
    id: int
    title: str
    source: str
    body: str
    summary: str
    feedback: str
    created_at: str
    updated_at: str


@dataclass
class WordCandidate:
    id: int
    note_id: int | None
    word: str
    sentence: str
    source: str  # 出典(文章のタイトル・出典、またはメモで入力したもの)
    status: str
    vocab_id: int | None
    created_at: str


class ReadingRepository:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    # ---------- 読んだ文章 ----------

    def add_note(self, title: str, source: str, body: str) -> int:
        if not body.strip():
            raise ValueError("文章を入力してください。")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO reading_notes (title, source, body) VALUES (?, ?, ?)",
                (title.strip() or "(無題)", source.strip(), body.strip()),
            )
            return cur.lastrowid

    def update_summary(self, note_id: int, summary: str, feedback: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE reading_notes SET summary = ?, feedback = ?, "
                "updated_at = datetime('now', 'localtime') WHERE id = ?",
                (summary, feedback, note_id),
            )

    def list_notes(self) -> list[ReadingNote]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM reading_notes ORDER BY created_at DESC, id DESC").fetchall()
        return [ReadingNote(**dict(r)) for r in rows]

    def get_note(self, note_id: int) -> ReadingNote | None:
        return next((n for n in self.list_notes() if n.id == note_id), None)

    def delete_note(self, note_id: int) -> None:
        """文章を削除する(その文章から拾った登録候補も消える。登録済みの語彙は残る)。"""
        with self._connect() as conn:
            conn.execute("DELETE FROM reading_notes WHERE id = ?", (note_id,))

    # ---------- 登録候補の語(出会った言葉) ----------

    def add_candidates(self, note_id: int | None, items: list[tuple[str, str]], source: str = "") -> int:
        """(語, その語が出てくる文) を登録候補に足す。同じ語がまだ候補に残っていれば足さない。"""
        added = 0
        with self._connect() as conn:
            for word, sentence in items:
                exists = conn.execute(
                    "SELECT 1 FROM reading_candidates WHERE word = ? AND status = ?", (word, STATUS_PENDING)
                ).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO reading_candidates (note_id, word, sentence, source) VALUES (?, ?, ?, ?)",
                        (note_id, word.strip(), sentence.strip(), source.strip()),
                    )
                    added += 1
        return added

    def list_candidates(self, status: str = STATUS_PENDING) -> list[WordCandidate]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reading_candidates WHERE status = ? ORDER BY created_at DESC, id DESC", (status,)
            ).fetchall()
        return [WordCandidate(**dict(r)) for r in rows]

    def mark_registered(self, candidate_id: int, vocab_id: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE reading_candidates SET status = ?, vocab_id = ? WHERE id = ?",
                (STATUS_REGISTERED, vocab_id, candidate_id),
            )

    def ignore(self, candidate_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE reading_candidates SET status = ? WHERE id = ?", (STATUS_IGNORED, candidate_id))
