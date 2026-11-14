// 語彙ライブラリ画面:検索・一覧・詳細(ポップアップ)。Python 版の views/library.py と同じ構成。
// 語彙は CSV から作るので、Web 版には「新規追加」「編集」「削除」はない。

import type { App } from "../app.ts";
import { formatDateTime } from "../lib/day.ts";
import { MASTERY_LEVELS, searchVocabs, senseNumber, SORT_OPTIONS, synonymGroup, type LibraryQuery, type SortOption } from "../lib/library.ts";
import { masteryLabel, MODE_LABELS, RESULT_LABELS } from "../lib/scheduler.ts";
import type { Vocab } from "../lib/vocab.ts";
import { esc, highlight, ruby } from "./dom.ts";
import { senseBadge, stars, vocabCardHtml, vocabLink } from "./vocabCard.ts";

// 検索条件と今のページは画面を移動しても残す
const query: LibraryQuery = { keyword: "", categories: [], mastery: [], difficulty: [1, 5], sort: "ID順" };
let page = 0;

// 一覧に追加で表示する項目と 1 ページの件数(「表示する項目」メニュー。このブラウザに保存して次回も使う)
const VIEW_KEY = "vorge-web-library-view";
const view = { showDifficulty: true, showCategory: false, showMastery: false, pageSize: 25 };
try {
  Object.assign(view, JSON.parse(localStorage.getItem(VIEW_KEY) ?? "{}"));
} catch {
  // 読めなければ初期値のまま
}
function saveView(): void {
  try {
    localStorage.setItem(VIEW_KEY, JSON.stringify(view));
  } catch {
    // 保存できなくても表示はできる
  }
}

/** 一覧の列(見出し, 幅の比率)。「表示する項目」の設定で列が増える。 */
function listColumns(): [string, number][] {
  const columns: [string, number][] = [["語彙", 1.4], ["意味", 2.6], ["例文", 3.6]];
  if (view.showDifficulty) columns.push(["難易度", 1.1]);
  if (view.showCategory) columns.push(["カテゴリ", 1.3]);
  if (view.showMastery) columns.push(["習得状況", 0.8]);
  columns.push(["", 0.8]); // 「詳細」ボタン
  return columns;
}

/** 複数選べるプルダウン(選ばなければ「すべて」)。 */
function multiselect(id: string, label: string, options: string[], selected: string[]): string {
  const summary = selected.length ? selected.join("、") : "すべて";
  return `<div class="vg-field"><span class="vg-field-label">${label}</span>
    <details class="vg-select" id="${id}"><summary title="${esc(summary)}">${esc(summary)}</summary>
      <div class="vg-menu">${options.map((o) => `<label><input type="checkbox" value="${esc(o)}" ${selected.includes(o) ? "checked" : ""}/> ${esc(o)}</label>`).join("")}</div>
    </details></div>`;
}

export function renderLibrary(root: HTMLElement, app: App, openKey: string | null): void {
  // 一覧がすでに表示されていれば、ポップアップだけ切り替える(検索条件やスクロール位置を保つため)
  if (root.dataset.page !== "library") {
    root.dataset.page = "library";
    renderPage(root, app);
  }
  showDialog(root, app, openKey);
}

