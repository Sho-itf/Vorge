# Vorge 設計メモ

## 1. 全体方針

- **画面(UI)** と **処理(ロジック)** と **データ保存(DB)** を別ファイルに分ける。
  - 画面を作り直しても、ロジックとDBはそのまま使える。
  - ロジックは Streamlit に依存しないので、pytest でテストしやすい。
- 機能ごとにフォルダ(パッケージ)を分ける。将来の機能は `vorge/<機能名>/` を追加し、
  画面は `views/<機能名>.py` を追加して `app.py` のナビゲーションに 1 行足すだけにする。

```
 views/ (Streamlit画面)  ─呼び出す→  vorge/vocab/ (ロジック)  ─呼び出す→  vorge/db.py (SQLite)
```

## 2. フォルダ構成

```
Vorge/
├─ app.py                  … 起動ファイル。DB初期化とサイドバーのナビゲーション
├─ views/                  … 画面(1ファイル = 1ページ)
│   ├─ home.py             … ホーム
│   ├─ flashcard.py        … フラッシュカード
│   ├─ quiz.py             … 穴埋めクイズ
│   ├─ writing.py          … 作文トレーニング
│   ├─ debate.py           … 議論トレーニング
│   ├─ history.py          … 学習履歴
│   ├─ library.py          … 語彙ライブラリ(検索・一覧・詳細・追加・編集・削除)
│   └─ csv_io.py           … CSV入出力
├─ vorge/                  … アプリ本体のロジック(Streamlitに依存しない部分)
│   ├─ config.py           … パスや環境変数(.env)の読み込み
│   ├─ db.py               … SQLite接続とテーブル作成
│   ├─ vocab/              … 語彙機能
│   │   ├─ models.py       … 語彙データの形(Vocab)と入力チェック
│   │   ├─ repository.py   … 語彙のDB操作(追加・検索・更新・削除・一括取り込み)
│   │   └─ csv_io.py       … CSVの読み込み・検証・書き出し
│   ├─ flashcard/          … フラッシュカード機能
│   │   ├─ scheduler.py    … 間隔反復の計算ルール(DB・画面に依存しない)
│   │   ├─ repository.py   … 習得状況・学習履歴のDB操作、出題の選択
│   │   └─ session.py      … 出題中の状態(何枚目か等)の出し入れ
│   ├─ debate/            … 議論トレーニング
│   │   ├─ templates.py    … 型(基本・反論つき)と欄の定義、立場
│   │   └─ checker.py      … 欄ごとのチェック・つなぎ言葉・具体例の判定、添削依頼文
│   ├─ quiz/              … 穴埋めクイズ
│   │   ├─ builder.py      … 例文の空欄化・はずれ選択肢の選択・入力式の採点(DB・画面に依存しない)
│   │   └─ repository.py   … 問題セットの作成と回答記録(quiz_log)
│   ├─ writing/           … 作文トレーニング
│   │   ├─ prompts.py      … 選択肢(お題の種類・文字数・語彙の選び方)とお題の初期セット60個
│   │   ├─ checker.py      … 自動チェック(語彙の使用・文字数・繰り返し・文末)と添削依頼文
│   │   └─ repository.py   … お題・作文の保存、使う語彙の選択
│   ├─ settings.py         … 前回選んだ条件などの設定を DB に保存
│   ├─ history/           … 学習履歴機能
│   │   └─ repository.py   … 回答数・正答率・連続日数・苦手語彙などの集計(読み取り専用)
│   └─ ui/                 … 画面間で共通の部品
│       ├─ theme.py        … 余白・フォントなどのCSS
│       └─ components.py   … 語彙カード、入力フォーム、通知など
├─ tests/                  … pytest のテスト
├─ docs/design.md          … この設計メモ
├─ data/                   … SQLiteのDBファイル(自動作成、Git管理外)
├─ .streamlit/config.toml  … Streamlitの設定
├─ csv/vorge_vocab_seed.csv … サンプル語彙(200語)
├─ requirements.txt / pyproject.toml / .gitignore / .env.example
```

将来の追加予定(今回は作らない):

```
vorge/reading/     … 読解トレーニング               views/reading.py
vorge/debate/      … 議論トレーニング               views/debate.py
vorge/ai/          … AI添削(APIキーは .env から読む)
```

## 3. データベース

### 今回作成するテーブル

**vocab**(語彙ライブラリ)

