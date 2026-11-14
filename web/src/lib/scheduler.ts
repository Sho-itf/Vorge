// 間隔反復(次にいつ復習するか)の計算。Python 版(vorge/flashcard/scheduler.py)と同じ FSRS の設定。
//
// 回答の 4 段階と FSRS の評価の対応:
//   不正解 → Again / 自信がない → Hard / 正解 → Good / 簡単 → Easy
// 日単位で復習するので、分単位の学習ステップは使わない。

import { createEmptyCard, fsrs, Rating, type Card, type FSRS, type Grade } from "ts-fsrs";
import { addDays, daysBetween, logicalDate } from "./day.ts";

export const RESULTS = ["wrong", "unsure", "correct", "easy"] as const; // キーボードの 1〜4
export type Result = (typeof RESULTS)[number];
export const RESULT_LABELS: Record<Result, string> = {
  wrong: "不正解",
  unsure: "自信がない",
  correct: "正解",
  easy: "簡単",
};
export const RESULT_ICONS: Record<Result, string> = { wrong: "❌", unsure: "🤔", correct: "✅", easy: "🌟" };
export const CORRECT_RESULTS: readonly Result[] = ["correct", "easy"];
const RATINGS: Record<Result, Grade> = {
  wrong: Rating.Again,
  unsure: Rating.Hard,
  correct: Rating.Good,
  easy: Rating.Easy,
};

export const MODES = ["word_to_meaning", "meaning_to_word", "cloze"] as const;
export type Mode = (typeof MODES)[number];
export const MODE_LABELS: Record<Mode, string> = {
  word_to_meaning: "語彙 → 意味",
  meaning_to_word: "意味 → 語彙",
  cloze: "例文の穴埋め → 語彙",
};

/** 保存用のカード(日時は文字列)。 */
export type StoredCard = Omit<Card, "due" | "last_review"> & { due: string; last_review?: string };

function makeScheduler(enableFuzz: boolean): FSRS {
  return fsrs({ learning_steps: [], relearning_steps: [], maximum_interval: 3650, enable_fuzz: enableFuzz });
}

let scheduler = makeScheduler(true);

/** 間隔の「ゆらぎ」の有無。テストでは切って結果を固定する。 */
export function configure(enableFuzz: boolean): void {
  scheduler = makeScheduler(enableFuzz);
}

export function toStored(card: Card): StoredCard {
  return { ...card, due: card.due.toISOString(), last_review: card.last_review?.toISOString() };
}

export function fromStored(stored: StoredCard | null | undefined, now: Date): Card {
  if (!stored) return createEmptyCard(now);
  return {
    ...stored,
    due: new Date(stored.due),
    last_review: stored.last_review ? new Date(stored.last_review) : undefined,
  };
}

export interface ReviewOutcome {
  card: StoredCard;
  /** 次回復習日(「今日」の区切りで数えた日付 YYYY-MM-DD) */
  due: string;
  /** 今日から次回復習日までの日数 */
  interval: number;
}

/** 回答を反映した新しいカードと、次回復習日・間隔を返す。次回は少なくとも翌日以降。 */
export function review(stored: StoredCard | null | undefined, result: Result, now: Date): ReviewOutcome {
  const rating = RATINGS[result];
  if (rating === undefined) throw new Error(`不明な回答結果です: ${result}`);
  const card = scheduler.next(fromStored(stored, now), now, rating).card;
  const today = logicalDate(now);
  let due = logicalDate(card.due);
  if (due <= today) due = addDays(today, 1);
  return { card: toStored(card), due, interval: daysBetween(today, due) };
}

/** それぞれの回答をしたら、次の復習まで何日になるか(ボタンに表示する)。 */
export function preview(stored: StoredCard | null | undefined, now: Date): Record<Result, number> {
  return Object.fromEntries(RESULTS.map((r) => [r, review(stored, r, now).interval])) as Record<Result, number>;
}

/** 復習間隔の長さから、習得状況を 4 段階の言葉で表す。 */
export function masteryLabel(intervalDays: number | null | undefined): string {
  if (intervalDays == null) return "未学習";
  if (intervalDays < 7) return "学習中";
  if (intervalDays < 21) return "定着中";
  return "習得";
}

/** ボタンなどに出す「次はいつか」の表示。 */
export function intervalText(days: number): string {
  if (days === 1) return "明日";
  if (days < 60) return `${days}日後`;
  if (days < 365) return `約${Math.round(days / 30)}か月後`;
  return `約${(days / 365).toFixed(1)}年後`;
}