function renderPage(root: HTMLElement, app: App): void {
  root.innerHTML = `
    <h1 class="vg-title">語彙ライブラリ</h1>
    <div class="vg-tabs"><span class="active">🔍 一覧・検索</span></div>
    <div class="vg-filters">
      <div class="vg-field"><label class="vg-field-label" for="kw">キーワード</label>
        <input type="search" id="kw" placeholder="語彙・読み・意味・例文など(スペースで AND 検索)" value="${esc(query.keyword)}" /></div>
      ${multiselect("cat", "カテゴリ", app.categories, query.categories)}
      ${multiselect("mastery", "習得状況", MASTERY_LEVELS, query.mastery)}
      <div class="vg-field"><span class="vg-field-label">難易度</span>
        <div class="vg-range">
          <div class="vg-range-vals"><span id="dlo-v"></span><span id="dhi-v"></span></div>
          <div class="vg-range-track"><div class="vg-range-fill" id="dfill"></div>
            <input type="range" id="dlo" min="1" max="5" step="1" value="${query.difficulty[0]}" aria-label="難易度の下限" />
            <input type="range" id="dhi" min="1" max="5" step="1" value="${query.difficulty[1]}" aria-label="難易度の上限" /></div>
        </div></div>
      <div class="vg-field"><label class="vg-field-label" for="sort">並び順</label>
        <select id="sort">${SORT_OPTIONS.map((s) => `<option ${s === query.sort ? "selected" : ""}>${s}</option>`).join("")}</select></div>
    </div>
    <div class="vg-info">
      <span class="vg-caption" id="count"></span>
      <details class="vg-popover" id="viewmenu"><summary>⚙️ 表示する項目</summary>
        <div class="vg-menu">
          <p class="vg-caption">一覧に追加で表示する項目</p>
          <label><input type="checkbox" data-view="showDifficulty" ${view.showDifficulty ? "checked" : ""}/> 難易度</label>
          <label><input type="checkbox" data-view="showCategory" ${view.showCategory ? "checked" : ""}/> カテゴリ</label>
          <label><input type="checkbox" data-view="showMastery" ${view.showMastery ? "checked" : ""}/> 習得状況</label>
          <label class="vg-slider">1 ページの件数 <b id="ps-v">${view.pageSize}</b>
            <input type="range" id="ps" min="1" max="100" value="${view.pageSize}" /></label>
        </div>
      </details>
    </div>
    <div id="results"></div>
    <dialog class="vg-dialog" id="detail"></dialog>`;

  const results = root.querySelector<HTMLDivElement>("#results")!;
  const draw = () => drawResults(results, root, app);
  // 絞り込み条件が変わったら 1 ページ目に戻す
  const changed = () => {
    page = 0;
    draw();
  };

  root.querySelector<HTMLInputElement>("#kw")!.addEventListener("input", (e) => {
    query.keyword = (e.target as HTMLInputElement).value;
    changed();
  });
  for (const [id, field] of [["cat", "categories"], ["mastery", "mastery"]] as const) {
    const box = root.querySelector<HTMLDetailsElement>(`#${id}`)!;
    box.addEventListener("change", () => {
      query[field] = [...box.querySelectorAll<HTMLInputElement>("input:checked")].map((c) => c.value);
      const text = query[field].length ? query[field].join("、") : "すべて";
      box.querySelector("summary")!.textContent = text;
      box.querySelector("summary")!.title = text;
      changed();
    });
  }

  const lo = root.querySelector<HTMLInputElement>("#dlo")!;
  const hi = root.querySelector<HTMLInputElement>("#dhi")!;
  const syncRange = () => {
    const a = Number(lo.value);
    const b = Number(hi.value);
    query.difficulty = [Math.min(a, b), Math.max(a, b)];
    root.querySelector("#dlo-v")!.textContent = String(query.difficulty[0]);
    root.querySelector("#dhi-v")!.textContent = String(query.difficulty[1]);
    const fill = root.querySelector<HTMLDivElement>("#dfill")!;
    fill.style.left = `${((query.difficulty[0] - 1) / 4) * 100}%`;
    fill.style.right = `${100 - ((query.difficulty[1] - 1) / 4) * 100}%`;
    root.querySelector<HTMLSpanElement>("#dlo-v")!.style.left = fill.style.left;
    root.querySelector<HTMLSpanElement>("#dhi-v")!.style.left = `${((query.difficulty[1] - 1) / 4) * 100}%`;
  };
  lo.addEventListener("input", () => {
    syncRange();
    changed();
  });
  hi.addEventListener("input", () => {
    syncRange();
    changed();
  });
  syncRange();

  root.querySelector<HTMLSelectElement>("#sort")!.addEventListener("change", (e) => {
    query.sort = (e.target as HTMLSelectElement).value as SortOption;
    changed();
  });

  const menu = root.querySelector<HTMLDetailsElement>("#viewmenu")!;
  menu.querySelectorAll<HTMLInputElement>("[data-view]").forEach((c) =>
    c.addEventListener("change", () => {
      (view as Record<string, boolean | number>)[c.dataset.view!] = c.checked;
      saveView();
      draw();
    }),
  );
  menu.querySelector<HTMLInputElement>("#ps")!.addEventListener("input", (e) => {
    view.pageSize = Number((e.target as HTMLInputElement).value);
    menu.querySelector("#ps-v")!.textContent = String(view.pageSize);
    saveView();
    draw();
  });

  // プルダウン・メニューは外側を押したら閉じる
  root.addEventListener("click", (e) => {
    root.querySelectorAll<HTMLDetailsElement>("details.vg-select[open], details.vg-popover[open]").forEach((d) => {
      if (!d.contains(e.target as Node)) d.open = false;
    });
  });

  const dialog = root.querySelector<HTMLDialogElement>("#detail")!;
  dialog.addEventListener("close", () => {
    // ポップアップを閉じたら URL を一覧に戻す(hashchange を起こさないので一覧は描き直さない)
    if (location.hash.startsWith("#/library/")) history.replaceState(null, "", "#/library");
  });
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) dialog.close(); // 背景を押したら閉じる
  });
  draw();
}

