"""アプリ全体で使う設定値(ファイルの場所など)をまとめたモジュール。

秘密情報や環境ごとに変えたい値は .env ファイルに書き、ここで読み込む。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# プロジェクトのルートフォルダ(この config.py の 1 つ上の階層)
BASE_DIR = Path(__file__).resolve().parent.parent

# .env があれば環境変数として読み込む(無くてもエラーにならない)
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"


def _resolve(path_str: str) -> Path:
    """相対パスならプロジェクトルート基準の絶対パスに変換する。"""
    path = Path(path_str)
    return path if path.is_absolute() else BASE_DIR / path


DB_PATH = _resolve(os.getenv("VORGE_DB_PATH", "data/vorge.db"))

# 同梱のサンプル語彙CSV
SEED_CSV_PATH = BASE_DIR / "csv" / "vorge_vocab_seed.csv"
