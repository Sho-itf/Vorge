"""設定画面:「今日」の区切り時刻、1 日の目標など、アプリ全体の設定。"""

import socket

import streamlit as st

from vorge import daily, timeutil
from vorge.settings import set_setting
from vorge.ui.components import set_flash


def lan_address() -> str:
    """この PC の、家のネットワーク内での IP アドレス(分からなければ「この PC の IP アドレス」)。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 80))  # 実際には通信しない。使われる自分側のアドレスを調べるだけ
            return s.getsockname()[0]
    except OSError:
        return "この PC の IP アドレス"


st.title("設定")

with st.container(border=True):
    st.markdown("#### 1 日の始まりの時刻")
    st.write("この時刻に「今日」が切り替わります。夜ふかしして学習しても、前の日の学習として数えられます。")
    hour = st.selectbox(
        "1 日の始まり", list(range(0, 13)), index=timeutil.day_start_hour(),
        format_func=lambda h: f"{h}:00" + ("(真夜中)" if h == 0 else ""),
    )
    if hour != timeutil.day_start_hour():
        timeutil.set_day_start_hour(hour)
        set_setting(timeutil.SETTING_KEY, hour)
        set_flash(f"1 日の始まりを {hour}:00 にしました")
        st.rerun()
    st.caption(f"今は {timeutil.today():%Y-%m-%d} の学習として記録されます。")

with st.container(border=True):
    st.markdown("#### 1 日の目標(ホームの「今日の学習」)")
    st.write("復習は、復習日が来ている語彙をすべて行います。それ以外の目標をここで決めます"
             "(0 にするとメニューから外れます)。")
    current = daily.goals()
    for key, label in daily.GOAL_LABELS.items():
        value = st.number_input(label, min_value=0, max_value=200, value=current[key], step=1, key=f"goal_{key}")
        if value != current[key]:
            set_setting(key, int(value))
            set_flash("目標を保存しました")
            st.rerun()

with st.container(border=True):
    st.markdown("#### スマホ・タブレットから使う")
    st.write("この PC で Vorge を起動している間は、同じ Wi-Fi につながったスマホやタブレットのブラウザから開けます。")
    st.code(f"http://{lan_address()}:{st.get_option('server.port')}", language=None)
    st.caption("開けないときは、Windows のファイアウォールで Python の通信が「プライベート ネットワーク」で"
               "許可されているか確認してください。外出先からは開けません。")
