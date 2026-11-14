import { beforeEach, describe, expect, it } from "vitest";
import { blanksFor, findBlank, matchesWord, wordVariants } from "../src/lib/blank.ts";
import { csvRecords, parseCsv } from "../src/lib/csv.ts";
import { addDays, daysBetween, logicalDate } from "../src/lib/day.ts";
import { buildQueue, dueKeys, newKeys, Session } from "../src/lib/queue.ts";
import { configure, intervalText, masteryLabel, preview, review } from "../src/lib/scheduler.ts";
import { BEFORE_IMPORT_KEY, RecordStore, STORAGE_KEY, type KeyValueStorage } from "../src/lib/store.ts";
import { buildVocabList, sortCsvFiles, splitTerms, type Vocab } from "../src/lib/vocab.ts";

class MemoryStorage implements KeyValueStorage {
  map = new Map<string, string>();
  getItem(k: string) {
    return this.map.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.map.set(k, v);
  }
}

function vocab(word: string, extra: Partial<Vocab> = {}): Vocab {
  return {
    key: `${word}#1`, word, reading: "", meaning: `${word}の意味`, examples: [], nuance: "",
    synonyms: [], antonyms: [], collocations: [], category: "A", difficulty: 3, ...extra,
  };
}

// テストでは間隔の「ゆらぎ」を切って結果を固定する(Python 版の conftest と同じ)
beforeEach(() => configure(false));

describe("CSV", () => {
  it("引用符の中のカンマ・改行・二重引用符を読める", () => {
    const rows = parseCsv('﻿a,b\n1,"x,y"\r\n2,"改\n行 ""引用"""\n\n');
    expect(rows).toEqual([["a", "b"], ["1", "x,y"], ["2", '改\n行 "引用"']]);
  });

  it("語彙の一覧を作り、同じ語には #1, #2 と番号をつける", () => {
    const records = csvRecords(
      "word,reading,meaning,example_1,example_2,synonyms,category,difficulty\n" +
        '俯瞰,ふかん,見渡すこと,俯瞰する,,"概観、鳥瞰",思考,9\n' +
        "俯瞰,ふかん,別の意味,,,,,2\n" +
        ",,意味だけ,,,,,\n",
    );
    const list = buildVocabList(records);
    expect(list.map((v) => v.key)).toEqual(["俯瞰#1", "俯瞰#2"]);
    expect(list[0].synonyms).toEqual(["概観", "鳥瞰"]);
    expect(list[0].examples).toEqual(["俯瞰する"]);
    expect(list[0].difficulty).toBe(3); // 範囲外は標準の 3
    expect(list[1].category).toBe("未分類");
  });

  it("CSV は seed を先に、追加分はファイル名順に読む", () => {
    expect(sortCsvFiles(["add_2026-11.csv", "vorge_vocab_seed.csv", "add_2026-10.csv"])).toEqual([
      "vorge_vocab_seed.csv", "add_2026-10.csv", "add_2026-11.csv",
    ]);
    expect(splitTerms(" a 、b,,c ")).toEqual(["a", "b", "c"]);
  });
});

describe("1 日の区切り(朝 4 時)", () => {
  it("4 時より前は前日として数える", () => {
    expect(logicalDate(new Date(2026, 10, 14, 3, 59))).toBe("2026-11-13");
    expect(logicalDate(new Date(2026, 10, 14, 4, 0))).toBe("2026-11-14");
  });
  it("日付の足し算と差", () => {
    expect(addDays("2026-12-31", 1)).toBe("2027-01-01");
    expect(daysBetween("2026-11-14", "2026-12-01")).toBe(17);
  });
});

describe("FSRS(Python 版と同じ値になる)", () => {
  const now = new Date(2026, 10, 14, 12, 0);

  it("初めての回答の間隔", () => {
    // Python 版(fsrs 6.3.2、同じ設定)で計算した値:Again 1 / Hard 1 / Good 2 / Easy 8 日
    expect(preview(null, now)).toEqual({ wrong: 1, unsure: 1, correct: 2, easy: 8 });
  });

  it("2 回目は 1 回目の結果を引き継いで延びる", () => {
    const first = review(null, "correct", now);
    expect(first.due).toBe("2026-11-16");
    const later = new Date(2026, 10, 16, 12, 0);
    // Python 版:Again 1 / Hard 8 / Good 11 / Easy 19 日
    expect(preview(first.card, later)).toEqual({ wrong: 1, unsure: 8, correct: 11, easy: 19 });
  });

  it("次回は必ず翌日以降(深夜の回答でも)", () => {
    const lateNight = new Date(2026, 10, 15, 2, 0); // 論理上は 11/14
    const r = review(null, "wrong", lateNight);
    expect(r.due > logicalDate(lateNight)).toBe(true);
    expect(r.interval).toBeGreaterThanOrEqual(1);
  });

  it("習得状況と間隔の表示", () => {
    expect([undefined, 1, 7, 21].map((d) => masteryLabel(d))).toEqual(["未学習", "学習中", "定着中", "習得"]);
    expect([1, 5, 90, 730].map(intervalText)).toEqual(["明日", "5日後", "約3か月後", "約2.0年後"]);
  });

  it("ゆらぎを入れても間隔は 1〜3650 日に収まる", () => {
    configure(true);
    let card = review(null, "easy", now);
    for (let i = 0; i < 30; i++) card = review(card.card, "easy", new Date(card.card.due));
    expect(card.interval).toBeGreaterThan(0);
    expect(card.interval).toBeLessThanOrEqual(3651);
  });
});

