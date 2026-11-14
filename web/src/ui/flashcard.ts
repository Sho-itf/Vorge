// 単語カード:設定 → 出題(答えを確認して自己採点)→ 結果。

import type { App } from "../app.ts";
import { blanksFor, matchesWord, type Blank } from "../lib/blank.ts";
import { logicalDate } from "../lib/day.ts";
import { buildQueue, dueKeys, newKeys, Session, type Filter } from "../lib/queue.ts";
import {
  CORRECT_RESULTS,
  intervalText,
  masteryLabel,
  MODE_LABELS,
  MODES,
  preview,
  RESULT_ICONS,
  RESULT_LABELS,
  RESULTS,
  type Mode,
  type Result,
} from "../lib/scheduler.ts";
import type { Vocab } from "../lib/vocab.ts";
import { esc } from "./dom.ts";
import { vocabCardHtml } from "./vocabCard.ts";

// 出題中の状態は画面を移動しても残す(ライブラリを見てから戻って続きができる)
let session: Session | null = null;
let keyHandler: ((e: KeyboardEvent) => void) | null = null;

function setKeys(handler: ((e: KeyboardEvent) => void) | null): void {
  if (keyHandler) document.removeEventListener("keydown", keyHandler);
  keyHandler = handler;
  if (handler) document.addEventListener("keydown", handler);
}

export function leaveFlashcard(): void {
  setKeys(null);
}

/** ホームの「今日の学習をはじめる」から、設定画面を通らずに出題を始める。 */
export function startFlashcard(queue: string[], mode: Mode, input: boolean): void {
  session = new Session(queue, mode, mode !== "word_to_meaning" && input);
  location.hash = "#/cards";
}

export function renderFlashcard(root: HTMLElement, app: App): void {
  if (!session) renderSettings(root, app);
  else if (session.finished) renderSummary(root, app, session);
  else renderCard(root, app, session);
}

