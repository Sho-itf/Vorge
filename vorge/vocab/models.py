"""語彙データの「形」と入力チェックを定義するモジュール。

画面の入力フォームと CSV インポートの両方がここのチェックを使うので、
ルールを変えたいときはこのファイルだけ直せばよい。
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields, replace
from typing import Any

UNCATEGORIZED = "未分類"

DEFAULT_CATEGORIES = [
    "思考・認識",
    "判断・論理",
    "言語・説明",
    "感情・心理",
    "態度・姿勢",
    "評価・程度",
    "関係・構造",
    "行為・プロセス",
    "価値・性質",
    "社会・集団",
    UNCATEGORIZED,
]

DIFFICULTY_MIN = 1
DIFFICULTY_MAX = 5
DEFAULT_DIFFICULTY = 3

# CSV やフォームで扱う列(この順番で CSV に書き出す)
CSV_COLUMNS = [
    "id",
    "word",
    "reading",
    "meaning",
    "example_1",
    "example_2",
    "nuance",
    "synonyms",
    "antonyms",
    "collocations",
    "category",
    "difficulty",
    "source",
]
REQUIRED_COLUMNS = ["word", "meaning"]

# 画面に表示する日本語の項目名
FIELD_LABELS = {
    "id": "ID",
    "word": "語彙",
    "reading": "読み",
    "meaning": "意味",
    "example_1": "例文1",
    "example_2": "例文2",
    "nuance": "ニュアンス",
    "synonyms": "類義語",
    "antonyms": "対義語",
    "collocations": "コロケーション",
    "category": "カテゴリ",
    "difficulty": "難易度",
    "source": "出典",
}

# 文字列の長さの上限(極端に長い入力でレイアウトが崩れるのを防ぐ)
MAX_WORD_LENGTH = 100
MAX_TEXT_LENGTH = 2000


@dataclass
class Vocab:
    """語彙 1 件分のデータ。"""

    word: str
    meaning: str
    reading: str = ""
    example_1: str = ""
    example_2: str = ""
    nuance: str = ""
    synonyms: str = ""
    antonyms: str = ""
    collocations: str = ""
    category: str = UNCATEGORIZED
    difficulty: int = DEFAULT_DIFFICULTY
    source: str = ""
    id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None
    deleted_at: str | None = None  # ゴミ箱に入れた日時(入っていなければ None)
    # 3 本目以降の例文(別テーブル vocab_examples)。None は「読み込んでいない/変更しない」の意味で、
    # CSV の取り込みで上書きしても、アプリで追加した例文が消えないようにしている
    extra_examples: list[str] | None = None

    @property
    def all_examples(self) -> list[str]:
        """例文をすべて(例文 1・2 と、3 本目以降)。空のものは除く。"""
        return [e for e in (self.example_1, self.example_2, *(self.extra_examples or [])) if e]

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "Vocab":
        """DB の 1 行(sqlite3.Row)や辞書から Vocab を作る。"""
        names = {f.name for f in fields(cls)}
        return cls(**{k: row[k] for k in row.keys() if k in names})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def normalized(self) -> "Vocab":
        """前後の空白を取り除き、空のカテゴリを「未分類」にしたコピーを返す。"""
        cleaned = {
            f.name: getattr(self, f.name).strip()
            for f in fields(self)
            if isinstance(getattr(self, f.name), str)
        }
        result = replace(self, **cleaned)
        if not result.category:
            result.category = UNCATEGORIZED
        if result.extra_examples is not None:
            result.extra_examples = [e.strip() for e in result.extra_examples if e.strip()]
        return result

    def validate(self) -> list[str]:
        """入力の問題点を日本語のメッセージで返す(問題が無ければ空リスト)。"""
        errors = []
        if not self.word.strip():
            errors.append("「語彙」は必須です。")
        elif len(self.word) > MAX_WORD_LENGTH:
            errors.append(f"「語彙」は{MAX_WORD_LENGTH}文字以内で入力してください。")
        if not self.meaning.strip():
            errors.append("「意味」は必須です。")
        if not (
            isinstance(self.difficulty, int)
            and DIFFICULTY_MIN <= self.difficulty <= DIFFICULTY_MAX
        ):
            errors.append(
                f"「難易度」は{DIFFICULTY_MIN}〜{DIFFICULTY_MAX}の整数にしてください。"
            )
        for name in CSV_COLUMNS:
            value = getattr(self, name)
            if isinstance(value, str) and len(value) > MAX_TEXT_LENGTH:
                errors.append(
                    f"「{FIELD_LABELS[name]}」が長すぎます({MAX_TEXT_LENGTH}文字以内)。"
                )
        return errors


def parse_difficulty(value: str | int | None) -> int:
    """難易度の入力値を整数に変換する。空なら既定値(3)。不正なら ValueError。

    Excel で保存すると "3.0" になることがあるので、小数点以下が 0 なら許可する。
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return DEFAULT_DIFFICULTY
    text = str(value).strip()
    try:
        number = float(text)
    except ValueError:
        raise ValueError(f"難易度「{text}」は数値ではありません。") from None
    if not number.is_integer():
        raise ValueError(f"難易度「{text}」は整数ではありません。")
    level = int(number)
    if not DIFFICULTY_MIN <= level <= DIFFICULTY_MAX:
        raise ValueError(
            f"難易度「{text}」は{DIFFICULTY_MIN}〜{DIFFICULTY_MAX}の範囲外です。"
        )
    return level


def split_terms(text: str) -> list[str]:
    """「概観,鳥瞰」や「概観、鳥瞰」のような区切り文字列をリストにする。"""
    normalized = text.replace("、", ",").replace(",", ",")
    return [t.strip() for t in normalized.split(",") if t.strip()]
