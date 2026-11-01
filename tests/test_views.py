"""画面のテスト(Streamlit の AppTest でアプリを実際に動かし、ボタンを押して確かめる)。

ロジックのテストでは見つからない、画面まわりの不具合(ウィジェットの値の扱いなど)を検出するためのもの。
本物の DB には触れず、テストごとに一時フォルダの DB を使う。
"""

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from vorge import config, timeutil
from vorge.db import init_db
from vorge.flashcard.repository import ReviewRepository
from vorge.quiz.repository import FORMAT_CHOICE, QuizRepository
from vorge.vocab.models import Vocab
from vorge.vocab.repository import VocabRepository

APP = str(Path(__file__).resolve().parent.parent / "app.py")
PAGES = [
    "views/home.py",
    "views/flashcard.py",
    "views/quiz.py",
    "views/writing.py",
    "views/debate.py",
    "views/history.py",
    "views/library.py",
    "views/csv_io.py",
]
WORDS = ["俯瞰", "洞察", "看破", "熟慮", "論拠", "帰結"]


@pytest.fixture
def app(tmp_path, monkeypatch):
    """一時 DB に語彙を入れた状態でアプリを起動する。"""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    init_db(db_path)
    repo = VocabRepository(db_path)
    for w in WORDS:
        repo.add(Vocab(word=w, meaning=f"{w}の意味", example_1=f"これは{w}の例文だ",
                       category="論理・議論" if w in ("論拠", "帰結") else "思考・認識"))
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def open_page(at: AppTest, page: str) -> AppTest:
    at.switch_page(page).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def click(at: AppTest, label: str) -> AppTest:
    """ラベルに label を含むボタンを押す。"""
    button = next(b for b in at.button if label in b.label)
    button.click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@pytest.mark.parametrize("page", PAGES)
def test_every_page_opens(app, page):
    open_page(app, page)
    assert app.title


def test_empty_db_pages_show_guidance(tmp_path, monkeypatch):
    db_path = tmp_path / "empty.db"
    monkeypatch.setattr(config, "DB_PATH", db_path)
    init_db(db_path)
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    for page in PAGES:
        open_page(at, page)


def test_flashcard_answer_flow(app):
    open_page(app, "views/flashcard.py")
    click(app, "学習をはじめる")
    click(app, "答えを見る")
    click(app, "✅ 正解")
    assert any("2 /" in p.text for p in app.get("progress"))


def test_quiz_flow_and_difficulty_slider_keeps_range(app):
    open_page(app, "views/quiz.py")
    # 以前の不具合:範囲スライダーが 1 つの値になり、2 回目の表示でエラーになっていた
    assert app.select_slider(key="qz_difficulty_widget").value == (1, 5)
    click(app, "クイズをはじめる")
    assert app.session_state["qz_difficulty"] == (1, 5)
    choice = next(b for b in app.button if b.key and b.key.startswith("choice_"))
    choice.click().run()
    assert not app.exception
    assert app.success or app.error  # 正解・不正解のどちらかが表示される


def test_writing_save_flow(app):
    open_page(app, "views/writing.py")
    click(app, "お題を決めて書きはじめる")
    app.text_area[0].input("これは俯瞰と洞察を使った作文です。").run()
    click(app, "保存する")
    assert any("保存しました" in s.value for s in app.success)


def test_debate_save_flow(app):
    open_page(app, "views/debate.py")
    click(app, "はじめる")
    for area in app.text_area:
        area.input("確かに論拠はある。しかし帰結を考えるべきだ。したがってこう考える。").run()
    click(app, "保存する")
    assert any("保存しました" in s.value for s in app.success)


def test_library_lists_words(app):
    open_page(app, "views/library.py")
    assert sum(1 for b in app.button if b.label == "詳細") == len(WORDS)


def test_learning_record_component(app):
    """語彙の詳細に出す「学習の記録」が、記録があってもエラーにならない。"""
    vocab = VocabRepository(config.DB_PATH).search("俯瞰")[0]
    ReviewRepository(config.DB_PATH).record_answer(vocab.id, "wrong")
    QuizRepository(config.DB_PATH).record(vocab.id, FORMAT_CHOICE, False, "洞察")
    at = AppTest.from_function(_render_record, args=(vocab.id,), default_timeout=60)
    at.run()
    assert not at.exception
    assert any("フラッシュカード" in m.value for m in at.markdown)


def _render_record(vocab_id):
    # AppTest.from_function はこの関数のソースだけを実行するので、import は中に書く
    from vorge.ui.learning_record import show_learning_record
    from vorge.vocab.repository import VocabRepository

    show_learning_record(VocabRepository().get(vocab_id))


