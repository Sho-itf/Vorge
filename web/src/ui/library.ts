// 語彙ライブラリ:検索・絞り込み・一覧と、1 語の詳細。

import type { App } from "../app.ts";
import { masteryLabel } from "../lib/scheduler.ts";
import { esc, ruby, vocabHref } from "./dom.ts";
import { vocabCardHtml } from "./vocabCard.ts";

// 検索条件は画面を移動しても残す(詳細から戻ったときに同じ一覧を出すため)
const query = { text: "", category: "", difficulty: "", mastery: "" };
const MASTERY = ["未学習", "学習中", "定着中", "習得"];

export function renderLibrary(root: HTMLElement, app: App): void {
  root.innerHTML = `
    <h1>語彙ライブラリ</h1>
    <div class="card filters">
      <input type="search" id="q" placeholder="語彙・読み・意味で検索" value="${esc(query.text)}" />
      <div class="row">
        <select id="cat"><option value="">すべてのカテゴリ</option>${app.categories.map((c) => `<option ${c === query.category ? "selected" : ""}>${esc(c)}</option>`).join("")}</select>
        <select id="diff"><option value="">難易度:すべて</option>${[1, 2, 3, 4, 5].map((d) => `<option value="${d}" ${String(d) === query.difficulty ? "selected" : ""}>難易度 ${d}</option>`).join("")}</select>
        <select id="mastery"><option value="">習得状況:すべて</option>${MASTERY.map((m) => `<option ${m === query.mastery ? "selected" : ""}>${m}</option>`).join("")}</select>
      </div>
    </div>
    <p class="muted" id="count"></p>
    <ul class="vocab-list" id="list"></ul>`;

  const list = root.querySelector<HTMLUListElement>("#list")!;
  const count = root.querySelector<HTMLParagraphElement>("#count")!;

  const draw = () => {
    const q = query.text.trim().toLowerCase();
    const hits = app.vocabs.filter((v) => {
      const mastery = masteryLabel(app.store.get(v.key)?.interval);
      return (
        (!q || [v.word, v.reading, v.meaning].some((t) => t.toLowerCase().includes(q))) &&
        (!query.category || v.category === query.category) &&
        (!query.difficulty || String(v.difficulty) === query.difficulty) &&
        (!query.mastery || mastery === query.mastery)
      );
    });
    count.textContent = `${hits.length} / ${app.vocabs.length} 語`;
    list.innerHTML = hits
      .map((v) => {
        const mastery = masteryLabel(app.store.get(v.key)?.interval);
        return `<li><a href="${vocabHref(v.key)}">
          <span class="w">${ruby(v.word, v.reading)}</span>
          <span class="m">${esc(v.meaning)}</span>
          <span class="badge m-${mastery}">${mastery}</span>
        </a></li>`;
      })
      .join("");
  };

  const bind = (id: string, field: keyof typeof query, event: string) => {
    root.querySelector<HTMLInputElement | HTMLSelectElement>(`#${id}`)!.addEventListener(event, (e) => {
      query[field] = (e.target as HTMLInputElement).value;
      draw();
    });
  };
  bind("q", "text", "input");
  bind("cat", "category", "change");
  bind("diff", "difficulty", "change");
  bind("mastery", "mastery", "change");
  draw();
}

export function renderVocabDetail(root: HTMLElement, app: App, key: string): void {
  const v = app.byKey.get(key);
  if (!v) {
    root.innerHTML = `<p>語彙が見つかりませんでした。</p><a href="#/library">← ライブラリへ</a>`;
    return;
  }
  root.innerHTML = `<p><a href="#/library">← ライブラリへ</a></p>${vocabCardHtml(app, v, { showRecord: true })}`;
}