| 列 | 型 | 説明 |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | 自動採番。一意性はこれで判定(同じ word の複数登録OK) |
| word | TEXT NOT NULL | 語彙 |
| reading | TEXT | 読み |
| meaning | TEXT NOT NULL | 意味 |
| example_1, example_2 | TEXT | 例文 |
| nuance | TEXT | ニュアンス |
| synonyms, antonyms, collocations | TEXT | 類義語・対義語・コロケーション(カンマ区切り) |
| category | TEXT | カテゴリ(空なら「未分類」) |
| difficulty | INTEGER 1〜5 | 難易度(CHECK制約あり) |
| source | TEXT | 出典 |
| created_at, updated_at | TEXT | 登録・更新日時(「今日追加した語彙数」に使う) |

**categories**(カテゴリ候補)… 初期値10件+ユーザーが追加したもの。

### 第2段階で追加したテーブル(スキーマバージョン 2)

**review_state**(語彙ごとの現在の習得状況。1 語彙 1 行。未学習の語彙には行が無い)

| 列 | 説明 |
|---|---|
| vocab_id | vocab.id(主キー、語彙削除時のみ連鎖削除) |
| interval_days | 現在の復習間隔(日) |
| next_review | 次回復習日(YYYY-MM-DD) |
| review_count / correct_count / unsure_count / wrong_count | 回答回数の内訳 |
| last_result / last_studied_at | 最後の回答 |

**study_log**(回答のたびに 1 行追加する学習履歴)

| 列 | 説明 |
|---|---|
| vocab_id | 語彙ID |
| studied_at | 学習日時 |
| mode | word_to_meaning / meaning_to_word |
| result | correct / unsure / wrong(回答結果 = 3 段階の自己評価) |
| self_rating | 将来の細かい自己評価(1〜5)用。現在は未使用 |
| interval_days / next_review | この回答で決まった間隔と次回復習日 |

### 間隔反復のルール(`vorge/flashcard/scheduler.py`)

| 回答 | 次の間隔 |
|---|---|
| 正解 | 今の間隔 × 2.5(切り上げ、上限 365 日)。初回は 1 日扱い → 3 → 8 → 20 … |
| 自信がない | 据え置き |
| 不正解 | 1 日(翌日) |

習得状況: 未学習 / 学習中(7日未満)/ 定着中(7〜20日)/ 習得(21日以上)。

出題順: 復習日が今日以前の語彙(古い順)→ 未学習の語彙(指定数まで)。シャッフルしてもこの優先順は保つ。

### 学習履歴を守るための工夫

- 学習履歴は vocab と**別テーブル**にし、`vocab_id` でつなぐ。
- CSVの「上書きインポート」は `UPDATE` で既存行を書き換える。
  `INSERT OR REPLACE` は内部的に「削除→再作成」になり、履歴が連鎖削除される恐れがあるので使わない。
- DBの初期化は `CREATE TABLE IF NOT EXISTS` のみ。既存データを消す処理はアプリに含めない。
- テーブル構造の変更は `PRAGMA user_version` でバージョン管理し、段階的に移行する。

## 4. CSV仕様

- 列: `id,word,reading,meaning,example_1,example_2,nuance,synonyms,antonyms,collocations,category,difficulty,source`
- 必須列: `word`, `meaning`(他の列は省略可。未知の列は無視して警告)
- `id`: 空なら自動採番。正の整数のみ。ファイル内での重複はエラー。
- `difficulty`: 1〜5の整数。空なら3。基準は次のとおり(語を足すときはこれにそろえる)。
  - 1:日常会話や中学〜高校の教科書で身につく語
  - 2:ニュースや新書で普通に目にする語
  - 3:評論文・ビジネス文書で頻出する、やや硬い語
  - 4:文章語・専門寄りの語、または意味・用法に注意がいる語
  - 5:哲学・批評などの専門用語、まれな語、読みや誤用の落とし穴が深い語
- `category`: 意味の分野で分ける。紛らわしい組み合わせの境目は次のとおり。
  - 判断・論理:判断や推論の道具になる概念(因果、仮説、必要条件、整合性など)
  - 論理・議論:議論の場で使う語・論証の型・誤謬(反駁、論拠、立証、論点先取など)
  - 思考・認識:心の働きや気づき方(直観、内省、洞察、先入観など)
  - 抽象概念:哲学・思想・批評の用語(概念、止揚、表象、メタ認知など)
  - 時間・変化:時の流れ・変化・持続(推移、恒常的、一過性、漸次など)
  - 四字熟語:四字熟語(ただし議論用の「牽強付会」「我田引水」「枝葉末節」「二律背反」は論理系のカテゴリに残す)
  - 「誤用注意」「言い換え表現」は意味ではなく用途で分けたカテゴリ
