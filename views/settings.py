"""設定画面:「今日」の区切り時刻など、アプリ全体の設定。"""

import streamlit as st

from vorge import timeutil
from vorge.settings import set_setting
from vorge.ui.components import set_flash

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