// ============ 設定画面 ============
function renderSettings(root: HTMLElement, app: App): void {
  setKeys(null);
  const s = app.store.settings;
  const today = logicalDate(new Date());
  const states = app.store.data.reviews;
  const filter: Filter = { categories: s.categories.filter((c) => app.categories.includes(c)), difficulty: s.difficulty };
  const due = dueKeys(app.vocabs, states, today, filter).length;
  const fresh = Math.min(s.newLimit, newKeys(app.vocabs, states, filter).length);
  const total = due + fresh;

  root.innerHTML = `
    <h1>単語カード</h1>
    <div class="stats">
      <div class="card stat"><span>今日の復習予定</span><b>${dueKeys(app.vocabs, states, today, { categories: [], difficulty: [1, 5] }).length} 語</b></div>
      <div class="card stat"><span>まだ学習していない</span><b>${newKeys(app.vocabs, states, { categories: [], difficulty: [1, 5] }).length} 語</b></div>
      <div class="card stat"><span>今日の回答数</span><b>${app.store.countAnswersOn(today)} 回</b></div>
    </div>
    <div class="card form">
      <h2>出題の設定</h2>
      <fieldset><legend>出題モード</legend>
        <div class="seg">${MODES.map((m) => `<label><input type="radio" name="mode" value="${m}" ${m === s.mode ? "checked" : ""}/><span>${esc(MODE_LABELS[m])}</span></label>`).join("")}</div>
      </fieldset>
      ${s.mode !== "word_to_meaning" ? `<label class="switch"><input type="checkbox" id="input" ${s.input ? "checked" : ""}/> 答えを入力してから確認する(読みのひらがなでも正解)</label>` : ""}
      <fieldset><legend>カテゴリ(選ばなければすべて)</legend>
        <div class="chips">${app.categories.map((c) => `<label class="chip toggle"><input type="checkbox" name="cat" value="${esc(c)}" ${filter.categories.includes(c) ? "checked" : ""}/><span>${esc(c)}</span></label>`).join("")}</div>
      </fieldset>
      <div class="row">
        <label>難易度 <select id="dmin">${[1, 2, 3, 4, 5].map((d) => `<option ${d === s.difficulty[0] ? "selected" : ""}>${d}</option>`).join("")}</select>
          〜 <select id="dmax">${[1, 2, 3, 4, 5].map((d) => `<option ${d === s.difficulty[1] ? "selected" : ""}>${d}</option>`).join("")}</select></label>
        <label>新しく覚える数 <input type="number" id="newLimit" min="0" max="100" step="5" value="${s.newLimit}" /></label>
        <label class="switch"><input type="checkbox" id="shuffle" ${s.shuffle ? "checked" : ""}/> 出題順をシャッフル</label>
      </div>
      <p>今回の出題:復習 <b>${due}</b> 枚 + 新規 <b>${fresh}</b> 枚 = <b>${total}</b> 枚</p>
      ${total === 0 ? `<p class="ok">🎉 この条件で今日出題する語彙はありません。新しく覚える数を増やすか、条件を変えてください。</p>` : ""}
      <button class="primary big" id="start" ${total === 0 ? "disabled" : ""}>▶ 学習をはじめる</button>
    </div>
    <details class="card"><summary>復習のタイミングのしくみ</summary>
      <p>復習日は <b>FSRS</b> という方式で、語彙ごとに「思い出せる確率が 90% まで下がる頃」に決めます。</p>
      <ul><li><b>簡単</b> → 間隔が大きく延びます</li><li><b>正解</b> → 間隔が延びます(何度も正解している語彙ほど大きく延びる)</li>
      <li><b>自信がない</b> → 少しだけ延びます</li><li><b>不正解</b> → すぐ(翌日〜数日後)にもう一度出題されます</li></ul>
      <p>間隔が 7 日以上で「定着中」、21 日以上で「習得」になります。1 日の区切りは朝 4 時です。</p>
    </details>`;

  // 設定を変えたら保存して描き直す(出題数の表示を更新するため)
  const update = (patch: Partial<typeof s>) => {
    app.store.updateSettings(patch);
    renderSettings(root, app);
  };
  root.querySelectorAll<HTMLInputElement>('input[name="mode"]').forEach((el) =>
    el.addEventListener("change", () => update({ mode: el.value as Mode })),
  );
  root.querySelector<HTMLInputElement>("#input")?.addEventListener("change", (e) => update({ input: (e.target as HTMLInputElement).checked }));
  root.querySelectorAll<HTMLInputElement>('input[name="cat"]').forEach((el) =>
    el.addEventListener("change", () =>
      update({ categories: [...root.querySelectorAll<HTMLInputElement>('input[name="cat"]:checked')].map((c) => c.value) }),
    ),
  );
  const dmin = root.querySelector<HTMLSelectElement>("#dmin")!;
  const dmax = root.querySelector<HTMLSelectElement>("#dmax")!;
  const onDifficulty = () => {
    const a = Number(dmin.value);
    const b = Number(dmax.value);
    update({ difficulty: [Math.min(a, b), Math.max(a, b)] });
  };
  dmin.addEventListener("change", onDifficulty);
  dmax.addEventListener("change", onDifficulty);
  root.querySelector<HTMLInputElement>("#newLimit")!.addEventListener("change", (e) => {
    const n = Math.round(Number((e.target as HTMLInputElement).value));
    update({ newLimit: Number.isFinite(n) ? Math.min(Math.max(n, 0), 100) : 10 });
  });
  root.querySelector<HTMLInputElement>("#shuffle")!.addEventListener("change", (e) => update({ shuffle: (e.target as HTMLInputElement).checked }));
  root.querySelector<HTMLButtonElement>("#start")!.addEventListener("click", () => {
    const queue = buildQueue(app.vocabs, app.store.data.reviews, logicalDate(new Date()), s.newLimit, filter, s.shuffle);
    session = new Session(queue, s.mode, s.mode !== "word_to_meaning" && s.input);
    renderFlashcard(root, app);
  });
}

