// ホーム画面:今日の学習(と 1 日の目標)・連続学習日数・今日の一語・習得状況・バックアップの注意。

import type { App } from "../app.ts";
import {
  BACKUP_REMIND_DAYS,
  daysSinceBackup,
  MASTERY_ORDER,
  masteryCounts,
  streak,
  todayPlan,
  wordOfDay,
} from "../lib/daily.ts";
import { logicalDate } from "../lib/day.ts";
import { buildQueue } from "../lib/queue.ts";
import { esc, highlight, ruby, vocabHref } from "./dom.ts";
import { startFlashcard } from "./flashcard.ts";

const ALL = { categories: [], difficulty: [1, 5] as [number, number] };
const MORE_COUNT = 5; // 「もう少し覚える」で出す新しい語の数

function bar(done: number, total: number): string {
  const pct = total ? Math.min(100, (done / total) * 100) : 0;
  return `<div class="home-bar"><div style="width:${pct}%"></div></div>`;
}

export function renderHome(root: HTMLElement, app: App): void {
  const today = logicalDate(new Date());
  const { store } = app;
  const states = store.data.reviews;
  const plan = todayPlan(app.vocabs, states, store.data.log, today, store.settings.dailyGoal);
  const days = streak(store.data.log, today);
  const word = wordOfDay(app.vocabs, today);
  const counts = masteryCounts(app.vocabs, states);
  const sinceBackup = daysSinceBackup(store.data, today);
  const reviewTotal = plan.reviewed + plan.dueRemaining;

  const status = plan.done
    ? `<p class="home-done">🎉 今日の分は完了しました!</p>`
    : `<p class="muted">復習 ${plan.dueRemaining} 語 + 新しい語 ${plan.newRemaining} 語 = ${plan.dueRemaining + plan.newRemaining} 枚</p>`;

  root.innerHTML = `
    <div class="home-head">
      <h1>ホーム</h1>
      ${days ? `<span class="home-streak" title="1 日 1 回でも回答した日が続いている日数">🔥 ${days}日連続</span>` : ""}
    </div>

    <section class="card">
      <h2>今日の学習</h2>
      <div class="home-row"><span>復習</span>${bar(plan.reviewed, reviewTotal)}
        <span class="home-num">${reviewTotal ? `残り ${plan.dueRemaining} 語` : "予定なし"}</span></div>
      <div class="home-row"><span>新しい語</span>${bar(plan.learnedNew, plan.goal)}
        <span class="home-num">${plan.learnedNew} / ${plan.goal} 語</span></div>
      ${status}
      <button class="primary big" id="start">${plan.done ? "▶ もう少し覚える" : "▶ 今日の学習をはじめる"}</button>
      <details class="home-goal"><summary>1 日の目標を変える</summary>
        <label>新しく覚える語の数 <input type="number" id="goal" min="0" max="100" step="1" value="${plan.goal}" /> 語</label>
        <p class="muted">復習日が来た語は、目標とは別に全部出題されます。</p>
      </details>
    </section>

    ${word ? `<section class="card">
      <h2>今日の一語</h2>
      <p class="home-word">${ruby(word.word, word.reading)}</p>
      <p>${esc(word.meaning)}</p>
      ${word.examples[0] ? `<p class="muted">・${highlight(word.examples[0], word.word)}</p>` : ""}
      <a href="${vocabHref(word.key)}">詳細を見る →</a>
    </section>` : ""}

    <section class="card">
      <h2>習得状況(${app.vocabs.length} 語)</h2>
      <div class="home-stack">${MASTERY_ORDER.map((m) => counts[m] ? `<div class="s-${m}" style="flex:${counts[m]}" title="${m} ${counts[m]} 語"></div>` : "").join("")}</div>
      <div class="home-legend">${MASTERY_ORDER.map((m) => `<span><i class="s-${m}"></i>${m} <b>${counts[m]}</b></span>`).join("")}</div>
    </section>

    ${sinceBackup !== null && sinceBackup >= BACKUP_REMIND_DAYS ? `<a class="card home-backup" href="#/data">
      💾 ${store.data.lastExportAt ? `最後の書き出しから ${sinceBackup} 日たちました。` : "まだ記録を書き出したことがありません。"}
      記録はこのブラウザの中にしかないので、ときどき書き出しておきましょう →</a>` : ""}`;

  root.querySelector("#start")!.addEventListener("click", () => {
    const s = store.settings;
    const newLimit = plan.done ? MORE_COUNT : plan.newRemaining;
    const queue = buildQueue(app.vocabs, store.data.reviews, logicalDate(new Date()), newLimit, ALL, s.shuffle);
    if (!queue.length) {
      root.querySelector(".home-done")?.replaceChildren("🎉 まだ学習していない語はもうありません。");
      return;
    }
    startFlashcard(queue, s.mode, s.input);
  });
  root.querySelector<HTMLInputElement>("#goal")!.addEventListener("change", (e) => {
    const n = Math.round(Number((e.target as HTMLInputElement).value));
    store.updateSettings({ dailyGoal: Number.isFinite(n) ? Math.min(Math.max(n, 0), 100) : 10 });
    renderHome(root, app);
    root.querySelector<HTMLDetailsElement>(".home-goal")!.open = true;
  });
}
