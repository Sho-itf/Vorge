// CSV の読み込み(RFC 4180 相当:"…" で囲んだ値の中のカンマ・改行・"" を扱う)。
// ビルド時のスクリプト(scripts/build-vocab.ts)から使う。

export function parseCsv(text: string): string[][] {
  const src = text.replace(/^﻿/, "");
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;

  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (quoted) {
      if (ch === '"') {
        if (src[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          quoted = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && src[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += ch;
    }
  }
  if (field !== "" || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  // 空行は除く
  return rows.filter((r) => r.some((v) => v.trim() !== ""));
}

/** 1 行目をヘッダーとして、各行を {列名: 値} にする。 */
export function csvRecords(text: string): Record<string, string>[] {
  const [header, ...rows] = parseCsv(text);
  if (!header) return [];
  const names = header.map((h) => h.trim());
  return rows.map((values) =>
    Object.fromEntries(names.map((name, i) => [name, (values[i] ?? "").trim()])),
  );
}
