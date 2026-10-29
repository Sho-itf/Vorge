"""語彙 CSV の読み込み(検証つき)と書き出しを担当するモジュール。

読み込みは「解析・検証」だけを行い、DB には保存しない。
保存はユーザーが結果を確認してから VocabRepository.import_vocabs() で行う。
"""

import csv
import io
from dataclasses import dataclass, field

from vorge.vocab.models import (
    CSV_COLUMNS,
    FIELD_LABELS,
    REQUIRED_COLUMNS,
    Vocab,
    parse_difficulty,
)

# 読み込みを試す文字コードの順番。utf-8-sig は BOM 有り・無しの両方を読める。
# cp932 は Windows の Excel で保存した「CSV(コンマ区切り)」(Shift_JIS)用。
ENCODINGS = [("utf-8-sig", "UTF-8"), ("cp932", "Shift_JIS")]


class CsvFormatError(Exception):
    """ファイル全体が読めない(文字コード不明・必須列なしなど)ときのエラー。"""


@dataclass
class RowError:
    line: int  # CSV ファイル上の行番号(ヘッダーが 1 行目)
    messages: list[str]
    word: str = ""


@dataclass
class ParsedRow:
    line: int
    vocab: Vocab


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)  # 取り込める行
    errors: list[RowError] = field(default_factory=list)  # 取り込めない行
    warnings: list[str] = field(default_factory=list)  # ファイル全体への注意
    encoding: str = ""
    total_rows: int = 0  # 空行を除いたデータ行の数


def decode_bytes(data: bytes) -> tuple[str, str]:
    """バイト列を文字列に変換し、(文字列, 文字コード名) を返す。"""
    for codec, label in ENCODINGS:
        try:
            return data.decode(codec), label
        except UnicodeDecodeError:
            continue
    raise CsvFormatError(
        "文字コードを判別できませんでした。UTF-8 で保存し直してから読み込んでください。"
    )


def parse_csv(data: bytes) -> ParseResult:
    """CSV のバイト列を解析・検証する。"""
    text, encoding = decode_bytes(data)
    if not text.strip():
        raise CsvFormatError("ファイルが空です。")

    reader = csv.reader(io.StringIO(text, newline=""))
    try:
        raw_header = next(reader)
    except csv.Error as e:
        raise CsvFormatError(f"ヘッダー行を読み込めませんでした: {e}") from None

    header = [h.strip().lower() for h in raw_header]
    result = ParseResult(encoding=encoding)

    duplicated = sorted({h for h in header if h and header.count(h) > 1})
    if duplicated:
        raise CsvFormatError(f"ヘッダーに同じ列名が重複しています: {', '.join(duplicated)}")

    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        labels = "、".join(f"{c}({FIELD_LABELS[c]})" for c in missing)
        raise CsvFormatError(
            f"必須の列 {labels} がありません。1 行目に列名(ヘッダー)があるか確認してください。"
            f"\n読み取った列名: {', '.join(h for h in header if h) or '(なし)'}"
        )

    unknown = [h for h in header if h and h not in CSV_COLUMNS]
    if unknown:
        result.warnings.append(f"次の列は使われないため無視します: {', '.join(unknown)}")

    seen_ids: dict[int, int] = {}  # id → 最初に出てきた行番号
    prev_line = reader.line_num
    while True:
        try:
            values = next(reader)
        except StopIteration:
            break
        except csv.Error as e:
            result.errors.append(RowError(prev_line + 1, [f"CSV の形式が壊れています: {e}"]))
            break

        # 1 件のデータが複数行にまたがる(セル内改行)こともあるので、開始行を記録する
        line = prev_line + 1
        prev_line = reader.line_num

        if not any(v.strip() for v in values):
            continue  # 空行は無視
        result.total_rows += 1

        row_error = _parse_row(values, header, line, seen_ids)
        if isinstance(row_error, RowError):
            result.errors.append(row_error)
        else:
            result.rows.append(ParsedRow(line, row_error))

    return result


def _parse_row(
    values: list[str], header: list[str], line: int, seen_ids: dict[int, int]
) -> Vocab | RowError:
    """1 行分を Vocab に変換する。問題があれば RowError を返す。"""
    messages: list[str] = []
    if len(values) > len(header):
        messages.append(
            f"列の数がヘッダーより多くなっています({len(values)}列 / ヘッダー{len(header)}列)。"
            "値にカンマを含む場合は \"…\" で囲んでください。"
        )
    record = {h: (values[i] if i < len(values) else "") for i, h in enumerate(header) if h}

    vocab_id = None
    raw_id = record.get("id", "").strip()
    if raw_id:
        if raw_id.isdigit() and int(raw_id) > 0:
            vocab_id = int(raw_id)
            if vocab_id in seen_ids:
                messages.append(
                    f"ID {vocab_id} がファイル内で重複しています({seen_ids[vocab_id]}行目と同じ)。"
                )
            else:
                seen_ids[vocab_id] = line
        else:
            messages.append(f"ID「{raw_id}」は正の整数ではありません(空欄なら自動採番)。")

    difficulty = 0
    try:
        difficulty = parse_difficulty(record.get("difficulty"))
    except ValueError as e:
        messages.append(str(e))

    vocab = Vocab(
        id=vocab_id,
        difficulty=difficulty,
        **{c: record.get(c, "") for c in CSV_COLUMNS if c not in ("id", "difficulty")},
    ).normalized()

    # 難易度のエラーは上で報告済みなので、重複しないよう除外する
    messages.extend(m for m in vocab.validate() if "難易度" not in m)

    if messages:
        return RowError(line, messages, vocab.word)
    return vocab


@dataclass
class ContentDuplicate:
    """語彙と意味の組み合わせが、登録済みの語彙かファイル内の前の行と同じ行。"""

    line: int
    vocab: Vocab
    existing_id: int | None = None  # 登録済みの語彙と同じ場合、その ID
    first_line: int | None = None  # ファイル内の前の行と同じ場合、その行番号


def find_content_duplicates(
    rows: list[ParsedRow], registered: dict[tuple[str, str], int]
) -> list[ContentDuplicate]:
    """「語彙」と「意味」が両方とも同じ行を探す。

    registered は (語彙, 意味) → 登録済みの ID の辞書。
    同じ語彙でも意味が違えば(多義語・同音異義語)重複とはみなさない。
    """
    seen: dict[tuple[str, str], int] = {}  # (語彙, 意味) → ファイル内で最初に出てきた行番号
    duplicates = []
    for r in rows:
        key = (r.vocab.word, r.vocab.meaning)
        if key in registered:
            duplicates.append(ContentDuplicate(r.line, r.vocab, existing_id=registered[key]))
        elif key in seen:
            duplicates.append(ContentDuplicate(r.line, r.vocab, first_line=seen[key]))
        else:
            seen[key] = r.line
    return duplicates


def template_csv() -> bytes:
    """列名(ヘッダー)だけが入った、新しい語彙を書き込むための CSV。"""
    return export_csv([])


def export_csv(vocabs: list[Vocab]) -> bytes:
    """語彙一覧を UTF-8 with BOM の CSV に変換する(Excel で開いても文字化けしない)。"""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for v in vocabs:
        writer.writerow([getattr(v, c) for c in CSV_COLUMNS])
    return buffer.getvalue().encode("utf-8-sig")
