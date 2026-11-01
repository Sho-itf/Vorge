"""テスト共通の準備。テストごとに一時フォルダに空の DB を作るので、本物のデータには触れない。"""

import pytest

from vorge.db import init_db
from vorge.vocab.repository import VocabRepository


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return VocabRepository(db_path)


@pytest.fixture(autouse=True)
def fixed_intervals():
    """FSRS の間隔の「ゆらぎ」を切り、テストの結果を毎回同じにする。"""
    from vorge.flashcard import scheduler

    scheduler.configure(enable_fuzzing=False)
    yield
    scheduler.configure(enable_fuzzing=True)
