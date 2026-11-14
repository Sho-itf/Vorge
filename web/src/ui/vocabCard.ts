// 語彙 1 件の詳細カード(Python 版の vorge/ui/components.py の vocab_card と同じ並び)。
// ライブラリの詳細ポップアップと、単語カードの答え面で使う。

import type { App } from "../app.ts";
import { senseNumber } from "../lib/library.ts";
import { masteryLabel } from "../lib/scheduler.ts";
import type { Vocab } from "../lib/vocab.ts";
import { esc, ruby, vocabHref } from "./dom.ts";

export function stars(level: number): string {
  return "★".repeat(level) + "☆".repeat(5 - level);
}

/** 同じ語が複数登録されているときの「①」「②」の印(意味違いの区別)。 */
export function senseBadge(app: App, v: Vocab): string {
  const n = senseNumber(v, app.byWord);
  return n ? `<span class="vg-sense" title="同じ語の ${n} 番目の意味">${String.fromCodePoint(0x2460 + n - 1)}</span>` : "";
}

/** 登録済みの語彙へのリンク(ライブラリでその語彙の詳細を開く)。 */
export function vocabLink(term: string, key: string): string {
  return `<a class="vg-chip vg-chip-link" href="${vocabHref(key)}">${esc(term)}</a>`;
}

function dictionaryLinks(word: string): string {
  const q = encodeURIComponent(word);
  return [
    ["コトバンク", `https://kotobank.jp/search?q=${q}`],
    ["Weblio", `https://www.weblio.jp/content/${q}`],
  ]
    .map(([name, url]) => `<a class="vg-dict" href="${url}" target="_blank" rel="noopener">📖 ${name}</a>`)
    .join("");
}

/**
 * 空の項目は表示しない。linked を true にすると、類義語・対義語のうち登録済みの語をリンクにする。
 */
export function vocabCardHtml(app: App, v: Vocab, opts: { linked?: boolean } = {}): string {
  const review = app.store.get(v.key);
  const label = (text: string) => `<p class="vg-label">${text}</p>`;
  const chips = (terms: string[]) =>
    terms
      .map((t) => {
        const key = opts.linked && t !== v.word ? app.byWord.get(t)?.[0] : undefined;
        return key ? vocabLink(t, key) : `<span class="vg-chip">${esc(t)}</span>`;
      })
      .join("");

  const parts = [
    '<div class="vg-card">',
    `<span class="vg-badge">${esc(v.category)}</span><span class="vg-badge vg-badge-sub">${masteryLabel(review?.interval)}</span>` +
      `<span class="vg-stars" title="難易度 ${v.difficulty}">${stars(v.difficulty)}</span>`,
    `<p class="vg-word">${ruby(v.word, v.reading)}${senseBadge(app, v)}</p>`,
    `<p class="vg-meaning">${esc(v.meaning)}</p>`,
  ];
  if (v.examples.length) {
    parts.push(label("例文"), ...v.examples.map((x) => `<p class="vg-text">・${esc(x)}</p>`));
  }
  if (v.nuance) parts.push(label("ニュアンス"), `<p class="vg-text">${esc(v.nuance)}</p>`);
  if (v.synonyms.length) parts.push(label("類義語"), `<div>${chips(v.synonyms)}</div>`);
  if (v.antonyms.length) parts.push(label("対義語"), `<div>${chips(v.antonyms)}</div>`);
  if (v.collocations.length) parts.push(label("コロケーション"), `<div>${v.collocations.map((t) => `<span class="vg-chip">${esc(t)}</span>`).join("")}</div>`);
  if (v.source) parts.push(label("出典"), `<p class="vg-text">${esc(v.source)}</p>`);
  if (review) {
    parts.push(
      label("学習状況"),
      `<p class="vg-text">次回復習 ${esc(review.next)}(間隔 ${review.interval}日) ・ 正解 ${review.correct + review.easy}` +
        ` / 自信なし ${review.unsure} / 不正解 ${review.wrong}</p>`,
    );
  }
  parts.push(`<p class="vg-dicts">${dictionaryLinks(v.word)}</p>`, "</div>");
  return parts.join("");
}
