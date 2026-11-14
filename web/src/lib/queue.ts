// 出題する語彙の選び方と、出題中の状態(Python 版の repository.build_queue と session.py に相当)。

import type { Mode, Result } from "./scheduler.ts";
import type { ReviewState } from "./store.ts";
import type { Vocab } from "./vocab.ts";

export interface Filter {
  categories: string[];
  difficulty: [number, number];
}

function matches(v: Vocab, f: Filter): boolean {
  return (
    v.difficulty >= f.difficulty[0] &&
    v.difficulty <= f.difficulty[1] &&
    (f.categories.length === 0 || f.categories.includes(v.category))
  );
}

type States = Record<string, ReviewState>;

/** 復習日が今日以前の語彙(期限を過ぎた古いものから順)。 */
export function dueKeys(vocabs: Vocab[], states: States, today: string, f: Filter): string[] {
  return vocabs
    .map((v, i) => ({ v, i, s: states[v.key] }))
    .filter(({ v, s }) => s && s.next <= today && matches(v, f))
    .sort((a, b) => a.s.next.localeCompare(b.s.next) || a.i - b.i)
    .map(({ v }) => v.key);
}

/** まだ一度も学習していない語彙(登録順)。 */
export function newKeys(vocabs: Vocab[], states: States, f: Filter): string[] {
  return vocabs.filter((v) => !states[v.key] && matches(v, f)).map((v) => v.key);
}

export function shuffled<T>(items: T[], rng: () => number = Math.random): T[] {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/**
 * 今回出題する語彙の並び。復習予定の語彙を先に、その後に新しい語彙を newLimit 個まで。
 * シャッフルしても「復習 → 新規」の順は保ち、それぞれの中だけ混ぜる。
 */
export function buildQueue(
  vocabs: Vocab[],
  states: States,
  today: string,
  newLimit: number,
  f: Filter,
  shuffle: boolean,
  rng: () => number = Math.random,
): string[] {
  let due = dueKeys(vocabs, states, today, f);
  let fresh = newKeys(vocabs, states, f);
  if (shuffle) {
    due = shuffled(due, rng);
    fresh = shuffled(fresh, rng);
  }
  return [...due, ...fresh.slice(0, Math.max(newLimit, 0))];
}

export interface AnswerRecord {
  key: string;
  word: string;
  result: Result;
  next: string;
  mastery: string;
}

/** 出題中の状態。不正解の語は今回の最後にもう一度出す(1 語 1 回、記録には残さない)。 */
export class Session {
  queue: string[];
  pos = 0;
  revealed = false;
  readonly firstCount: number;
  readonly mode: Mode;
  readonly input: boolean;
  results: AnswerRecord[] = [];
  retryResults: Result[] = [];
  /** 入力式で入力した答え(入力していなければ null) */
  typed: string | null = null;
  typedOk = false;

  constructor(queue: string[], mode: Mode, input: boolean) {
    this.queue = [...queue];
    this.firstCount = queue.length;
    this.mode = mode;
    this.input = input;
  }

  get current(): string | undefined {
    return this.queue[this.pos];
  }

  get finished(): boolean {
    return this.pos >= this.queue.length;
  }

  /** pos 枚目が、間違えた語彙の「もう一度」かどうか。 */
  isRetry(pos = this.pos): boolean {
    return pos >= this.firstCount;
  }

  addRetry(key: string): void {
    if (!this.queue.slice(this.firstCount).includes(key)) this.queue.push(key);
  }

  /** 次のカードへ進む。 */
  advance(): void {
    this.pos += 1;
    this.revealed = false;
    this.typed = null;
    this.typedOk = false;
  }

  /** 中断して結果を見る(ここまでで終わりにする)。 */
  stop(): void {
    this.queue = this.queue.slice(0, this.pos);
  }
}
