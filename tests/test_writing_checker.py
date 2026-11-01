from vorge.writing import checker


def test_count_chars_ignores_spaces_and_newlines():
    assert checker.count_chars("今日は 晴れ。\n明日は　雨。") == 11


def test_vocab_usage_allows_conjugation_and_reading():
    used = checker.check_vocab_usage(
        "説明を聞いてやっと腑に落ちた。そうたいかして考える。",
        [("腑に落ちる", "ふにおちる"), ("相対化", "そうたいか"), ("逡巡", "しゅんじゅん")],
    )
    assert used == {"腑に落ちる": True, "相対化": True, "逡巡": False}


def test_short_inflectable_word_is_not_over_matched():
    # 「論う」の語幹「論」だけでは「論文」に一致させない
    assert checker.check_vocab_usage("論文を読んだ", [("論う", "あげつらう")]) == {"論う": False}


def test_repeated_words():
    body = "私は思う。君も思うだろう。皆そう思っている。課題は課題として、課題を解く。"
    repeated = dict(checker.find_repeated_words(body))
    assert repeated["思う"] == 3
    assert repeated["課題"] == 3


def test_repeated_words_exclude_target_vocab():
    body = "相対化する。相対化した。相対化しよう。"
    assert checker.find_repeated_words(body, {"相対化"}) == []


def test_monotone_endings():
    # 2 回続くだけなら知らせない
    sentences = checker.split_sentences("顔を洗った。服を買った。家を出る。")
    assert checker.find_monotone_endings(sentences) is None
    sentences = checker.split_sentences("行った。買った。知った。終わる。")
    assert checker.find_monotone_endings(sentences) == ("った", 3)


def test_style_mix():
    mixed = checker.split_sentences("私は学生です。毎日勉強します。でも疲れた。眠いのだ。")
    assert checker.find_style_mix(mixed) == (2, 2)
    polite = checker.split_sentences("私は学生です。毎日勉強します。楽しいです。")
    assert checker.find_style_mix(polite) is None


def test_split_sentences_with_fullwidth_marks():
    assert checker.split_sentences("本当?うん!そうだ。") == ["本当?", "うん!", "そうだ。"]


def test_check_length_status():
    assert checker.check("あ" * 50, [], 100, 200).length_status == "short"
    assert checker.check("あ" * 150, [], 100, 200).length_status == "ok"
    assert checker.check("あ" * 250, [], 100, 200).length_status == "long"


def test_build_review_prompt_contains_everything():
    text = checker.build_review_prompt("お題A", [("逡巡", "ためらうこと")], "本文です", 100, 200)
    assert "お題A" in text and "逡巡:ためらうこと" in text and "本文です" in text
    assert "100〜200字" in text


def test_sentences_with():
    body = "私は迷った。結局、腑に落ちた。そうだ、ふにおちる瞬間だった。"
    assert checker.sentences_with(body, "腑に落ちる", "ふにおちる") == [
        "結局、腑に落ちた。", "そうだ、ふにおちる瞬間だった。"
    ]
