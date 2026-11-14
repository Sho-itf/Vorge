// 語彙ライブラリの検索・並び替え・関連語(Python 版の VocabRepository.search と relations.py に相当)。

import { masteryLabel } from "./scheduler.ts";
import type { ReviewState } from "./store.ts";
import type { Vocab } from "./vocab.ts";

export const SORT_OPTIONS = ["ID順", "読み順", "新しい順", "難易度(易→難)", "難易度(難→易)"] as const;
export type SortOption = (typeof SORT_OPTIONS)[number];
export const MASTERY_LEVELS = ["未学習", "学習中", "定着中", "習得"];

export interface LibraryQuery {
  /** スペース区切りで複数指定すると、すべてを含む語彙だけになる(AND 検索) */
  keyword: string;
  categories: string[];
  mastery: string[];
  difficulty: [number, number];
  sort: SortOption;
}

/** キーワードを探す項目(語彙・読み・意味・例文・ニュアンス・類義語・対義語・コロケーション・出典)。 */
function searchText(v: Vocab): string {
  return [v.word, v.reading, v.meaning, ...v.examples, v.nuance, ...v.synonyms, ...v.antonyms, ...v.collocations, v.source]
    .join("\n")
    .toLowerCase();
}

/** 条件に合う語彙を並び替えて返す。条件は AND で組み合わさる。 */
export function searchVocabs(vocabs: Vocab[], states: Record<string, ReviewState>, q: LibraryQuery): Vocab[] {
  const terms = q.keyword.toLowerCase().split(/\s+/).filter(Boolean);
  const hits = vocabs
    .map((v, index) => ({ v, index }))
    .filter(({ v }) => {
      if (v.difficulty < q.difficulty[0] || v.difficulty > q.difficulty[1]) return false;
      if (q.categories.length && !q.categories.includes(v.category)) return false;
      if (q.mastery.length && !q.mastery.includes(masteryLabel(states[v.key]?.interval))) return false;
      if (terms.length) {
        const text = searchText(v);
        if (!terms.every((t) => text.includes(t))) return false;
      }
      return true;
    });

  const byId = (a: { index: number }, b: { index: number }) => a.index - b.index;
  const compare: Record<SortOption, (a: { v: Vocab; index: number }, b: { v: Vocab; index: number }) => number> = {
    "ID順": byId,
    "読み順": (a, b) => (a.v.reading || a.v.word).localeCompare(b.v.reading || b.v.word, "ja") || byId(a, b),
    "新しい順": (a, b) => b.index - a.index,
    "難易度(易→難)": (a, b) => a.v.difficulty - b.v.difficulty || byId(a, b),
    "難易度(難→易)": (a, b) => b.v.difficulty - a.v.difficulty || byId(a, b),
  };
  return hits.sort(compare[q.sort] ?? byId).map(({ v }) => v);
}

/** 同じ語が複数登録されているとき、その中で何番目か(1 始まり)。1 つだけなら null。 */
export function senseNumber(v: Vocab, byWord: Map<string, string[]>): number | null {
  const keys = byWord.get(v.word) ?? [];
  return keys.length > 1 ? keys.indexOf(v.key) + 1 : null;
}

/**
 * 登録済みの類義語(自分も含めて先頭に置く)。
 * 片方にしか類義語として書いていなくても、つながっているものとして扱う。
 */
export function synonymGroup(v: Vocab, vocabs: Vocab[], byWord: Map<string, string[]>, byKey: Map<string, Vocab>): Vocab[] {
  const keys = v.synonyms.flatMap((t) => byWord.get(t) ?? []);
  keys.push(...vocabs.filter((o) => o.synonyms.includes(v.word)).map((o) => o.key));
  const others = [...new Set(keys)].filter((k) => k !== v.key);
  return [v, ...others.map((k) => byKey.get(k)).filter((o): o is Vocab => o !== undefined)];
}
