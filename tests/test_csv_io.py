import pytest

from vorge import config
from vorge.vocab.csv_io import CsvFormatError, export_csv, parse_csv
from vorge.vocab.models import Vocab

HEADER = "id,word,reading,meaning,category,difficulty\n"


def test_reads_utf8_with_and_without_bom():
    text = HEADER + "1,俯瞰,ふかん,全体を見渡すこと,思考・認識,3\n"
    for data in (text.encode("utf-8"), text.encode("utf-8-sig")):
        result = parse_csv(data)
        assert result.encoding == "UTF-8"
        assert result.rows[0].vocab.word == "俯瞰"
        assert not result.errors


def test_reads_shift_jis():
    text = HEADER + "1,俯瞰,ふかん,全体を見渡すこと,思考・認識,3\n"
    result = parse_csv(text.encode("cp932"))
    assert result.encoding == "Shift_JIS"
    assert result.rows[0].vocab.word == "俯瞰"


def test_missing_required_column():
    with pytest.raises(CsvFormatError, match="meaning"):
        parse_csv("id,word\n1,俯瞰\n".encode())


def test_empty_file():
    with pytest.raises(CsvFormatError):
        parse_csv(b"")


def test_row_errors_have_line_numbers():
    text = (
        HEADER
        + "1,俯瞰,ふかん,全体を見渡すこと,,3\n"  # 2行目: OK
        + "2,,どうさつ,本質を見抜く,,3\n"  # 3行目: word が空
        + "x,齟齬,そご,食い違い,,9\n"  # 4行目: id と難易度が不正
        + "1,重複,ちょうふく,重なる,,2\n"  # 5行目: ID がファイル内で重複
    )
    result = parse_csv(text.encode())
    assert [r.line for r in result.rows] == [2]
    errors = {e.line: e.messages for e in result.errors}
    assert set(errors) == {3, 4, 5}
    assert any("語彙" in m for m in errors[3])
    assert len(errors[4]) == 2
    assert any("重複" in m for m in errors[5])


def test_line_numbers_with_multiline_cell():
    text = HEADER + '1,俯瞰,ふかん,"1行目\n2行目",,3\n2,,x,y,,3\n'
    result = parse_csv(text.encode())
    assert result.rows[0].vocab.meaning == "1行目\n2行目"
    assert result.errors[0].line == 4  # セル内改行の分だけ行番号が進む


def test_optional_columns_and_defaults():
    result = parse_csv("word,meaning,extra\n俯瞰,全体を見渡す,無視\n\n".encode())
    v = result.rows[0].vocab
    assert v.id is None and v.difficulty == 3 and v.category == "未分類"
    assert result.warnings  # extra 列は無視される旨の警告
    assert result.total_rows == 1  # 空行は数えない


def test_too_many_columns_is_error():
    result = parse_csv("word,meaning\n概観,鳥瞰,余分\n".encode())
    assert result.errors and result.errors[0].line == 2


def test_export_roundtrip():
    vocabs = [
        Vocab(id=1, word="俯瞰", meaning="全体, を見渡す", synonyms="概観,鳥瞰", difficulty=3),
        Vocab(id=2, word="洞察", meaning='"本質"を見抜く', difficulty=4),
    ]
    data = export_csv(vocabs)
    assert data.startswith(b"\xef\xbb\xbf")  # BOM 付き
    result = parse_csv(data)
    assert not result.errors
    assert [r.vocab.meaning for r in result.rows] == ["全体, を見渡す", '"本質"を見抜く']
    assert result.rows[0].vocab.synonyms == "概観,鳥瞰"


def test_seed_csv_is_valid():
    result = parse_csv(config.SEED_CSV_PATH.read_bytes())
    assert not result.errors
    assert len(result.rows) == 99
