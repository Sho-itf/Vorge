// 学習の記録(復習状態・回答履歴・設定)。利用者のブラウザ内(localStorage)に保存する。
// 端末間の同期はしないので、書き出し/取り込み(JSON)でバックアップや引っ越しをする。

import { formatDateTime, logicalDate } from "./day.ts";
import { review, RESULTS, type Mode, type Result, type StoredCard } from "./scheduler.ts";

export const STORAGE_KEY = "vorge-web-v1";
export const BEFORE_IMPORT_KEY = "vorge-web-v1-before-import";
const FORMAT = "vorge-web-record";
const VERSION = 1;

export interface ReviewState {
  card: StoredCard;
  /** 今の復習間隔(日) */
  interval: number;
  /** 次回復習日 YYYY-MM-DD */
  next: string;
  count: number;
  wrong: number;
  unsure: number;
  correct: number;
  easy: number;
  last: Result;
  /** 最後に学習した日時(YYYY-MM-DD HH:MM) */
  lastAt: string;
}

export interface LogEntry {
  key: string;
  /** 回答した日時(ISO 形式) */
  at: string;
  mode: Mode;
  result: Result;
  interval: number;
  next: string;
}

export interface Settings {
  mode: Mode;
  categories: string[];
  difficulty: [number, number];
  newLimit: number;
  shuffle: boolean;
  input: boolean;
}

export const DEFAULT_SETTINGS: Settings = {
  mode: "word_to_meaning",
  categories: [],
  difficulty: [1, 5],
  newLimit: 10,
  shuffle: true,
  input: false,
};

export interface RecordData {
  format: typeof FORMAT;
  version: number;
  reviews: Record<string, ReviewState>;
  log: LogEntry[];
  settings: Settings;
}

function emptyData(): RecordData {
  return { format: FORMAT, version: VERSION, reviews: {}, log: [], settings: { ...DEFAULT_SETTINGS } };
}

/** localStorage と同じ形のもの(テストでは Map で代用する)。 */
export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

/** 取り込んだ JSON が記録として正しい形か確かめて、足りない項目は初期値で埋める。 */
export function parseRecord(text: string): RecordData {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new Error("JSON として読めませんでした。");
  }
  const obj = raw as Partial<RecordData> | null;
  if (!obj || typeof obj !== "object" || obj.format !== FORMAT) {
    throw new Error("Vorge(Web 版)の記録ファイルではありません。");
  }
  if (typeof obj.version !== "number" || obj.version > VERSION) {
    throw new Error("この記録ファイルは新しい版のもので、読み込めません。");
  }
  if (typeof obj.reviews !== "object" || obj.reviews === null || !Array.isArray(obj.log)) {
    throw new Error("記録ファイルの中身が壊れています。");
  }
  return {
    format: FORMAT,
    version: VERSION,
    reviews: obj.reviews,
    log: obj.log,
    settings: { ...DEFAULT_SETTINGS, ...(obj.settings ?? {}) },
  };
}

export class RecordStore {
  data: RecordData;
  private storage: KeyValueStorage;

  constructor(storage: KeyValueStorage) {
    this.storage = storage;
    const saved = storage.getItem(STORAGE_KEY);
    let data = emptyData();
    if (saved) {
      try {
        data = parseRecord(saved);
      } catch {
        // 壊れていても消さずに退避しておき、空の記録から始める
        storage.setItem(`${STORAGE_KEY}-broken-${Date.now()}`, saved);
      }
    }
    this.data = data;
  }

  private save(): void {
    this.storage.setItem(STORAGE_KEY, JSON.stringify(this.data));
  }

  get(key: string): ReviewState | undefined {
    return this.data.reviews[key];
  }

  get settings(): Settings {
    return this.data.settings;
  }

  updateSettings(patch: Partial<Settings>): void {
    this.data.settings = { ...this.data.settings, ...patch };
    this.save();
  }

  /** 回答を 1 件記録し、次回復習日を更新する。 */
  recordAnswer(key: string, result: Result, mode: Mode, now: Date = new Date()): ReviewState {
    if (!RESULTS.includes(result)) throw new Error(`不明な回答結果です: ${result}`);
    const current = this.get(key);
    const outcome = review(current?.card, result, now);
    const state: ReviewState = {
      card: outcome.card,
      interval: outcome.interval,
      next: outcome.due,
      count: (current?.count ?? 0) + 1,
      wrong: current?.wrong ?? 0,
      unsure: current?.unsure ?? 0,
      correct: current?.correct ?? 0,
      easy: current?.easy ?? 0,
      last: result,
      lastAt: formatDateTime(now),
    };
    state[result] += 1;
    this.data.reviews[key] = state;
    this.data.log.push({ key, at: now.toISOString(), mode, result, interval: outcome.interval, next: outcome.due });
    this.save();
    return state;
  }

  /** その日(朝 4 時区切り)の回答数。 */
  countAnswersOn(day: string): number {
    return this.data.log.filter((e) => logicalDate(new Date(e.at)) === day).length;
  }

  exportJson(): string {
    return JSON.stringify(this.data, null, 1);
  }

  /** 書き出した記録で今の記録を置き換える。置き換える前の記録は退避しておく。 */
  importJson(text: string): void {
    const data = parseRecord(text);
    this.storage.setItem(BEFORE_IMPORT_KEY, JSON.stringify(this.data));
    this.data = data;
    this.save();
  }
}