function pagerHtml(pageCount: number, position: string): string {
  if (pageCount <= 1) return "";
  return `<div class="vg-pager">
    <button data-pager="prev" id="prev-${position}" ${page === 0 ? "disabled" : ""}>« 前へ</button>
    <span>${page + 1} / ${pageCount} ページ</span>
    <button data-pager="next" id="next-${position}" ${page >= pageCount - 1 ? "disabled" : ""}>次へ »</button></div>`;
}

function rowHtml(app: App, v: Vocab, columns: [string, number][]): string {
  const more = v.examples.length > 2 ? `<div class="vg-list-ex vg-muted">ほか ${v.examples.length - 2} 件</div>` : "";
  const examples = v.examples.slice(0, 2).map((x) => `<div class="vg-list-ex">${highlight(x, v.word)}</div>`).join("") + more;
  const cells = [
    `<div class="vg-list-word">${ruby(v.word, v.reading)}${senseBadge(app, v)}</div>`,
    `<div class="vg-list-text">${esc(v.meaning)}</div>`,
    examples || `<div class="vg-list-ex vg-muted">—</div>`,
  ];
  for (const [name] of columns.slice(3, -1)) {
    if (name === "難易度") cells.push(`<span class="vg-stars vg-list-stars">${stars(v.difficulty)}</span>`);
    else if (name === "カテゴリ") cells.push(`<span class="vg-badge">${esc(v.category)}</span>`);
    else if (name === "習得状況") cells.push(`<div class="vg-list-ex">${masteryLabel(app.store.get(v.key)?.interval)}</div>`);
  }
  cells.push(`<a class="vg-tertiary" href="#/library/${encodeURIComponent(v.key)}">詳細</a>`);
  return `<div class="vg-row" style="${gridStyle(columns)}">${cells.map((c) => `<div class="vg-cell">${c}</div>`).join("")}</div>`;
}

function gridStyle(columns: [string, number][]): string {
  return `grid-template-columns:${columns.map(([name, w]) => (name ? `minmax(0, ${w}fr)` : "3.5em")).join(" ")}`;
}

