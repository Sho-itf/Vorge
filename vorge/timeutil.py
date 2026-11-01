"""「今日」の区切り(1 日の始まりの時刻)を扱うモジュール。

夜中の 0 時ではなく、朝 4 時(設定で変更可)に日付が切り替わるものとして扱う。
例:深夜 1 時の学習は「前の日」の学習として数える。

アプリ起動時に app.py が設定を読み込んで set_day_start_hour() を呼ぶ。
"""

from datetime import date, datetime, timedelta

DEFAULT_DAY_START_HOUR = 4
SETTING_KEY = "day_start_hour"

_day_start_hour = DEFAULT_DAY_START_HOUR


def set_day_start_hour(hour: int) -> None:
    global _day_start_hour
    if not 0 <= int(hour) <= 12:
        raise ValueError("1 日の始まりの時刻は 0〜12 時の範囲で指定してください。")
    _day_start_hour = int(hour)


def day_start_hour() -> int:
    return _day_start_hour


def logical_date(moment: datetime) -> date:
    """日時が「どの日の学習か」。区切り時刻より前なら前日になる。"""
    return (moment - timedelta(hours=_day_start_hour)).date()


def today(now: datetime | None = None) -> date:
    return logical_date(now or datetime.now())


def sql_date(column: str) -> str:
    """SQL で、日時の列を「どの日の学習か」に変換する式。例:date(studied_at, '-4 hours')。

    column にはプログラム内の固定の列名だけを渡す(ユーザー入力は渡さない)。
    """
    return f"date({column}, '-{_day_start_hour} hours')"
