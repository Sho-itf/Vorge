import sqlite3

import pytest

from vorge.db import SCHEMA_VERSION, init_db
from vorge.debate import checker
from vorge.debate.templates import (
    KIND_DEBATE,
    PREP,
    REBUTTAL,
    STANCE_CON,
    STANCE_PRO,
    opposite,
)
from vorge.vocab.models import Vocab
from vorge.writing import prompts as P
from vorge.writing.repository import WritingRepository, WritingWord

SECTIONS = {
    "claim": "私はリモートワークに賛成だ。",
    "reason1": "第一に、通勤時間がなくなる。例えば往復2時間かかる人なら、その時間を学習に使える。",
    "reason2": "第二に、家庭と仕事を両立しやすくなるからだ。",
    "counter": "確かに、対面でないと連携が弱まるという論拠もある。",
    "rebuttal": "しかし、週に一度の出社日を設ければその問題は補える。",
    "conclusion": "したがって、リモートワークは広げるべきだ。",
}


@pytest.fixture
def writing(repo):
    return WritingRepository(repo.db_path)


# ---------- 型・チェック ----------


def test_templates():
    assert [s.label for s in PREP.sections] == ["主張", "理由", "具体例", "結論"]
    assert REBUTTAL.min_chars == sum(s.min_chars for s in REBUTTAL.sections)
    assert opposite(STANCE_PRO) == STANCE_CON and opposite(STANCE_CON) == STANCE_PRO


def test_compose_skips_empty_sections():
    text = checker.compose(PREP, {"point": "主張です。", "reason": "", "conclusion": "結論です。"})
    assert text == "主張です。\n結論です。"


def test_check_full_rebuttal():
    result = checker.check(REBUTTAL, SECTIONS, [("論拠", "ろんきょ"), ("反駁", "はんばく")])
    assert result.empty_sections == []
    assert result.vocab_used == {"論拠": True, "反駁": False}
    # 根拠1は「例えば」「2時間」があるが、根拠2には具体例が無い
    assert result.missing_evidence == ["根拠2"]
    assert result.connectors["譲歩する"] == ["確かに"]
    assert result.connectors["逆接で返す"] == ["しかし"]
    assert "したがって" in result.connectors["結論を示す"]
    assert "からだ" in result.connectors["理由を示す"]


def test_check_reports_empty_sections():
    result = checker.check(PREP, {"point": "主張"}, [])
    assert result.empty_sections == ["理由", "具体例", "結論"]


@pytest.mark.parametrize("text, expected", [
    ("例えば駅前の店では", True),
    ("利用者は3割増えた", True),
    ("利用者は３割増えた", True),  # 全角数字
    ("なんとなくそう思う", False),
])
def test_has_evidence(text, expected):
    assert checker.has_evidence(text) is expected


def test_review_prompt_contains_sections_and_counterargument_request():
    text = checker.build_review_prompt("お題X", STANCE_CON, REBUTTAL, [("論拠", "よりどころ")], SECTIONS)
    assert "お題X" in text and "否定側" in text and "反論つき" in text
    assert "【再反論】しかし" in text and "論拠:よりどころ" in text
    assert "もっとも強い反論" in text


# ---------- 保存・一覧 ----------


def test_save_and_list_debate(repo, writing):
    vid = repo.add(Vocab(word="論拠", meaning="よりどころ", category="論理・議論"))
    prompt = writing.random_prompt(P.KIND_OPINION)
    body = checker.compose(REBUTTAL, SECTIONS)
    wid = writing.save_debate(
        prompt.id, prompt.text, STANCE_PRO, "rebuttal", SECTIONS, body, len(body),
        REBUTTAL.min_chars, REBUTTAL.max_chars, [WritingWord(vid, "論拠", True)],
    )
    w = writing.get_writing(wid)
    assert w.kind == KIND_DEBATE and w.stance == STANCE_PRO and w.template == "rebuttal"
    assert w.section_texts == SECTIONS
    assert [x.id for x in writing.list_writings(kind=KIND_DEBATE)] == [wid]
    assert writing.list_writings(kind=P.KIND_OPINION) == []
    assert writing.usage_count(vid) == 1


def test_save_debate_with_custom_topic(writing):
    wid = writing.save_debate(None, "自分のお題", STANCE_CON, "prep", {"point": "a"}, "a", 1,
                              PREP.min_chars, PREP.max_chars, [])
    w = writing.get_writing(wid)
    assert w.prompt_id is None and w.prompt_text == "自分のお題"


def test_pick_vocab_logic_prefers_logic_categories(repo, writing):
    logic = repo.add(Vocab(word="論拠", meaning="m", category="論理・議論"))
    judge = repo.add(Vocab(word="妥当", meaning="m", category="判断・論理"))
    repo.add(Vocab(word="葛藤", meaning="m", category="感情・心理"))
    assert set(writing.pick_vocab(P.VOCAB_LOGIC, 2)) == {logic, judge}
    assert len(writing.pick_vocab(P.VOCAB_LOGIC, 3)) == 3  # 足りない分は他から補う


# ---------- 古い DB の移行 ----------


def test_migration_adds_debate_columns_to_old_db(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE writings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, prompt_id INTEGER, prompt_text TEXT NOT NULL,
            kind TEXT NOT NULL, min_chars INTEGER NOT NULL, max_chars INTEGER NOT NULL,
            body TEXT NOT NULL, char_count INTEGER NOT NULL, feedback TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        INSERT INTO writings (prompt_text, kind, min_chars, max_chars, body, char_count)
        VALUES ('昔のお題', 'daily', 100, 200, '昔の作文', 4);
        PRAGMA user_version = 4;
        """
    )
    conn.close()

    init_db(path)
    init_db(path)  # 2 回目も安全(列を二重に追加しない)
    w = WritingRepository(path).list_writings()[0]
    assert w.body == "昔の作文" and w.stance == "" and w.section_texts == {}
    conn = sqlite3.connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