- 文字コード: UTF-8(BOM有り/無し)を優先し、読めなければ Shift_JIS(cp932)で読む。
- エクスポートは UTF-8 with BOM(Excelで開いても文字化けしない)。
- インポートの流れ: ①読み込み・検証(まだ保存しない)→ ②結果確認(エラー行・ID重複行)→ ③実行。
  - エラー行は取り込まず、行番号と理由を表示。
  - 既存IDと重複する行はデフォルトでスキップ。「上書きインポート」を選ぶと更新。

## 5. 学習履歴の指標

- 正答率 = 正解 ÷ 全回答(「自信がない」は正解に含めない)。直近7日とその前の7日を比較表示。
- 連続学習日数 = 今日(まだ回答が無ければ昨日)からさかのぼって、回答がある日が続いている日数。
- 苦手な語彙 = 不正解か「自信がない」が1回以上ある語彙を、正答率の低い順 → 不正解回数の多い順に最大20語。
  ここから「苦手な語彙を練習する」で出題でき、回答は通常どおり記録・復習日に反映される。
- 今後7日の復習予定 = 日ごとの復習予定数(今日の分には期限切れを含む)。

## 6. 作文トレーニング(スキーマバージョン 3)

テーブル:
- `writing_prompts` … お題(kind: daily / explain / opinion、active で出題のオン/オフ)。初期セット60個は一度だけ登録し、削除したお題は復活させない
- `writings` … 作文。お題の文面は書いた時点のものを保存するので、お題を編集・削除しても作文は残る
- `writing_vocab` … 作文で指定した語彙と、実際に使えたか(used)。語彙を削除すると対応だけが消える
- `app_settings` … 前回選んだ出題条件などの設定(JSON で保存)

語彙の選び方:
- 苦手 = 不正解か「自信がない」が1回以上 / 学習中 = 学習済みで間隔21日未満 / 未学習 = 一度も学習していない
- おまかせ = 苦手 → 学習中 → 未学習 から1つずつ順番に選ぶ。足りなければ全語彙から補う

自動チェック(外部APIなし、目安):
- 指定語彙の使用(活用する語は最後の1文字を除いた形、ひらがな書きも認める)
- 文字数(空白・改行を除く)と目安との比較
- 同じ言葉の繰り返し(「思う」などの口癖、漢字2字以上・カタカナ3字以上の語が3回以上)
- 同じ文末が3回以上続く / です・ます調とだ・である調の混在(どちらも2文以上)

## 7. 穴埋めクイズ(スキーマバージョン 4)

- 例文 1・2 のうち、語彙(活用形を含む)が入っているものを空欄にして出題する。例文が無い語彙は出題しない
- はずれの選択肢:同じカテゴリで難易度差 1 以内 → 同じカテゴリ → その他、の順に選ぶ。
  「どちらも正解」を防ぐため、正解と同じ語・類義語として登録された語は使わない
- 入力式は、語彙・読み(ひらがな)・例文中の表記のどれでも正解。全角/半角・空白は無視
- 回答は `quiz_log` に記録し、フラッシュカードの復習日(review_state)には影響させない
- 出題範囲の「苦手・学習中・未学習」は `ReviewRepository.ids_in_group` で作文トレーニングと共通

## 8. 議論トレーニング(スキーマバージョン 5)

- 保存先は作文と同じ `writings` テーブル(kind = 'debate')。初めての「列の追加」による移行:
  `stance`(pro/con)・`template`(prep/rebuttal)・`sections`(欄ごとの文章の JSON)を追加。
  `db.py` の `ADDED_COLUMNS` に書いた列が無ければ `ALTER TABLE` で足す(既存の行は既定値 '' になる)
- `body` には欄をつなげた 1 つの文章を入れるので、作文と同じ一覧・語彙の使用回数の集計がそのまま使える
- お題は作文の「意見・議論」のお題を共用。自由入力のお題は prompt_id が NULL
- 語彙の選び方に「論理・議論の語彙を優先」(カテゴリ 論理・議論 / 判断・論理)を追加
- 自動チェック:空の欄、指定語彙、具体例(「例えば」「実際」や数字+単位)、つなぎ言葉(理由・譲歩・逆接・結論)

