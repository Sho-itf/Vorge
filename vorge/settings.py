"""アプリの設定(前回選んだ条件など)を DB に保存・読み込みする。

ブラウザを閉じても設定が残るよう、session_state ではなく app_settings テーブルに保存する。
値は JSON 文字列にして保存するので、数値・文字列・リストなどをそのまま扱える。
"""

import json
from pathlib import Path
from typing import Any

from vorge.db import get_connection


def get_setting(key: str, default: Any = None, db_path: Path | None = None) -> Any:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return default


def set_setting(key: str, value: Any, db_path: Path | None = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, json.dumps(value, ensure_ascii=False)),
        )
