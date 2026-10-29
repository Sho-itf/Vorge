"""SQLite への接続とテーブル作成を担当するモジュール。

ここではテーブルを「無ければ作る」だけで、既存データを消す処理は一切行わない。
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from vorge import config
from vorge.vocab.models import DEFAULT_CATEGORIES

# テーブル構造を変えるときにこの数字を上げ、init_db() に移行処理を追加する
SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    name       TEXT PRIMARY KEY,
    sort_order INTEGER NOT NULL DEFAULT 100,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS vocab (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    word         TEXT NOT NULL,
    reading      TEXT NOT NULL DEFAULT '',
    meaning      TEXT NOT NULL,
    example_1    TEXT NOT NULL DEFAULT '',
    example_2    TEXT NOT NULL DEFAULT '',
    nuance       TEXT NOT NULL DEFAULT '',
    synonyms     TEXT NOT NULL DEFAULT '',
    antonyms     TEXT NOT NULL DEFAULT '',
    collocations TEXT NOT NULL DEFAULT '',
    category     TEXT NOT NULL DEFAULT '未分類',
    difficulty   INTEGER NOT NULL DEFAULT 3 CHECK (difficulty BETWEEN 1 AND 5),
    source       TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_vocab_word ON vocab(word);
CREATE INDEX IF NOT EXISTS idx_vocab_category ON vocab(category);
CREATE INDEX IF NOT EXISTS idx_vocab_created_at ON vocab(created_at);
"""


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    """DB 接続を開き、ブロックを抜けるときに自動で保存(commit)して閉じる。

    使い方:
        with get_connection() as conn:
            conn.execute(...)

    途中でエラーが起きた場合は rollback され、中途半端な状態で保存されない。
    """
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row  # row["word"] のように列名で値を取り出せる
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    """テーブルが無ければ作成し、初期カテゴリを登録する(既存データはそのまま)。"""
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with get_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executemany(
            "INSERT OR IGNORE INTO categories (name, sort_order) VALUES (?, ?)",
            [(name, i) for i, name in enumerate(DEFAULT_CATEGORIES)],
        )
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current < SCHEMA_VERSION:
            # 将来ここにバージョンごとの移行処理(ALTER TABLE など)を書く
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
