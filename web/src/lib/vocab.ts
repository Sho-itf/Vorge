// 語彙のデータ形式と、CSV の行から語彙を作る処理。

export interface Vocab {
  /** 学習記録と結びつける鍵。「語#同じ語の何番目か」(例:俯瞰#1)。 */
  key: string;
  word: string;
  reading: string;
  meaning: string;
  examples: string[];
  nuance: string;
  synonyms: string[];
  antonyms: string[];
  collocations: string[];
  category: string;
  difficulty: number;
}

/** 「概観,鳥瞰」「概観、鳥瞰」のような区切り文字列を配列にする。 */
export function splitTerms(text: string): string[] {
  return text
    .replace(/[、,]/g, ",")
    .split(",")
    .map((t) => t.trim())
    .filter(Boolean);
}

/**
 * CSV の行(列名 → 値)から語彙の一覧を作る。語彙か意味が空の行は飛ばす。
 *
 * 鍵は CSV の id 列ではなく「語#n」にする(追加用 CSV は id が空のため)。
 * 同じ語が複数あるとき(多義語)は、読み込んだ順に #1, #2 … と番号をつける。
 */
export function buildVocabList(records: Record<string, string>[]): Vocab[] {
  const seen = new Map<string, number>();
  const list: Vocab[] = [];
  for (const r of records) {
    const word = (r.word ?? "").trim();
    const meaning = (r.meaning ?? "").trim();
    if (!word || !meaning) continue;
    const n = (seen.get(word) ?? 0) + 1;
    seen.set(word, n);
    const difficulty = Number.parseInt(r.difficulty ?? "", 10);
    list.push({
      key: `${word}#${n}`,
      word,
      reading: r.reading ?? "",
      meaning,
      examples: [r.example_1, r.example_2].filter((e): e is string => Boolean(e)),
      nuance: r.nuance ?? "",
      synonyms: splitTerms(r.synonyms ?? ""),
      antonyms: splitTerms(r.antonyms ?? ""),
      collocations: splitTerms(r.collocations ?? ""),
      category: r.category || "未分類",
      difficulty: difficulty >= 1 && difficulty <= 5 ? difficulty : 3,
    });
  }
  return list;
}

/** CSV ファイルを読む順番。最初の語彙集(seed)を先に、追加分はファイル名順(日付順)に。 */
export function sortCsvFiles(names: string[]): string[] {
  const isSeed = (n: string) => n.includes("seed");
  return [...names].sort((a, b) => Number(isSeed(b)) - Number(isSeed(a)) || a.localeCompare(b));
}
