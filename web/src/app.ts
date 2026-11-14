// アプリ全体で使うデータ(語彙の一覧と学習の記録)。

import { RecordStore } from "./lib/store.ts";
import type { Vocab } from "./lib/vocab.ts";

export interface App {
  vocabs: Vocab[];
  byKey: Map<string, Vocab>;
  /** 語 → その語の鍵の一覧(同じ語で意味違いが複数あれば複数) */
  byWord: Map<string, string[]>;
  categories: string[];
  store: RecordStore;
  builtAt: string;
}

export async function loadApp(): Promise<App> {
  const res = await fetch("./vocab.json", { cache: "no-cache" });
  if (!res.ok) throw new Error(`語彙データを読み込めませんでした(${res.status})`);
  const { vocabs, builtAt } = (await res.json()) as { vocabs: Vocab[]; builtAt: string };
  const byWord = new Map<string, string[]>();
  for (const v of vocabs) byWord.set(v.word, [...(byWord.get(v.word) ?? []), v.key]);
  return {
    vocabs,
    byKey: new Map(vocabs.map((v) => [v.key, v])),
    byWord,
    categories: [...new Set(vocabs.map((v) => v.category))],
    store: new RecordStore(window.localStorage),
    builtAt,
  };
}
