// 例文の穴埋めと、入力した答えの採点(Python 版の vorge/quiz/builder.py と同じ考え方)。

import type { Vocab } from "./vocab.ts";

export interface Blank {
  before: string;
  /** 例文中の実際の表記(活用していればその形) */
  answer: string;
  after: string;
}

/**
 * 文中で語彙とみなす表記の一覧(長い順)。
 * 活用する語(最後がひらがな)は最後の 1 文字を除いた形も認める(「腑に落ちる」→「腑に落ち」)。
 */
export function wordVariants(word: string, reading = ""): string[] {
  const variants = new Set([word]);
  const last = word.at(-1) ?? "";
  const inflectable = last >= "ぁ" && last <= "ゖ";
  if (inflectable && [...word].length >= 3) variants.add(word.slice(0, -1));
  if (reading && reading !== word) {
    variants.add(reading);
    if (inflectable && [...reading].length >= 4) variants.add(reading.slice(0, -1));
  }
  return [...variants].sort((a, b) => b.length - a.length);
}

/** 例文の中から語彙(活用形を含む)を探して空欄にする。見つからなければ null。 */
export function findBlank(sentence: string, word: string): Blank | null {
  for (const variant of wordVariants(word)) {
    const pos = sentence.indexOf(variant);
    if (pos >= 0) {
      return { before: sentence.slice(0, pos), answer: variant, after: sentence.slice(pos + variant.length) };
    }
  }
  return null;
}

/** その語彙の例文から作れる空欄の一覧。 */
export function blanksFor(vocab: Vocab): Blank[] {
  return vocab.examples.map((s) => findBlank(s, vocab.word)).filter((b): b is Blank => b !== null);
}

/** 全角・半角の違いと空白を無視して比べるための正規化。 */
function normalize(text: string): string {
  return text.normalize("NFKC").replace(/\s+/g, "");
}

/** 入力した答えが語彙に一致するか。語彙・読み・活用形・extraForms のどれでも正解にする。 */
export function matchesWord(answer: string, word: string, reading = "", extraForms: string[] = []): boolean {
  const given = normalize(answer);
  if (!given) return false;
  const accepted = new Set([word, ...extraForms, ...wordVariants(word)]);
  if (reading) {
    accepted.add(reading);
    wordVariants(reading).forEach((v) => accepted.add(v));
  }
  return [...accepted].some((a) => normalize(a) === given);
}