## 9. 第 7 段階の改善(スキーマバージョン 6)

- 共通部品:`vorge/ui/persist.py`(設定・下書きの DB 保存)、`components.html`、
  `ui/writing_list.py`(作文・議論の一覧)、`ui/prompt_admin.py`(お題の管理)、`ui/learning_record.py`(学習の記録)
- 苦手の判定:`HistoryRepository.weak_vocab` が唯一の定義。フラッシュカード(正解・自信がない 0.5・不正解)と
  クイズ(正解・不正解)を合わせた正答率が 80% 未満で、間違えたことがある語彙。`ids_in_group("weak")` もこれを使う
- 下書き:`app_settings` に `draft_writing` / `draft_debate` として JSON で保存し、作文・議論を保存したら削除
- フラッシュカードの「もう一度」:`session.add_retry` で出題列の最後に 1 回だけ追加。2 回目の回答は記録しない
- `quiz_excluded`:「この問題はおかしい」と報告した (語彙, 例文)。出題時に除外し、報告時はその回答記録を削除
- 範囲スライダーはウィジェット用のキーと設定用のキーを分ける(value を明示しないと 1 つの値のスライダーになるため)
- 画面テスト:`tests/test_views.py`(AppTest で全ページの表示と主要な操作、設定・下書きの記憶を確認)

## 10. 第 8 段階:学習の質と土台の強化(スキーマバージョン 9)

### 開発の土台
- `requirements.txt` はバージョン固定、開発用は `requirements-dev.txt`。`ruff` でコードチェック
- GitHub Actions(`.github/workflows/test.yml`)が push・プルリクエスト時に ruff と pytest を実行
- `.gitattributes` で改行コードを LF に統一
- DB の移行は `db.MIGRATIONS`(バージョン, 移行処理)の一覧。v6 までは `_baseline` にまとめ、以降 1 バージョンずつ追加。
  データの入った DB を移行する前に `backups/before_vN_…db` を自動で作る

### 移行の一覧
| バージョン | 内容 |
|---|---|
| 7 | 語彙を `vocab_all` に改名し `deleted_at`(ゴミ箱)を追加、`vocab` はゴミ箱以外を見せるビュー。作文にも `deleted_at`。3 本目以降の例文 `vocab_examples` |
| 8 | `review_state` に `fsrs_card`(FSRS のカード JSON)と `easy_count` |
| 9 | 読解:`reading_notes`(文章・要約)、`reading_candidates`(登録候補の語) |

- 書き込み(追加・更新・削除)は `vocab_all`、読み取りは原則 `vocab` ビュー。ビューは `SELECT *` の列が作成時に固定されるので、
  `vocab_all` に列を足したらビューも作り直すこと

### 学習
- 復習の計算は FSRS(`flashcard/scheduler.py`)。分単位のステップは使わず日単位。回答は 不正解=Again / 自信がない=Hard /
  正解=Good / 簡単=Easy。以前の方式の記録は、次の回答時に今の間隔を安定度として引き継いで変換(`legacy_card`)
- 「今日」は `timeutil` の区切り時刻(初期値 4 時)で数える。SQL では `timeutil.sql_date(列名)` を使う
- 今日の学習メニュー:`vorge/daily.py`(目標は app_settings の `daily_new` / `daily_quiz` / `daily_writing`)
- 関連語(`vocab/relations.py`):類義語・対義語の文字列と登録済みの語を表示のたびに照合。
  詳細ではクエリパラメータ `?vocab=ID` のリンクで語彙ライブラリの詳細を開く

### 画面
- キーボード操作(`ui/shortcuts.py`):小さな JavaScript でキーとボタンの表示文字を対応させてクリックする
- スマホ:`theme.py` の `@media (max-width: 640px)` で一覧の折り返し・文字サイズ・ボタンの大きさを調整
- バックアップ・ゴミ箱は「データ管理」画面のタブ(`ui/backup_panel.py`、`ui/trash_panel.py`)

### 読解(`vorge/reading/`)
- 未登録語の候補は「漢字 2 字以上・カタカナ 4 字以上」から、登録済み・よく使う言葉(`COMMON_WORDS`)を除いたもの。
  辞書を使わない目安なので、画面で自分で選ぶ
- 登録済み語彙の印は 1 回の正規表現の置き換えで付ける(1 語ずつ置き換えると、意味の文字の中まで置き換えてしまうため)
