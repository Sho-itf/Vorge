"""語彙データの DB 操作(追加・検索・更新・削除・一括取り込み)をまとめたモジュール。

画面側は SQL を書かず、必ずこのクラスのメソッドを通して DB を操作する。
"""

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from vorge.db import get_connection
from vorge.vocab.models import CSV_COLUMNS, UNCATEGORIZED, Vocab

# id 以外の、ユーザーが編集できる列
_EDITABLE = [c for c in CSV_COLUMNS if c != "id"]

# キーワード検索の対象にする列
_SEARCH_COLUMNS = [
    "word",
    "reading",
    "meaning",
    "example_1",
    "example_2",
    "nuance",
    "synonyms",
    "antonyms",
    "collocations",
    "source",
]

# 並び順の選択肢(画面の表示名 → SQL の ORDER BY)
SORT_OPTIONS = {
    "ID順": "id ASC",
    "読み順": "CASE WHEN reading = '' THEN word ELSE reading END ASC, id ASC",
    "新しい順": "created_at DESC, id DESC",
    "難易度(易→難)": "difficulty ASC, id ASC",
    "難易度(難→易)": "difficulty DESC, id ASC",
}


@dataclass
class ImportResult:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0


def _escape_like(text: str) -> str:
    """LIKE 検索で % や _ を普通の文字として扱うためにエスケープする。"""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class VocabRepository:
    """語彙テーブルを操作するクラス。db_path を変えるとテスト用 DB も使える。"""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path

    def _connect(self):
        return get_connection(self.db_path)

    # ---------- 1 件ずつの操作 ----------

    def get(self, vocab_id: int) -> Vocab | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM vocab WHERE id = ?", (vocab_id,)).fetchone()
        return Vocab.from_row(row) if row else None

    def add(self, vocab: Vocab) -> int:
        """語彙を追加し、採番された id を返す。vocab.id が指定されていればその id で登録。"""
        with self._connect() as conn:
            return self._insert(conn, vocab.normalized())

    def update(self, vocab: Vocab) -> bool:
        """id が一致する語彙を更新する。対象が無ければ False。"""
        if vocab.id is None:
            raise ValueError("更新する語彙の id が指定されていません。")
        with self._connect() as conn:
            return self._update(conn, vocab.normalized())

    def delete(self, vocab_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM vocab WHERE id = ?", (vocab_id,))
            return cur.rowcount > 0

    # ---------- 検索・集計 ----------

    def search(
        self,
        keyword: str = "",
        categories: list[str] | None = None,
        difficulty_range: tuple[int, int] = (1, 5),
        sort: str = "ID順",
    ) -> list[Vocab]:
        """条件に合う語彙を返す。条件は AND で組み合わさる。

        keyword はスペース区切りで複数指定でき、すべてを含む語彙が見つかる。
        """
        where = ["difficulty BETWEEN ? AND ?"]
        params: list = [difficulty_range[0], difficulty_range[1]]

        for term in keyword.split():
            like = f"%{_escape_like(term)}%"
            ors = " OR ".join(f"{col} LIKE ? ESCAPE '\\'" for col in _SEARCH_COLUMNS)
            where.append(f"({ors})")
            params.extend([like] * len(_SEARCH_COLUMNS))

        if categories:
            placeholders = ",".join("?" * len(categories))
            where.append(f"category IN ({placeholders})")
            params.extend(categories)

        order = SORT_OPTIONS.get(sort, SORT_OPTIONS["ID順"])
        sql = f"SELECT * FROM vocab WHERE {' AND '.join(where)} ORDER BY {order}"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [Vocab.from_row(r) for r in rows]

    def list_all(self) -> list[Vocab]:
        return self.search()

    def count(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) FROM vocab").fetchone()[0]

    def count_added_on(self, day: date) -> int:
        """指定日に登録された語彙の数。"""
        with self._connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM vocab WHERE date(created_at) = ?",
                (day.isoformat(),),
            ).fetchone()[0]

    def recent(self, limit: int = 5) -> list[Vocab]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM vocab ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Vocab.from_row(r) for r in rows]

    def existing_ids(self, ids: list[int]) -> set[int]:
        """指定した id のうち、DB に既に存在するものを返す。"""
        if not ids:
            return set()
        found: set[int] = set()
        with self._connect() as conn:
            # SQLite の変数上限を超えないよう 500 件ずつ問い合わせる
            for i in range(0, len(ids), 500):
                chunk = ids[i : i + 500]
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT id FROM vocab WHERE id IN ({placeholders})", chunk
                ).fetchall()
                found.update(r["id"] for r in rows)
        return found

    def get_many(self, ids: list[int]) -> dict[int, Vocab]:
        """id → Vocab の辞書を返す(存在しない id は含まれない)。"""
        result: dict[int, Vocab] = {}
        with self._connect() as conn:
            for i in range(0, len(ids), 500):
                chunk = ids[i : i + 500]
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT * FROM vocab WHERE id IN ({placeholders})", chunk
                ).fetchall()
                result.update({r["id"]: Vocab.from_row(r) for r in rows})
        return result

    # ---------- カテゴリ ----------

    def list_categories(self) -> list[str]:
        """カテゴリ候補の一覧(登録順)。語彙で使われているものも含める。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name FROM categories
                UNION
                SELECT DISTINCT category FROM vocab
                """
            ).fetchall()
            order = {
                r["name"]: (r["sort_order"], r["created_at"])
                for r in conn.execute("SELECT * FROM categories")
            }
        names = [r[0] for r in rows]
        # 「未分類」は常に最後に表示する
        return sorted(
            names,
            key=lambda n: (n == UNCATEGORIZED, order.get(n, (10**9, "")), n),
        )

    def add_category(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("カテゴリ名を入力してください。")
        with self._connect() as conn:
            self._ensure_category(conn, name)

    # ---------- CSV からの一括取り込み ----------

    def import_vocabs(self, vocabs: list[Vocab], overwrite: bool = False) -> ImportResult:
        """複数の語彙をまとめて登録する(1 つのトランザクション)。

        - id が無い / DB に無い id → 新規追加
        - id が DB に既にある → overwrite=True なら更新、False ならスキップ

        更新は UPDATE 文で行い、行を削除しないので、将来の学習履歴(vocab_id で
        紐づく別テーブル)が消えることはない。
        途中でエラーが起きた場合は全件取り消される。
        """
        result = ImportResult()
        with self._connect() as conn:
            for vocab in vocabs:
                vocab = vocab.normalized()
                exists = vocab.id is not None and conn.execute(
                    "SELECT 1 FROM vocab WHERE id = ?", (vocab.id,)
                ).fetchone()
                if not exists:
                    self._insert(conn, vocab)
                    result.inserted += 1
                elif overwrite:
                    self._update(conn, vocab)
                    result.updated += 1
                else:
                    result.skipped += 1
        return result

    # ---------- 内部用 ----------

    @staticmethod
    def _ensure_category(conn: sqlite3.Connection, name: str) -> None:
        conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))

    def _insert(self, conn: sqlite3.Connection, vocab: Vocab) -> int:
        self._ensure_category(conn, vocab.category)
        columns = list(_EDITABLE)
        values = [getattr(vocab, c) for c in columns]
        if vocab.id is not None:
            columns.insert(0, "id")
            values.insert(0, vocab.id)
        placeholders = ",".join("?" * len(columns))
        cur = conn.execute(
            f"INSERT INTO vocab ({','.join(columns)}) VALUES ({placeholders})", values
        )
        return cur.lastrowid

    def _update(self, conn: sqlite3.Connection, vocab: Vocab) -> bool:
        self._ensure_category(conn, vocab.category)
        assignments = ", ".join(f"{c} = ?" for c in _EDITABLE)
        values = [getattr(vocab, c) for c in _EDITABLE]
        cur = conn.execute(
            f"UPDATE vocab SET {assignments}, updated_at = datetime('now', 'localtime') "
            "WHERE id = ?",
            [*values, vocab.id],
        )
        return cur.rowcount > 0
