// 「今日」の区切り。夜中の 0 時ではなく朝 4 時に日付が切り替わるものとして扱う
// (Python 版の vorge/timeutil.py と同じ)。日付は端末の時刻(ローカル時刻)で数える。

export const DAY_START_HOUR = 4;

function ymd(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** 日時が「どの日の学習か」(YYYY-MM-DD)。区切り時刻より前なら前日になる。 */
export function logicalDate(moment: Date): string {
  return ymd(new Date(moment.getTime() - DAY_START_HOUR * 3600_000));
}

/** YYYY-MM-DD に日数を足す。 */
export function addDays(day: string, days: number): string {
  const [y, m, d] = day.split("-").map(Number);
  return ymd(new Date(y, m - 1, d + days));
}

/** 2 つの日付(YYYY-MM-DD)の差(b − a、日数)。 */
export function daysBetween(a: string, b: string): number {
  const toUtc = (s: string) => {
    const [y, m, d] = s.split("-").map(Number);
    return Date.UTC(y, m - 1, d);
  };
  return Math.round((toUtc(b) - toUtc(a)) / 86400_000);
}

/** 画面に出す日時(YYYY-MM-DD HH:MM)。 */
export function formatDateTime(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${ymd(d)} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