function drawResults(results: HTMLElement, root: HTMLElement, app: App): void {
  const hits = searchVocabs(app.vocabs, app.store.data.reviews, query);
  root.querySelector("#count")!.textContent = `${hits.length} 件 / 全 ${app.vocabs.length} 件 ・ 「詳細」で例文以外の情報が見られます`;
  if (!hits.length) {
    results.innerHTML = `<p class="vg-alert">条件に一致する語彙がありません。キーワードや絞り込み条件を変えてみてください。</p>`;
    return;
  }
  const pageCount = Math.ceil(hits.length / view.pageSize);
  page = Math.min(page, pageCount - 1);
  const items = hits.slice(page * view.pageSize, (page + 1) * view.pageSize);
  const columns = listColumns();
  results.innerHTML = `${pagerHtml(pageCount, "top")}
    <div class="vg-list">
      <div class="vg-row vg-list-head" style="${gridStyle(columns)}">${columns.map(([name]) => `<div class="vg-cell">${name}</div>`).join("")}</div>
      ${items.map((v) => rowHtml(app, v, columns)).join("")}
    </div>
    ${pagerHtml(pageCount, "bottom")}`;
  results.querySelectorAll<HTMLButtonElement>("[data-pager]").forEach((b) =>
    b.addEventListener("click", () => {
      page += b.dataset.pager === "next" ? 1 : -1;
      drawResults(results, root, app);
      if (b.id.endsWith("bottom")) results.scrollIntoView({ block: "start" });
    }),
  );
}

// ============ 詳細ポップアップ ============

/** 同じ語の別の意味へのリンクと、登録済みの類義語との使い分けの比較。 */
function relationsHtml(app: App, v: Vocab): string {
  let out = "";
  const others = (app.byWord.get(v.word) ?? []).filter((k) => k !== v.key);
  if (others.length) {
    const links = others
      .map((k) => app.byKey.get(k)!)
      .map((o) => vocabLink(`${String.fromCodePoint(0x2460 + (senseNumber(o, app.byWord) ?? 1) - 1)} ${o.meaning.slice(0, 24)}`, o.key))
      .join("");
    out += `<p class="vg-label">この語のほかの意味</p>${links}`;
  }
  const group = synonymGroup(v, app.vocabs, app.byWord, app.byKey);
  if (group.length > 1) {
    const rows = group
      .map(
        (o) => `<tr><td class="vg-list-word">${ruby(o.word, o.reading)}</td>
          <td>${esc(o.meaning)}${o.nuance ? `<div class="vg-list-ex">ニュアンス:${esc(o.nuance)}</div>` : ""}</td>
          <td class="vg-list-ex">${highlight(o.examples[0] ?? "", o.word)}</td></tr>`,
      )
      .join("");
    out += `<details class="vg-expander"><summary>🔀 似た語との使い分け(${group.length} 語)</summary>
      <table class="vg-compare"><tr><th>語彙</th><th>意味・ニュアンス</th><th>例文</th></tr>${rows}</table></details>`;
  }
  return out;
}

/** 語彙 1 件の「学習の記録」(Web 版で記録するのは単語カードだけ)。 */
function learningRecordHtml(app: App, v: Vocab): string {
  const logs = app.store.data.log.filter((e) => e.key === v.key).reverse();
  if (!logs.length) return `<p class="vg-caption">まだ記録はありません。単語カードで学習すると、ここに記録が残ります。</p>`;
  const lines = logs
    .slice(0, 10)
    .map((e) => `<li>${esc(formatDateTime(new Date(e.at)))} ・ ${MODE_LABELS[e.mode]} ・ ${RESULT_LABELS[e.result]} → 次回 ${esc(e.next)}</li>`)
    .join("");
  return `<p><b>🃏 単語カード</b>(${logs.length} 回)</p><ul>${lines}</ul>`;
}

function showDialog(root: HTMLElement, app: App, key: string | null): void {
  const dialog = root.querySelector<HTMLDialogElement>("#detail")!;
  if (!key) {
    if (dialog.open) dialog.close();
    return;
  }
  const v = app.byKey.get(key);
  dialog.innerHTML = `<div class="vg-dialog-head"><h2>語彙の詳細</h2><button class="vg-close" aria-label="閉じる">✕</button></div>
    ${v
      ? `${vocabCardHtml(app, v, { linked: true })}${relationsHtml(app, v)}
        <details class="vg-expander"><summary>📒 学習の記録</summary>${learningRecordHtml(app, v)}</details>`
      : `<p class="vg-alert">この語彙は見つかりませんでした。</p>`}`;
  dialog.querySelector(".vg-close")!.addEventListener("click", () => dialog.close());
  if (!dialog.open) dialog.showModal();
  dialog.scrollTop = 0;
}