// ============ 出題画面 ============
/** 穴埋めモードで使う例文の空欄。例文が無ければ null(そのカードは「意味 → 語彙」で出す)。 */
function clozeBlank(v: Vocab, pos: number): Blank | null {
  const blanks = blanksFor(v);
  return blanks.length ? blanks[pos % blanks.length] : null;
}

function frontHtml(app: App, v: Vocab, ss: Session): string {
  const state = app.store.get(v.key);
  const kind = ss.isRetry() ? "🔂 もう一度(さっき間違えた語彙)" : state ? `🔁 復習(${masteryLabel(state.interval)})` : "🆕 新しい語彙";
  const blank = ss.mode === "cloze" ? clozeBlank(v, ss.pos) : null;
  if (ss.mode === "word_to_meaning") {
    return `<div class="card flash"><p class="label">${esc(kind)} ・ この語彙の意味は?</p><p class="flash-text">${esc(v.word)}</p></div>`;
  }
  if (blank) {
    return `<div class="card flash"><p class="label">${esc(kind)} ・ 空欄に入る語彙は?</p>
      <p class="flash-text long">${esc(blank.before)}<span class="blank">　　　</span>${esc(blank.after)}</p>
      <p class="sub">意味:${esc(v.meaning)}</p></div>`;
  }
  return `<div class="card flash"><p class="label">${esc(kind)} ・ この意味の語彙は?</p>
    <p class="flash-text long">${esc(v.meaning)}</p><p class="sub">カテゴリ:${esc(v.category)}</p></div>`;
}

function renderCard(root: HTMLElement, app: App, ss: Session): void {
  const v = app.byKey.get(ss.current!);
  if (!v) {
    // CSV の更新で語彙が無くなっていたら飛ばす
    ss.advance();
    renderFlashcard(root, app);
    return;
  }
  const retry = ss.isRetry();
  const progress = `<div class="progress"><div style="width:${(ss.pos / ss.queue.length) * 100}%"></div></div>
    <p class="muted">${ss.pos + 1} / ${ss.queue.length} 枚目</p>`;
  const answersWithWord = ss.mode !== "word_to_meaning";

  if (!ss.revealed) {
    const inputForm = ss.input && answersWithWord;
    root.innerHTML = `${progress}${frontHtml(app, v, ss)}
      ${inputForm
        ? `<form id="typed" class="typed"><input id="answer" autocomplete="off" placeholder="語彙を入力(読みのひらがなでもOK)" />
            <div class="row"><button class="primary" type="submit">答え合わせ</button><button type="button" id="giveup">わからない</button></div></form>`
        : `<button class="primary big" id="reveal">答えを見る(Space)</button>`}
      <p><button class="link-btn" id="stop">中断して結果を見る</button></p>`;
    const reveal = (typed: string | null) => {
      if (typed !== null) {
        const blank = ss.mode === "cloze" ? clozeBlank(v, ss.pos) : null;
        ss.typed = typed || "(わからない)";
        ss.typedOk = Boolean(typed) && matchesWord(typed, v.word, v.reading, blank ? [blank.answer] : []);
      }
      ss.revealed = true;
      renderFlashcard(root, app);
    };
    if (inputForm) {
      const input = root.querySelector<HTMLInputElement>("#answer")!;
      input.focus();
      root.querySelector("#typed")!.addEventListener("submit", (e) => {
        e.preventDefault();
        reveal(input.value.trim());
      });
      root.querySelector("#giveup")!.addEventListener("click", () => reveal(""));
      setKeys(null);
    } else {
      root.querySelector("#reveal")!.addEventListener("click", () => reveal(null));
      setKeys((e) => {
        if ((e.key === " " || e.key === "Enter") && !e.repeat) {
          e.preventDefault();
          reveal(null);
        }
      });
    }
  } else {
    const days = retry ? null : preview(app.store.get(v.key)?.card, new Date());
    // 入力式で間違えたときは「不正解」、それ以外は「正解」を目立たせる
    const suggested: Result = ss.typed !== null && !ss.typedOk ? "wrong" : "correct";
    const typedMsg =
      ss.typed === null ? "" : ss.typedOk
        ? `<p class="ok">✅ 入力した答え「${esc(ss.typed)}」は正解です。</p>`
        : `<p class="ng">❌ 入力した答え:${esc(ss.typed)} / 正解:${esc(v.word)}</p>`;
    root.innerHTML = `${progress}${typedMsg}
      <p><b>思い出せましたか?</b><span class="muted hide-sm">(キーボードの 1〜4 でも選べます)</span></p>
      ${retry ? `<p class="muted">この回答は記録しません(復習日は 1 回目の回答で決まっています)。</p>` : ""}
      <div class="answers">${RESULTS.map((r, i) => `<button data-result="${r}" class="${r === suggested ? "primary" : ""}">
        <span>${RESULT_ICONS[r]} ${RESULT_LABELS[r]}</span>${days ? `<small>${intervalText(days[r])}</small>` : ""}<kbd>${i + 1}</kbd></button>`).join("")}</div>
      ${vocabCardHtml(app, v)}
      <p><button class="link-btn" id="stop">中断して結果を見る</button></p>`;
    const answer = (result: Result) => {
      if (retry) {
        ss.retryResults.push(result);
      } else {
        const state = app.store.recordAnswer(v.key, result, ss.mode);
        ss.results.push({ key: v.key, word: v.word, result, next: state.next, mastery: masteryLabel(state.interval) });
        if (result === "wrong") ss.addRetry(v.key);
      }
      ss.advance();
      renderFlashcard(root, app);
      window.scrollTo({ top: 0 });
    };
    root.querySelectorAll<HTMLButtonElement>("[data-result]").forEach((b) =>
      b.addEventListener("click", () => answer(b.dataset.result as Result)),
    );
    setKeys((e) => {
      const i = Number(e.key) - 1;
      if (i >= 0 && i < RESULTS.length && !e.repeat) answer(RESULTS[i]);
    });
  }
  root.querySelector("#stop")!.addEventListener("click", () => {
    ss.stop();
    renderFlashcard(root, app);
  });
}

