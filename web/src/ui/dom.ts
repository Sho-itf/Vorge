// 画面づくりの小さな道具。

/** HTML に埋め込む文字列のエスケープ。CSV の内容は必ずこれを通してから表示する。 */
export function esc(text: string | number): string {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** 語彙の上に読みをふりがなとして載せた HTML。 */
export function ruby(word: string, reading: string): string {
  return reading && reading !== word ? `<ruby>${esc(word)}<rt>${esc(reading)}</rt></ruby>` : esc(word);
}

/** 文中に出てくる語彙を太字にした HTML。 */
export function highlight(text: string, word: string): string {
  const escaped = esc(text);
  return word ? escaped.split(esc(word)).join(`<b>${esc(word)}</b>`) : escaped;
}

export function vocabHref(key: string): string {
  return `#/library/${encodeURIComponent(key)}`;
}

/** 画面下に一瞬出るお知らせ。 */
export function toast(message: string): void {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  document.body.append(el);
  setTimeout(() => el.remove(), 2600);
}
