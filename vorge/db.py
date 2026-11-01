"""SQLite への接続と、テーブルの作成・移行(バージョンアップ)を担当するモジュール。

既存データを消す処理は一切行わない。テーブル構造の変更は MIGRATIONS に「移行処理」を足して行う。
"""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from vorge import backup, config
from vorge.vocab.models import DEFAULT_CATEGORIES
from vorge.writing.prompts import DEFAULT_PROMPTS

# ---------- バージョン 6 までのテーブル(「基準のテーブル構造」) ----------
#   1: vocab, categories
#   2: review_state, study_log(フラッシュカード・学習履歴)
#   3: app_settings, writing_prompts, writings, writing_vocab(作文トレーニング)
#   4: quiz_log(穴埋めクイズ)
#   5: writings に stance / template / sections 列を追加(議論トレーニング)
#   6: quiz_excluded(穴埋めクイズで「おかしい」と報告した例文)
# バージョン 6 までは「無ければ作る」方式で足してきたので、まとめて 1 つの移行処理(_baseline)として扱う。
# バージョン 7 以降は MIGRATIONS に 1 バージョンずつ移行処理を足していく。

# 既存のテーブルに後から追加した列(テーブル名 → [(列名, 型と既定値)])。
# CREATE TABLE IF NOT EXISTS は既存のテーブルを変更しないので、無ければ ALTER TABLE で足す。
BASELINE_ADDED_COLUMNS = {
    "writings": [
        ("stance", "TEXT NOT NULL DEFAULT ''"),
        ("template", "TEXT NOT NULL DEFAULT ''"),
        ("sections", "TEXT NOT NULL DEFAULT ''"),
    ],
}