// ============ 結果画面 ============
function renderSummary(root: HTMLElement, app: App, ss: Session): void {
  setKeys(null);
  const counts = Object.fromEntries(RESULTS.map((r) => [r, ss.results.filter((x) => x.result === r).length]));
  const retryOk = ss.retryResults.filter((r) => CORRECT_RESULTS.includes(r)).length;
  root.innerHTML = ss.results.length
    ? `<h1>🎉 おつかれさまでした!</h1>
      <div class="stats">${RESULTS.map((r) => `<div class="card stat"><span>${RESULT_ICONS[r]} ${RESULT_LABELS[r]}</span><b>${counts[r]} 語</b></div>`).join("")}</div>
      <div class="card"><table class="results"><thead><tr><th>語彙</th><th>結果</th><th>次回復習</th><th>習得状況</th></tr></thead>
      <tbody>${ss.results.map((x) => `<tr><td><a href="#/library/${encodeURIComponent(x.key)}">${esc(x.word)}</a></td><td>${RESULT_LABELS[x.result]}</td><td>${esc(x.next)}</td><td>${esc(x.mastery)}</td></tr>`).join("")}</tbody></table></div>
      ${ss.retryResults.length ? `<p class="muted">🔂 間違えた語彙のもう一度:${retryOk} / ${ss.retryResults.length} 語を思い出せました。</p>` : ""}
      <p class="muted">不正解の語彙は、近いうちにまた出題されます。</p>`
    : `<h1>単語カード</h1><p>回答した語彙はありませんでした。</p>`;
  const back = document.createElement("button");
  back.className = "primary big";
  back.textContent = "設定に戻る";
  back.addEventListener("click", () => {
    session = null;
    renderFlashcard(root, app);
  });
  const home = document.createElement("a");
  home.className = "home-link";
  home.href = "#/home";
  home.textContent = "🏠 ホームへ";
  home.addEventListener("click", () => {
    session = null;
  });
  root.append(back, home);
}
