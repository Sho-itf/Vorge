// ホーム画面の集計:今日の学習の進み具合・連続学習日数・今日の一語・習得状況・バックアップの注意。

import { addDays, daysBetween, logicalDate } from "./day.ts";
import { dueKeys } from "./queue.ts";
import { masteryLabel } from "./scheduler.ts";
import type { LogEntry, RecordData, ReviewState } from "./store.ts";
import type { Vocab } from "./vocab.ts";

const ALL = { categories: [], difficulty: [1, 5] as [number, number] };

export interface TodayPlan {
  /** 今日すでに復習した語の数(今日はじめて学習した語は除く) */
  reviewed: number;
  /** まだ復習していない、復習日が来ている語の数 */
  dueRemaining: number;
  /** 今日はじめて学習した語の数 */
  learnedNew: number;
  goal: number;
  /** 目標まであと何語覚えるか */
  newRemaining: number;
  /** 今日やるべき分(復習と新しい語の目標)が終わったか */
  done: boolean;
}

/** その日(朝 4 時区切り)に「はじめて」学習した語。 */
export function newKeysOn(log: LogEntry[], day: string): Set<string> {
  const first = new Map<string, string>();
  for (const e of log) if (!first.has(e.key)) first.set(e.key, logicalDate(new Date(e.at)));
  return new Set([...first].filter(([, d]) => d === day).map(([k]) => k));
}

export function todayPlan(
  vocabs: Vocab[], states: Record<string, ReviewState>, log: LogEntry[], today: string, goal: number,
): TodayPlan {
  const learned = newKeysOn(log, today);
  const studiedToday = new Set(log.filter((e) => logicalDate(new Date(e.at)) === today).map((e) => e.key));
  const reviewed = [...studiedToday].filter((k) => !learned.has(k)).length;
  const dueRemaining = dueKeys(vocabs, states, today, ALL).length;
  const unstudied = vocabs.filter((v) => !states[v.key]).length;
  const newRemaining = Math.min(Math.max(goal - learned.size, 0), unstudied);
  return { reviewed, dueRemaining, learnedNew: learned.size, goal, newRemaining, done: dueRemaining === 0 && newRemaining === 0 };
}

/** 連続学習日数。今日まだ学習していなくても、昨日まで続いていればその日数を返す。 */
export function streak(log: LogEntry[], today: string): number {
  const days = new Set(log.map((e) => logicalDate(new Date(e.at))));
  let day = days.has(today) ? today : addDays(today, -1);
  let count = 0;
  while (days.has(day)) {
    count++;
    day = addDays(day, -1);
  }
  return count;
}

/** 日替わりの 1 語(同じ日なら何度開いても同じ語)。 */
export function wordOfDay(vocabs: Vocab[], day: string): Vocab | undefined {
  if (!vocabs.length) return undefined;
  let h = 2166136261;
  for (const ch of day) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return vocabs[(h >>> 0) % vocabs.length];
}

export const MASTERY_ORDER = ["習得", "定着中", "学習中", "未学習"] as const;

export function masteryCounts(vocabs: Vocab[], states: Record<string, ReviewState>): Record<string, number> {
  const counts: Record<string, number> = Object.fromEntries(MASTERY_ORDER.map((m) => [m, 0]));
  for (const v of vocabs) counts[masteryLabel(states[v.key]?.interval)]++;
  return counts;
}

export const BACKUP_REMIND_DAYS = 7;

/**
 * 最後に書き出してから(書き出したことがなければ最初に学習してから)何日たったか。
 * まだ何も学習していなければ null(注意を出す必要がない)。
 */
export function daysSinceBackup(data: RecordData, today: string): number | null {
  if (!data.log.length) return null;
  const since = data.lastExportAt ?? data.log[0].at;
  return daysBetween(logicalDate(new Date(since)), today);
}
