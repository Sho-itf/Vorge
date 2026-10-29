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
vorge/writing/     … 文章トレーニング               views/writing.py
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
- `difficulty`: 1〜5の整数。空なら3。
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
