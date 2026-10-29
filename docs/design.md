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
│   ├─ library.py          … 語彙ライブラリ(検索・一覧・詳細・追加・編集・削除)
│   └─ csv_io.py           … CSV入出力
├─ vorge/                  … アプリ本体のロジック(Streamlitに依存しない部分)
│   ├─ config.py           … パスや環境変数(.env)の読み込み
│   ├─ db.py               … SQLite接続とテーブル作成
│   ├─ vocab/              … 語彙機能
│   │   ├─ models.py       … 語彙データの形(Vocab)と入力チェック
│   │   ├─ repository.py   … 語彙のDB操作(追加・検索・更新・削除・一括取り込み)
│   │   └─ csv_io.py       … CSVの読み込み・検証・書き出し
│   └─ ui/                 … 画面間で共通の部品
│       ├─ theme.py        … 余白・フォントなどのCSS
│       └─ components.py   … 語彙カード、入力フォーム、通知など
├─ tests/                  … pytest のテスト
├─ docs/design.md          … この設計メモ
├─ data/                   … SQLiteのDBファイル(自動作成、Git管理外)
├─ .streamlit/config.toml  … Streamlitの設定
├─ vorge_vocab_seed.csv    … サンプル語彙(99語)
├─ requirements.txt / pyproject.toml / .gitignore / .env.example
```

将来の追加予定(今回は作らない):

```
vorge/flashcard/   … 出題選択・間隔反復の計算        views/flashcard.py
vorge/history/     … 学習履歴の保存・集計            views/history.py
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

### 将来追加するテーブル(設計のみ)

```sql
-- 語彙ごとの現在の習得状況(1語彙につき1行)
CREATE TABLE review_state (
  vocab_id      INTEGER PRIMARY KEY REFERENCES vocab(id) ON DELETE CASCADE,
  interval_days INTEGER NOT NULL DEFAULT 1,
  next_review   TEXT,           -- 次回復習日
  streak        INTEGER NOT NULL DEFAULT 0
);
-- 回答のたびに1行追加する学習履歴
CREATE TABLE study_log (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  vocab_id    INTEGER NOT NULL REFERENCES vocab(id) ON DELETE CASCADE,
  studied_at  TEXT NOT NULL,
  result      TEXT NOT NULL,    -- correct / unsure / wrong
  self_rating INTEGER,
  next_review TEXT
);
```

間隔反復: 正解 → interval×2.5(切り上げ)/ 自信がない → 据え置き / 不正解 → 1日。

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
