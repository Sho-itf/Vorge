// 語彙の詳細カード(ライブラリの詳細画面と、単語カードの答え面で使う)。

import type { App } from "../app.ts";
import { intervalText, masteryLabel, RESULT_LABELS } from "../lib/scheduler.ts";
import type { Vocab } from "../lib/vocab.ts";
import { esc, highlight, ruby, vocabHref } from "./dom.ts";

/** 類義語・対義語を、登録済みの語ならリンクにして並べる。 */
function termLinks(app: App, terms: string[], self: Vocab): string {
  return terms
    .map((t) => {
      const keys = app.byWord.get(t)?.filter((k) => k !== self.key);
      return keys?.length ? `<a class="chip link" href="${vocabHref(keys[0])}">${esc(t)}</a>` : `<span class="chip">${esc(t)}</span>`;
    })
    .join("");
}

/** 片方にしか類義語として書いていなくても、つながっているものとして扱う。 */
function reverseSynonyms(app: App, v: Vocab): Vocab[] {
  return app.vocabs.filter((o) => o.key !== v.key && o.synonyms.includes(v.word) && !v.synonyms.includes(o.word));
}

function recordHtml(app: App, v: Vocab): string {
  const s = app.store.get(v.key);
  if (!s) return `<p class="muted">まだ単語カードで学習していません。</p>`;
  return `
    <dl class="record">
      <div><dt>習得状況</dt><dd><span class="badge m-${masteryLabel(s.interval)}">${masteryLabel(s.interval)}</span></dd></div>
      <div><dt>次回の復習</dt><dd>${esc(s.next)}(間隔 ${esc(intervalText(s.interval))})</dd></div>
      <div><dt>回答</dt><dd>${s.count} 回(正解 ${s.correct} ・ 簡単 ${s.easy} ・ 自信がない ${s.unsure} ・ 不正解 ${s.wrong})</dd></div>
      <div><dt>前回</dt><dd>${esc(s.lastAt)}(${esc(RESULT_LABELS[s.last])})</dd></div>
    </dl>`;
}

export function vocabCardHtml(app: App, v: Vocab, opts: { showRecord?: boolean } = {}): string {
  const sense = (app.byWord.get(v.word)?.length ?? 0) > 1 ? `<span class="muted">(意味 ${esc(v.key.split("#")[1])})</span>` : "";
  const others = (app.byWord.get(v.word) ?? []).filter((k) => k !== v.key);
  const reverse = reverseSynonyms(app, v);
  const section = (title: string, body: string) => (body ? `<section><h3>${title}</h3>${body}</section>` : "");
  return `
    <article class="card vocab-card">
      <p class="meta">${esc(v.category)} ・ 難易度 ${"★".repeat(v.difficulty)}${"☆".repeat(5 - v.difficulty)}</p>
      <h2 class="vocab-word">${ruby(v.word, v.reading)} ${sense}</h2>
      <p class="meaning">${esc(v.meaning)}</p>
      ${section("例文", v.examples.length ? `<ul class="examples">${v.examples.map((e) => `<li>${highlight(e, v.word)}</li>`).join("")}</ul>` : "")}
      ${section("ニュアンス・使い方", v.nuance ? `<p>${esc(v.nuance)}</p>` : "")}
      ${section("類義語", v.synonyms.length || reverse.length ? `<div class="chips">${termLinks(app, v.synonyms, v)}${reverse.map((o) => `<a class="chip link" href="${vocabHref(o.key)}">${esc(o.word)}</a>`).join("")}</div>` : "")}
      ${section("対義語", v.antonyms.length ? `<div class="chips">${termLinks(app, v.antonyms, v)}</div>` : "")}
      ${section("よく一緒に使う言葉", v.collocations.length ? `<div class="chips">${v.collocations.map((c) => `<span class="chip">${esc(c)}</span>`).join("")}</div>` : "")}
      ${section("同じ語の別の意味", others.length ? `<div class="chips">${others.map((k) => `<a class="chip link" href="${vocabHref(k)}">${esc(app.byKey.get(k)?.meaning ?? k)}</a>`).join("")}</div>` : "")}
      ${opts.showRecord ? section("学習の記録", recordHtml(app, v)) : ""}
      <p class="dict">辞書で調べる:
        <a href="https://kotobank.jp/search?q=${encodeURIComponent(v.word)}" target="_blank" rel="noopener">コトバンク</a> ・
        <a href="https://www.weblio.jp/content/${encodeURIComponent(v.word)}" target="_blank" rel="noopener">Weblio</a>
      </p>
    </article>`;
}