describe("例文の穴埋めと入力の採点", () => {
  it("活用形も空欄にできる", () => {
    expect(wordVariants("腑に落ちる")).toEqual(["腑に落ちる", "腑に落ち"]);
    expect(findBlank("ようやく腑に落ちた", "腑に落ちる")).toEqual({ before: "ようやく", answer: "腑に落ち", after: "た" });
    expect(blanksFor(vocab("俯瞰", { examples: ["全体を俯瞰する", "無関係な文"] }))).toHaveLength(1);
  });

  it("語彙・読み・全角半角の違いを許して採点する", () => {
    expect(matchesWord(" 俯瞰 ", "俯瞰", "ふかん")).toBe(true);
    expect(matchesWord("ふかん", "俯瞰", "ふかん")).toBe(true);
    expect(matchesWord("ＰＤＣＡ", "PDCA")).toBe(true);
    expect(matchesWord("煮詰ま", "煮詰まる", "につまる", ["煮詰ま"])).toBe(true);
    expect(matchesWord("", "俯瞰")).toBe(false);
    expect(matchesWord("鳥瞰", "俯瞰", "ふかん")).toBe(false);
  });
});

describe("出題の選び方", () => {
  const vocabs = ["a", "b", "c", "d"].map((w, i) => vocab(w, { difficulty: i + 1, category: i < 2 ? "X" : "Y" }));
  const storage = new MemoryStorage();
  const store = new RecordStore(storage);
  const now = new Date(2026, 10, 14, 12, 0);

  it("復習日が来た語を先に、そのあと未学習を新規の数だけ", () => {
    store.recordAnswer("c#1", "wrong", "word_to_meaning", now);
    store.recordAnswer("a#1", "wrong", "word_to_meaning", now);
    const states = store.data.reviews;
    const all = { categories: [], difficulty: [1, 5] as [number, number] };
    expect(dueKeys(vocabs, states, "2026-11-14", all)).toEqual([]);
    expect(dueKeys(vocabs, states, "2026-11-15", all)).toEqual(["a#1", "c#1"]);
    expect(newKeys(vocabs, states, all)).toEqual(["b#1", "d#1"]);
    expect(buildQueue(vocabs, states, "2026-11-15", 1, all, false)).toEqual(["a#1", "c#1", "b#1"]);
    // カテゴリ・難易度で絞り込む
    expect(buildQueue(vocabs, states, "2026-11-15", 5, { categories: ["Y"], difficulty: [4, 5] }, false)).toEqual(["d#1"]);
  });

  it("シャッフルしても復習 → 新規の順は保つ", () => {
    const all = { categories: [], difficulty: [1, 5] as [number, number] };
    for (let seed = 0; seed < 10; seed++) {
      const q = buildQueue(vocabs, store.data.reviews, "2026-11-15", 2, all, true);
      expect(new Set(q.slice(0, 2))).toEqual(new Set(["a#1", "c#1"]));
      expect(new Set(q.slice(2))).toEqual(new Set(["b#1", "d#1"]));
    }
  });

  it("不正解の語は最後にもう一度(1 語 1 回)", () => {
    const s = new Session(["a#1", "b#1"], "word_to_meaning", false);
    s.addRetry("a#1");
    s.addRetry("a#1");
    expect(s.queue).toEqual(["a#1", "b#1", "a#1"]);
    s.advance();
    s.advance();
    expect(s.isRetry()).toBe(true);
    s.stop();
    expect(s.finished).toBe(true);
  });
});

describe("記録の保存", () => {
  const now = new Date(2026, 10, 14, 12, 0);

  it("回答を記録し、読み込み直しても残る", () => {
    const storage = new MemoryStorage();
    const store = new RecordStore(storage);
    store.recordAnswer("a#1", "correct", "cloze", now);
    const s = store.recordAnswer("a#1", "unsure", "cloze", new Date(2026, 10, 16, 12, 0));
    expect(s).toMatchObject({ count: 2, correct: 1, unsure: 1, last: "unsure" });
    store.updateSettings({ newLimit: 25 });

    const reloaded = new RecordStore(storage);
    expect(reloaded.get("a#1")?.count).toBe(2);
    expect(reloaded.settings.newLimit).toBe(25);
    expect(reloaded.settings.shuffle).toBe(true);
    expect(reloaded.countAnswersOn("2026-11-14")).toBe(1);
  });

  it("書き出した記録を別の端末で取り込める(前の記録は退避)", () => {
    const pc = new RecordStore(new MemoryStorage());
    pc.recordAnswer("a#1", "easy", "word_to_meaning", now);
    const phoneStorage = new MemoryStorage();
    const phone = new RecordStore(phoneStorage);
    phone.recordAnswer("b#1", "wrong", "word_to_meaning", now);

    phone.importJson(pc.exportJson());
    expect(phone.get("a#1")?.easy).toBe(1);
    expect(phone.get("b#1")).toBeUndefined();
    expect(JSON.parse(phoneStorage.getItem(BEFORE_IMPORT_KEY)!).reviews["b#1"]).toBeDefined();
  });

  it("おかしなファイルは取り込まない", () => {
    const store = new RecordStore(new MemoryStorage());
    expect(() => store.importJson("{")).toThrow("JSON");
    expect(() => store.importJson('{"format":"other"}')).toThrow("記録ファイルではありません");
  });

  it("保存データが壊れていても消さずに退避する", () => {
    const storage = new MemoryStorage();
    storage.setItem(STORAGE_KEY, "壊れた");
    const store = new RecordStore(storage);
    expect(store.data.log).toEqual([]);
    expect([...storage.map.values()]).toContain("壊れた");
  });
});
