import json
import sqlite3
from datetime import datetime

import pytest

from vorge import backup, daily, db, timeutil
from vorge.db import SCHEMA_VERSION, init_db, migrate
from vorge.flashcard.repository import ReviewRepository
from vorge.quiz.repository import FORMAT_CHOICE, QuizRepository
from vorge.settings import set_setting
from vorge.vocab.models import Vocab
from vorge.vocab.repository import VocabRepository
from vorge.writing import prompts as P
from vorge.writing.repository import WritingRepository


def test_auto_backup_once_per_day_and_keeps_limit(repo):
    db = repo.db_path
    first = backup.auto_backup(db)
    assert first is not None and first.exists()
    assert backup.auto_backup(db) is None  # 同じ日は作らない
    folder = backup.backup_dir(db)
    for i in range(20):  # 古い自動バックアップを並べておく
        (folder / f"{backup.AUTO_PREFIX}2020{i:04d}.db").write_bytes(b"")
    (folder / "manual_20200101_000000.db").write_bytes(b"")
    backup.auto_backup(db, keep=14)
    assert len(list(folder.glob(f"{backup.AUTO_PREFIX}*.db"))) == 14
    assert (folder / "manual_20200101_000000.db").exists()  # 手動バックアップは消さない


def test_restore_backup(repo):
    vid = repo.add(Vocab(word="俯瞰", meaning="m"))
    saved = backup.create_backup("manual", repo.db_path)
    repo.add(Vocab(word="あとから追加", meaning="m"))
    safety = backup.restore_backup(saved, repo.db_path)
    assert [v.id for v in repo.list_all()] == [vid]
    assert safety.exists()  # 戻す前の状態も残っている


def test_export_and_import_all_roundtrip(repo, tmp_path):
    vid = repo.add(Vocab(word="俯瞰", meaning="全体を見渡す"))
    ReviewRepository(repo.db_path).record_answer(vid, "correct", now=datetime(2026, 11, 1, 9))
    writing = WritingRepository(repo.db_path)
    prompt = writing.random_prompt(P.KIND_DAILY)
    writing.save_writing(prompt, 100, 200, "本文", 2, [])
    data = backup.export_all(repo.db_path)
    assert json.loads(data)["schema_version"] == SCHEMA_VERSION

    other = tmp_path / "other.db"
    init_db(other)
    backup.import_all(data, other)
    assert [v.word for v in VocabRepository(other).list_all()] == ["俯瞰"]
    assert ReviewRepository(other).get_state(vid) is not None
    assert len(WritingRepository(other).list_writings()) == 1
    assert len(WritingRepository(other).list_prompts()) == 60  # 二重に登録されない


def test_import_rejects_other_files(repo):
    with pytest.raises(ValueError):
        backup.import_all(b'{"hello": 1}', repo.db_path)


def test_migration_from_v6_keeps_data_and_backs_up(tmp_path):
    """バージョン 6 の DB(ゴミ箱導入前)を、データを保ったまま最新に移行できる。"""
    path = tmp_path / "v6.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    db._baseline(conn)
    conn.execute("PRAGMA user_version = 6")
    conn.execute("INSERT INTO vocab (id, word, meaning) VALUES (1, '俯瞰', '全体を見渡す')")
    conn.execute(
        "INSERT INTO review_state VALUES (1, 3, '2026-11-04', 1, 1, 0, 0, 'correct', '2026-11-01 09:00:00')"
    )
    conn.commit()
    conn.close()

    init_db(path)
    assert list(backup.backup_dir(path).glob(f"before_v{SCHEMA_VERSION}_*.db"))  # 移行前のバックアップ
    repo = VocabRepository(path)
    assert [v.word for v in repo.list_all()] == ["俯瞰"]
    assert ReviewRepository(path).get_state(1) is not None
    repo.delete(1)
    assert repo.list_all() == [] and [v.id for v in repo.list_trash()] == [1]
    with sqlite3.connect(path) as conn:
        conn.row_factory = sqlite3.Row
        assert migrate(conn) == []  # 2 回目は何もしない
        conn.execute("PRAGMA foreign_keys = ON")
        # 参照先が vocab_all に書き換わっている(完全に削除すると学習記録も消える)
        conn.execute("DELETE FROM vocab_all WHERE id = 1")
        assert conn.execute("SELECT COUNT(*) FROM review_state").fetchone()[0] == 0
    conn.close()


def test_logical_day_boundary():
    timeutil.set_day_start_hour(4)
    assert timeutil.logical_date(datetime(2026, 11, 2, 1, 30)).isoformat() == "2026-11-01"
    assert timeutil.logical_date(datetime(2026, 11, 2, 4, 0)).isoformat() == "2026-11-02"
    assert timeutil.sql_date("studied_at") == "date(studied_at, '-4 hours')"
    with pytest.raises(ValueError):
        timeutil.set_day_start_hour(13)


def test_daily_tasks(repo):
    day = datetime(2026, 11, 1, 9)
    vid = repo.add(Vocab(word="俯瞰", meaning="m"))
    tasks = {t.key: t for t in daily.today_tasks(day.date(), repo.db_path)}
    assert tasks["review"].done and not tasks["new"].done and tasks["new"].progress_text == "0 / 10 語"
    ReviewRepository(repo.db_path).record_answer(vid, "correct", now=day)
    QuizRepository(repo.db_path).record(vid, FORMAT_CHOICE, True, "俯瞰", now=day)
    set_setting("daily_new", 1, repo.db_path)
    set_setting("daily_writing", 0, repo.db_path)  # 0 ならメニューから外れる
    tasks = {t.key: t for t in daily.today_tasks(day.date(), repo.db_path)}
    assert tasks["new"].done and tasks["quiz"].current == 1 and "writing" not in tasks
