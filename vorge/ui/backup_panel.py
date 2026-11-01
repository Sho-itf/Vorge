"""「データ管理」画面の「💾 バックアップ」タブ。"""

from datetime import datetime

import streamlit as st

from vorge import backup, config
from vorge.ui.components import set_flash


def show_backup_panel() -> None:
    st.markdown("#### 自動バックアップ")
    st.write(
        f"アプリを開いたとき、1 日 1 回自動でバックアップを作り、直近 {backup.KEEP_DAYS} 日分を残します。"
    )
    st.caption(f"保存先:`{backup.backup_dir()}`")
    if st.button("💾 今すぐバックアップ"):
        path = backup.create_backup("manual")
        set_flash(f"バックアップを作りました:{path.name}")
        st.rerun()

    st.markdown("#### バックアップから元に戻す")
    backups = backup.list_backups()
    if not backups:
        st.caption("まだバックアップはありません。")
    for path in backups[:30]:
        c1, c2, c3 = st.columns([4, 2, 1.2], vertical_alignment="center")
        c1.write(path.name)
        c2.caption(f"{datetime.fromtimestamp(path.stat().st_mtime):%Y-%m-%d %H:%M} ・ "
                   f"{path.stat().st_size / 1024:.0f} KB")
        with c3.popover("元に戻す"):
            st.write(f"今のデータを **{path.name}** の状態に戻します。")
            st.caption("戻す前の状態も自動でバックアップするので、あとからやり直せます。")
            if st.button("元に戻す", key=f"restore_{path.name}", type="primary"):
                safety = backup.restore_backup(path)
                set_flash(f"元に戻しました(戻す前の状態:{safety.name})")
                st.rerun()

    st.markdown("#### 全データの書き出し・読み込み")
    st.write("語彙だけでなく、学習記録・作文・設定まで含めた全データを 1 つのファイル(JSON)にします。"
             "別の PC への引っ越しや、長期保存に使えます。")
    st.download_button(
        "📤 全データを書き出す",
        data=backup.export_all(),
        file_name=f"vorge_all_{datetime.now():%Y%m%d_%H%M}.json",
        mime="application/json",
    )
    with st.expander("📥 全データを読み込む(今のデータを置き換えます)"):
        uploaded = st.file_uploader("書き出した JSON ファイル", type=["json"], key="import_all_file")
        agreed = st.checkbox("今のデータがファイルの内容に置き換わることを理解しました", key="import_all_ok")
        st.caption("置き換える前の状態は自動でバックアップします。")
        if st.button("読み込む", type="primary", disabled=not (uploaded and agreed)):
            try:
                safety = backup.import_all(uploaded.getvalue())
            except (ValueError, KeyError) as e:
                st.error(f"読み込めませんでした:{e}")
            else:
                set_flash(f"全データを読み込みました(読み込む前の状態:{safety.name})")
                st.rerun()
    st.caption(f"DB ファイル:`{config.DB_PATH}`")