BASELINE_SQL = """
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
    -- 以下は議論トレーニング用(kind = 'debate' の行だけが使う)
    stance      TEXT NOT NULL DEFAULT '',     -- 立場(pro / con)
    template    TEXT NOT NULL DEFAULT '',     -- 構成の型(prep / rebuttal)
    sections    TEXT NOT NULL DEFAULT '',     -- 欄ごとの文章(JSON)
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

-- 穴埋めクイズで「この問題はおかしい」と報告した例文。以後その例文からは出題しない
CREATE TABLE IF NOT EXISTS quiz_excluded (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    vocab_id   INTEGER NOT NULL REFERENCES vocab(id) ON DELETE CASCADE,
    sentence   TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (vocab_id, sentence)
);
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


# ---------- 移行処理 ----------


def _add_missing_columns(conn: sqlite3.Connection, table: str, columns: list[tuple[str, str]]) -> None:
    """列が無ければ ALTER TABLE で追加する(既存の行は既定値になる)。2 回実行しても安全。"""
    existing = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns:
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _baseline(conn: sqlite3.Connection) -> None:
    """バージョン 6 までのテーブル構造にする(新しい DB でも、古い DB でも同じ結果になる)。"""
    conn.executescript(BASELINE_SQL)
    for table, columns in BASELINE_ADDED_COLUMNS.items():
        _add_missing_columns(conn, table, columns)


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def _v7_trash_and_examples(conn: sqlite3.Connection) -> None:
    """ゴミ箱と、3 本目以降の例文。

    - 語彙の本体を vocab_all に改名し、deleted_at(ゴミ箱に入れた日時)を追加する。
      「vocab」はゴミ箱に入っていない語彙だけを見せるビューにするので、読み取り側の SQL は今までどおり使える。
      書き込み(追加・更新・削除)は vocab_all に対して行う。
      ※ ビューは SELECT * の列を作成時点で固定するので、vocab_all に列を足したらビューも作り直すこと
    - 改名すると、他のテーブルからの参照(REFERENCES vocab)も SQLite が自動で vocab_all に書き換える
    - 作文にも deleted_at を追加(ゴミ箱)
    - 例文 3 本目以降を入れる vocab_examples テーブル(例文 1・2 は今までどおり vocab_all の列)
    """
    if "vocab_all" not in _tables(conn):
        conn.execute("ALTER TABLE vocab RENAME TO vocab_all")
    _add_missing_columns(conn, "vocab_all", [("deleted_at", "TEXT")])
    conn.execute("DROP VIEW IF EXISTS vocab")
    conn.execute("CREATE VIEW vocab AS SELECT * FROM vocab_all WHERE deleted_at IS NULL")
    _add_missing_columns(conn, "writings", [("deleted_at", "TEXT")])
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vocab_examples (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            vocab_id   INTEGER NOT NULL REFERENCES vocab_all(id) ON DELETE CASCADE,
            sentence   TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_examples_vocab ON vocab_examples(vocab_id)")


def _v8_fsrs(conn: sqlite3.Connection) -> None:
    """復習の計算を FSRS に変更。カードの状態(JSON)と「簡単」の回数を保存する列を追加する。

    以前の方式で学習済みの語彙は fsrs_card が空のまま残り、次に回答したときに
    今の復習間隔を引き継いで FSRS のカードに変換される(scheduler.legacy_card)。
    """
    _add_missing_columns(conn, "review_state", [
        ("easy_count", "INTEGER NOT NULL DEFAULT 0"),
        ("fsrs_card", "TEXT NOT NULL DEFAULT ''"),
    ])


def _v9_reading(conn: sqlite3.Connection) -> None:
    """読解トレーニング:読んだ文章(要約つき)と、そこで出会った語(語彙ライブラリへの登録候補)。"""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS reading_notes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT NOT NULL,
            source     TEXT NOT NULL DEFAULT '',
            body       TEXT NOT NULL,
            summary    TEXT NOT NULL DEFAULT '',
            feedback   TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        -- 登録候補の語。文章から拾ったもの(note_id あり)と、言葉だけメモしたもの(note_id なし)
        CREATE TABLE IF NOT EXISTS reading_candidates (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id    INTEGER REFERENCES reading_notes(id) ON DELETE CASCADE,
            word       TEXT NOT NULL,
            sentence   TEXT NOT NULL DEFAULT '',
            source     TEXT NOT NULL DEFAULT '',
            status     TEXT NOT NULL DEFAULT 'pending',   -- pending / registered / ignored
            vocab_id   INTEGER REFERENCES vocab_all(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_candidates_status ON reading_candidates(status);
        """
    )


# (移行後のバージョン, 移行処理)。新しい変更はこのリストの最後に足す
MIGRATIONS: list[tuple[int, Callable[[sqlite3.Connection], None]]] = [
    (6, _baseline),
    (7, _v7_trash_and_examples),
    (8, _v8_fsrs),
    (9, _v9_reading),
]
SCHEMA_VERSION = MIGRATIONS[-1][0]


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection) -> list[int]:
    """まだ適用していない移行処理を、古い順に実行する。適用したバージョンの一覧を返す。"""
    applied = []
    for version, step in MIGRATIONS:
        if version > schema_version(conn):
            step(conn)
            conn.execute(f"PRAGMA user_version = {version}")
            applied.append(version)
    return applied


def _needs_migration(path: Path) -> bool:
    """データの入った DB で、まだ適用していない移行処理があるか。"""
    if not path.exists() or path.stat().st_size == 0:
        return False
    with sqlite3.connect(path) as conn:
        version = schema_version(conn)
    conn.close()
    return version < SCHEMA_VERSION


def init_db(db_path: Path | None = None, auto_backup_before_migration: bool = True) -> None:
    """テーブルを最新の構造にし、初期データを登録する(既存データはそのまま)。

    データの入った DB を移行するときは、念のため先にバックアップを取る。
    """
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    if auto_backup_before_migration and _needs_migration(path):
        backup.create_backup(f"before_v{SCHEMA_VERSION}", path)
    with get_connection(path) as conn:
        migrate(conn)
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
