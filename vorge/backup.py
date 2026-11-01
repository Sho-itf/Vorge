"""DB のバックアップ・復元と、全データの書き出し・読み込み。

- 自動バックアップ:アプリ起動時に 1 日 1 回、backups フォルダにコピーし、直近 KEEP_DAYS 日分を残す
- 手動バックアップ:データ管理画面のボタンから、いつでも作れる
- 復元:バックアップから戻す前に、今の状態も必ずバックアップしてから置き換える
- 全データの書き出し(JSON):語彙だけでなく学習記録・作文なども含めて 1 ファイルにする

ファイルのコピーには SQLite のバックアップ機能(Connection.backup)を使う。
アプリが DB を使っている最中でも、壊れていない一貫したコピーが取れる。
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from vorge import config, timeutil

KEEP_DAYS = 14
AUTO_PREFIX = "auto_"
EXPORT_FORMAT = "vorge-full-export"


def backup_dir(db_path: Path | None = None) -> Path:
    """バックアップの保存先(DB と同じフォルダの backups)。"""
    return Path(db_path or config.DB_PATH).parent / "backups"


def _copy_db(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(src) as source, sqlite3.connect(dest) as target:
        source.backup(target)
    # with を抜けても close はされないので明示的に閉じる(Windows でファイルが掴まれたままにならないように)
    source.close()
    target.close()


def create_backup(label: str = "manual", db_path: Path | None = None) -> Path:
    """今の DB をバックアップする。ファイル名は「ラベル_日時.db」。"""
    src = Path(db_path or config.DB_PATH)
    dest = backup_dir(src) / f"{label}_{datetime.now():%Y%m%d_%H%M%S}.db"
    _copy_db(src, dest)
    return dest


def auto_backup(db_path: Path | None = None, keep: int = KEEP_DAYS) -> Path | None:
    """今日の自動バックアップがまだ無ければ作り、古い自動バックアップを消す。作ったファイルを返す。

    消すのは自動バックアップ(auto_ で始まるファイル)だけで、手動や復元前のバックアップは残す。
    """
    src = Path(db_path or config.DB_PATH)
    if not src.exists():
        return None
    folder = backup_dir(src)
    name = f"{AUTO_PREFIX}{timeutil.today():%Y%m%d}.db"
    created = None
    if not (folder / name).exists():
        created = folder / name
        _copy_db(src, created)
    autos = sorted(folder.glob(f"{AUTO_PREFIX}*.db"), reverse=True)
    for old in autos[keep:]:
        old.unlink()
    return created


def list_backups(db_path: Path | None = None) -> list[Path]:
    """バックアップの一覧(新しい順)。"""
    folder = backup_dir(db_path)
    if not folder.exists():
        return []
    return sorted(folder.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)


def restore_backup(backup: Path, db_path: Path | None = None) -> Path:
    """バックアップから DB を元に戻す。戻す前の状態は before_restore_… として保存し、そのパスを返す。"""
    db = Path(db_path or config.DB_PATH)
    if not backup.exists():
        raise FileNotFoundError(f"バックアップが見つかりません: {backup}")
    safety = create_backup("before_restore", db)
    _copy_db(backup, db)
    return safety


# ---------- 全データの書き出し・読み込み(JSON) ----------

# 古い書き出しのテーブル名 → 今のテーブル名
TABLE_ALIASES = {"vocab": "vocab_all"}

# 読み込むときの順番(参照される側のテーブルを先に入れる)
TABLE_ORDER = [
    "categories",
    "app_settings",
    "vocab",  # 古いバージョン(ゴミ箱導入前)の書き出しでの語彙テーブル名
    "vocab_all",
    "vocab_examples",
    "review_state",
    "study_log",
    "writing_prompts",
    "writings",
    "writing_vocab",
    "quiz_log",
    "quiz_excluded",
    "reading_notes",
    "reading_candidates",
]


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def export_all(db_path: Path | None = None) -> bytes:
    """全テーブルの内容を JSON にする(ゴミ箱の中身も含む)。"""
    with sqlite3.connect(Path(db_path or config.DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        existing = _tables(conn)
        data = {
            "format": EXPORT_FORMAT,
            "schema_version": conn.execute("PRAGMA user_version").fetchone()[0],
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "tables": {
                t: [dict(r) for r in conn.execute(f"SELECT * FROM {t}")]
                for t in TABLE_ORDER if t in existing
            },
        }
    conn.close()
    return json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")


def import_all(raw: bytes, db_path: Path | None = None) -> Path:
    """export_all で書き出した JSON から、全データを置き換える。置き換える前の状態のバックアップを返す。

    新しい DB を一時ファイルに作ってから中身を入れ、最後に今の DB と入れ替える。
    途中で失敗しても、今の DB は変わらない。
    """
    from vorge.db import init_db  # db.py もこのモジュールを使うので、循環を避けるためここで読む

    data = json.loads(raw.decode("utf-8"))
    if data.get("format") != EXPORT_FORMAT:
        raise ValueError("Vorge の全データ書き出しファイルではありません。")

    db = Path(db_path or config.DB_PATH)
    temp = db.with_name(db.name + ".importing")
    if temp.exists():
        temp.unlink()
    init_db(temp, auto_backup_before_migration=False)
    with sqlite3.connect(temp) as conn:
        # 初期データ(お題・カテゴリ・設定)は、書き出しファイルの内容で置き換える
        for table in ("writing_prompts", "categories", "app_settings"):
            conn.execute(f"DELETE FROM {table}")
        existing = _tables(conn)
        for name in TABLE_ORDER:
            rows = data["tables"].get(name, [])
            table = TABLE_ALIASES.get(name, name) if TABLE_ALIASES.get(name) in existing else name
            if table not in existing or not rows:
                continue
            columns = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            for row in rows:
                cols = [c for c in row if c in columns]  # 古い書き出しにも新しい書き出しにも対応
                conn.execute(
                    f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    [row[c] for c in cols],
                )
        conn.commit()
    conn.close()

    safety = create_backup("before_import", db)
    _copy_db(temp, db)
    temp.unlink()
    return safety
