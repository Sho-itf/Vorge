"""CSV入出力画面:CSV からの一括インポートと、CSV へのエクスポート。

インポートは 3 ステップ:
  ① ファイルを選ぶ → ② 検証結果を確認(まだ保存しない)→ ③「インポートを実行」で保存
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from vorge import config
from vorge.vocab.csv_io import CsvFormatError, ParseResult, export_csv, parse_csv
from vorge.vocab.models import CSV_COLUMNS, FIELD_LABELS, REQUIRED_COLUMNS
from vorge.vocab.repository import VocabRepository

repo = VocabRepository()
st.session_state.setdefault("uploader_version", 0)  # アップロード欄をリセットするための番号

st.title("CSV入出力")
tab_import, tab_export = st.tabs(["📥 インポート", "📤 エクスポート"])


def show_format_help() -> None:
    with st.expander("CSV の形式について"):
        st.markdown(
            "- 1 行目に列名(ヘッダー)が必要です。\n"
            f"- **必須の列**: {', '.join(f'`{c}`' for c in REQUIRED_COLUMNS)}"
            "(この 2 つの値が空の行はエラーになります)\n"
            "- 使える列: " + ", ".join(f"`{c}`({FIELD_LABELS[c]})" for c in CSV_COLUMNS) + "\n"
            "- `id` が空の行は自動で番号を振ります。\n"
            "- `difficulty` は 1〜5 の整数(空なら 3)。\n"
            "- `category` が空なら「未分類」。新しいカテゴリは自動で候補に追加されます。\n"
            "- 文字コードは UTF-8(BOM付きも可)推奨。Excel の Shift_JIS 形式も読み込めます。\n"
            "- 値にカンマや改行を含む場合は `\"概観,鳥瞰\"` のようにダブルクォートで囲みます。"
        )


def show_result_message() -> None:
    """直前に実行したインポートの結果を表示する。"""
    done = st.session_state.pop("import_done", None)
    if done:
        st.success(
            f"インポートが完了しました:新規 {done.inserted} 件 / "
            f"更新 {done.updated} 件 / スキップ {done.skipped} 件"
        )
        st.page_link("views/library.py", label="語彙ライブラリで確認する", icon=":material/menu_book:")


def show_preview(result: ParseResult, source_name: str) -> None:
    """検証結果を表示し、「インポートを実行」ボタンを出す。"""
    ids_in_file = [r.vocab.id for r in result.rows if r.vocab.id is not None]
    existing = repo.get_many(ids_in_file)
    duplicates = [r for r in result.rows if r.vocab.id in existing]
    new_rows = [r for r in result.rows if r.vocab.id not in existing]

    st.markdown(f"#### ② 検証結果:`{source_name}`")
    st.caption(f"文字コード: {result.encoding}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("データ行", result.total_rows)
    c2.metric("新規登録できる行", len(new_rows))
    c3.metric("既存IDと重複", len(duplicates))
    c4.metric("エラー行", len(result.errors))

    for w in result.warnings:
        st.warning(w)

    if result.errors:
        st.error(
            f"**{len(result.errors)} 行にエラーがあります。** これらの行は取り込まれません。"
            "CSV を修正して読み込み直すこともできます。"
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "行番号": [e.line for e in result.errors],
                    "語彙": [e.word for e in result.errors],
                    "エラー内容": [" / ".join(e.messages) for e in result.errors],
                }
            ),
            hide_index=True,
            width="stretch",
        )

    overwrite = False
    if duplicates:
        st.warning(
            f"**{len(duplicates)} 行のIDが、登録済みの語彙と重複しています。**"
            "そのままではこれらの行は**スキップ**されます(既存データは変更されません)。"
        )
        st.dataframe(
            pd.DataFrame(
                {
                    "行番号": [r.line for r in duplicates],
                    "ID": [r.vocab.id for r in duplicates],
                    "CSVの語彙": [r.vocab.word for r in duplicates],
                    "登録済みの語彙": [existing[r.vocab.id].word for r in duplicates],
                }
            ),
            hide_index=True,
            width="stretch",
        )
        overwrite = st.checkbox(
            "上書きインポート(重複したIDの語彙を CSV の内容で更新する)",
            help="登録済みの語彙が CSV の内容に置き換わります。ID は変わらないので、"
            "将来の学習履歴は保持されます。",
        )

    if new_rows:
        with st.expander(f"新規登録される語彙のプレビュー({len(new_rows)} 件)"):
            st.dataframe(
                pd.DataFrame(
                    {
                        "行番号": [r.line for r in new_rows],
                        "ID": [r.vocab.id if r.vocab.id else "(自動)" for r in new_rows],
                        "語彙": [r.vocab.word for r in new_rows],
                        "意味": [r.vocab.meaning for r in new_rows],
                        "カテゴリ": [r.vocab.category for r in new_rows],
                        "難易度": [r.vocab.difficulty for r in new_rows],
                    }
                ),
                hide_index=True,
                width="stretch",
            )

    n_update = len(duplicates) if overwrite else 0
    n_skip = 0 if overwrite else len(duplicates)
    st.markdown("#### ③ 実行")
    st.write(f"新規 **{len(new_rows)}** 件 / 更新 **{n_update}** 件 / スキップ **{n_skip}** 件")

    if st.button(
        "インポートを実行",
        type="primary",
        disabled=(len(new_rows) + n_update == 0),
    ):
        try:
            done = repo.import_vocabs([r.vocab for r in result.rows], overwrite=overwrite)
        except Exception as e:
            st.error(f"保存中にエラーが発生したため、すべて取り消しました。\n\n詳細: {e}")
            return
        st.session_state.import_done = done
        st.session_state.uploader_version += 1  # アップロード欄を空に戻す
        st.rerun()


# ============ インポート ============
with tab_import:
    show_result_message()
    show_format_help()

    st.markdown("#### ① ファイルを選ぶ")
    choices = ["CSVファイルをアップロード"]
    if config.SEED_CSV_PATH.exists():
        choices.append(f"同梱のサンプル語彙({config.SEED_CSV_PATH.name})")
    source = st.radio("読み込むデータ", choices, horizontal=True, label_visibility="collapsed")

    data: bytes | None = None
    source_name = ""
    if source == choices[0]:
        uploaded = st.file_uploader(
            "CSVファイルを選択", type=["csv"], key=f"uploader_{st.session_state.uploader_version}"
        )
        if uploaded is not None:
            data, source_name = uploaded.getvalue(), uploaded.name
    else:
        data, source_name = config.SEED_CSV_PATH.read_bytes(), config.SEED_CSV_PATH.name

    if data is not None:
        try:
            parsed = parse_csv(data)
        except CsvFormatError as e:
            st.error(f"**CSV を読み込めませんでした。**\n\n{e}")
        else:
            if parsed.total_rows == 0:
                st.info("データ行がありません(ヘッダー行だけのファイルです)。")
            else:
                show_preview(parsed, source_name)

# ============ エクスポート ============
with tab_export:
    total = repo.count()
    if total == 0:
        st.info("エクスポートできる語彙がまだありません。")
    else:
        st.write("登録済みの語彙を CSV ファイルとして保存します。バックアップや Excel での編集に使えます。")
        selected = st.multiselect(
            "カテゴリで絞り込む(空欄ならすべて)",
            repo.list_categories(),
            placeholder="すべてのカテゴリ",
        )
        vocabs = repo.search(categories=selected)
        st.caption(
            f"{len(vocabs)} 件を書き出します。文字コードは UTF-8(BOM付き)なので Excel でも文字化けしません。"
        )
        st.download_button(
            "📤 CSVをダウンロード",
            data=export_csv(vocabs),
            file_name=f"vorge_vocab_{datetime.now():%Y%m%d_%H%M}.csv",
            mime="text/csv",
            type="primary",
            disabled=not vocabs,
        )
