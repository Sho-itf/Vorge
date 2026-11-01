"""SQLite への接続とテーブル作成を担当するモジュール。

ここではテーブルを「無ければ作る」だけで、既存データを消す処理は一切行わない。
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from vorge import config
from vorge.vocab.models import DEFAULT_CATEGORIES
from vorge.writing.prompts import DEFAULT_PROMPTS

# テーブル構造を変えるときにこの数字を上げ、init_db() に移行処理を追加する
#   1: vocab, categories
#   2: review_state, study_log(フラッシュカード・学習履歴)
#   3: app_settings, writing_prompts, writings, writing_vocab(作文トレーニング)
#   4: quiz_log(穴埋めクイズ)
SCHEMA_VERSION = 4

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

-- 語彙ごとの現在の習得状況(1 語彙につき 1 行。まだ学習していない語彙には行が無い)
-- 語彙を削除したときだけ一緒に消える(ON DELETE CASCADE)。CSV の上書きインポートでは消えない。
CREATE TABLE IF NOT EXISTS review_state (
    vocab_id        INTEGER PRIMARY KEY REFERENCES vocab(id) ON DELETE CASCADE,
    interval_days   INTEGER NOT NULL,
    next_review     TEXT NOT NULL,   -- 次回復習日(YYYY-MM-DD)
    review_count    INTEGER NOT NULL DEFAULT 0,
    correct_count   INTEGER NOT NULL DEFAULT 0,
    unsure_count    INTEGER NOT NULL DEFAULT 0,
    wrong_count     INTEGER NOT NULL DEFAULT 0,
    last_result     TEXT NOT NULL,
    last_studied_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_next ON review_state(next_review);

-- 回答のたびに 1 行ずつ追加していく学習履歴
CREATE TABLE IF NOT EXISTS study_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vocab_id      INTEGER NOT NULL REFERENCES vocab(id) ON DELETE CASCADE,
    studied_at    TEXT NOT NULL,     -- 学習日時(YYYY-MM-DD HH:MM:SS)
    mode          TEXT NOT NULL,     -- word_to_meaning / meaning_to_word
    result        TEXT NOT NULL,     -- correct / unsure / wrong(回答結果=自己評価)
    self_rating   INTEGER,           -- 将来の細かい自己評価(1〜5)用。今は未使用
    interval_days INTEGER NOT NULL,
    next_review   TEXT NOT NULL      -- この回答で決まった次回復習日
);
CREATE INDEX IF NOT EXISTS idx_log_vocab ON study_log(vocab_id);
CREATE INDEX IF NOT EXISTS idx_log_studied_at ON study_log(studied_at);

-- アプリの設定(前回選んだ出題条件など)を「名前 → 値」で保存する
CREATE TABLE IF NOT EXISTS app_settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- 作文のお題(kind: daily / explain / opinion)
CREATE TABLE IF NOT EXISTS writing_prompts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    text       TEXT NOT NULL,
    active     INTEGER NOT NULL DEFAULT 1,   -- 0 なら出題しない
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 書いた作文。お題の文面は書いた時点のものを保存する(お題を編集・削除しても残る)
CREATE TABLE IF NOT EXISTS writings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id   INTEGER REFERENCES writing_prompts(id) ON DELETE SET NULL,
    prompt_text TEXT NOT NULL,
    kind        TEXT NOT NULL,
    min_chars   INTEGER NOT NULL,
    max_chars   INTEGER NOT NULL,
    body        TEXT NOT NULL,
    char_count  INTEGER NOT NULL,
    feedback    TEXT NOT NULL DEFAULT '',     -- 添削結果のメモ
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_writings_created_at ON writings(created_at);

-- 作文で使うよう指定された語彙(used: 本文で実際に使えたか)
-- 語彙を削除するとこの対応だけが消え、作文そのものは残る
CREATE TABLE IF NOT EXISTS writing_vocab (
    writing_id INTEGER NOT NULL REFERENCES writings(id) ON DELETE CASCADE,
    vocab_id   INTEGER NOT NULL REFERENCES vocab(id) ON DELETE CASCADE,
    word       TEXT NOT NULL,                 -- 書いた時点の語彙(表示用)
    used       INTEGER NOT NULL,
    PRIMARY KEY (writing_id, vocab_id)
);
CREATE INDEX IF NOT EXISTS idx_writing_vocab_vocab ON writing_vocab(vocab_id);

-- 穴埋めクイズの回答記録。フラッシュカードの復習日(review_state)には影響させない
CREATE TABLE IF NOT EXISTS quiz_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vocab_id    INTEGER NOT NULL REFERENCES vocab(id) ON DELETE CASCADE,
    answered_at TEXT NOT NULL,
    format      TEXT NOT NULL,     -- choice(4択) / input(入力式)
    correct     INTEGER NOT NULL,
    answer      TEXT NOT NULL      -- 選んだ・入力した答え
);
CREATE INDEX IF NOT EXISTS idx_quiz_vocab ON quiz_log(vocab_id);
CREATE INDEX IF NOT EXISTS idx_quiz_answered_at ON quiz_log(answered_at);
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
        # 作文のお題の初期セット。一度だけ登録する(ユーザーが削除したお題を復活させないため)
        seeded = conn.execute(
            "SELECT 1 FROM app_settings WHERE key = 'writing_prompts_seeded'"
        ).fetchone()
        if not seeded:
            conn.executemany(
                "INSERT INTO writing_prompts (kind, text) VALUES (?, ?)",
                [(kind, text) for kind, texts in DEFAULT_PROMPTS.items() for text in texts],
            )
            conn.execute(
                "INSERT INTO app_settings (key, value) VALUES ('writing_prompts_seeded', '1')"
            )
        current = conn.execute("PRAGMA user_version").fetchone()[0]
        if current < SCHEMA_VERSION:
            # 1 → 2 → 3 → 4 は新しいテーブルの追加だけなので、上の CREATE TABLE IF NOT EXISTS で完了。
            # 既存の列を変えるような変更が必要になったら、ここに移行処理(ALTER TABLE など)を書く
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