def test_settings_are_remembered_after_restart(app):
    """設定を変えてアプリを開き直しても、前回の値が使われる。"""
    open_page(app, "views/flashcard.py")
    app.number_input(key="fc_setting_new_limit").set_value(25).run()
    open_page(app, "views/library.py")
    app.slider(key="page_size").set_value(40).run()

    fresh = AppTest.from_file(APP, default_timeout=60)  # ブラウザを開き直したのと同じ状態
    fresh.run()
    open_page(fresh, "views/flashcard.py")
    assert fresh.number_input(key="fc_setting_new_limit").value == 25
    assert fresh.select_slider(key="fc_difficulty_widget").value == (1, 5)
    open_page(fresh, "views/library.py")
    assert fresh.slider(key="page_size").value == 40


def test_writing_draft_survives_restart(app):
    open_page(app, "views/writing.py")
    click(app, "お題を決めて書きはじめる")
    app.text_area[0].input("書きかけの文章").run()

    fresh = AppTest.from_file(APP, default_timeout=60)
    fresh.run()
    open_page(fresh, "views/writing.py")
    assert fresh.text_area[0].value == "書きかけの文章"


def test_flashcard_wrong_answer_comes_back_once_without_recording(app):
    open_page(app, "views/flashcard.py")
    app.number_input(key="fc_setting_new_limit").set_value(1).run()
    click(app, "学習をはじめる")
    click(app, "答えを見る")
    click(app, "❌ 不正解")
    # 1 枚だけの出題に、間違えた語彙が「もう一度」として追加される
    assert app.session_state["fc_queue"] == [app.session_state["fc_queue"][0]] * 2
    click(app, "答えを見る")
    click(app, "✅ 正解")
    assert len(app.session_state["fc_results"]) == 1  # 2 回目は記録しない
    assert app.session_state["fc_retry_results"] == ["correct"]
    assert ReviewRepository(config.DB_PATH).count_answers_on(date.today()) == 1


def test_quiz_report_bad_question(app):
    open_page(app, "views/quiz.py")
    click(app, "クイズをはじめる")
    choice = next(b for b in app.button if b.key and b.key.startswith("choice_"))
    choice.click().run()
    click(app, "この問題はおかしい")
    assert QuizRepository(config.DB_PATH).total_answers() == 0
    assert len(QuizRepository(config.DB_PATH).excluded_examples()) == 1
    assert app.session_state["qz_results"] == []


def test_settings_page_changes_day_start(app):
    open_page(app, "views/settings.py")
    app.selectbox[0].set_value(6).run()
    assert not app.exception
    assert timeutil.day_start_hour() == 6
    timeutil.set_day_start_hour(timeutil.DEFAULT_DAY_START_HOUR)  # ほかのテストに影響しないよう戻す


def test_trash_tab_restore_and_library_link(app):
    repo = VocabRepository(config.DB_PATH)
    vid = repo.search("俯瞰")[0].id
    repo.delete(vid)
    open_page(app, "views/csv_io.py")
    click(app, "元に戻す")
    assert repo.get(vid) is not None

    # 他の語彙の詳細からのリンク(?vocab=ID)で、語彙ライブラリが開ける
    app.query_params["vocab"] = str(vid)
    open_page(app, "views/library.py")
    assert "vocab" not in app.query_params


def test_flashcard_cloze_with_typed_answer(app):
    open_page(app, "views/flashcard.py")
    app.radio(key="fc_setting_mode").set_value("cloze").run()
    app.toggle(key="fc_setting_input").set_value(True).run()
    click(app, "学習をはじめる")
    assert any("空欄に入る語彙" in m.value for m in app.markdown)
    vocab = VocabRepository(config.DB_PATH).get(app.session_state["fc_queue"][0])
    app.text_input[0].input(vocab.word)  # フォームの中の入力は、送信ボタンと同時に送る
    click(app, "答え合わせ")
    assert app.session_state["fc_typed_ok"] is True
    assert any("正解です" in s.value for s in app.success)
    click(app, "🌟 簡単")
    assert app.session_state["fc_results"][0]["結果"] == "簡単"


def test_home_daily_menu_starts_flashcard(app):
    open_page(app, "views/home.py")
    assert any("今日の学習" in s.value for s in app.subheader)
    click(app, "続きから")
    assert app.session_state["fc_label"] == "今日の学習"
    assert len(app.session_state["fc_queue"]) == len(WORDS)  # 目標 10 語 > 登録 6 語なので全部
