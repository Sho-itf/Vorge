// リポジトリの csv/*.csv を読み、語彙の一覧を public/vocab.json に書き出す。
// npm run dev / npm run build の前に自動で実行される(package.json の predev / prebuild)。

import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { csvRecords } from "../src/lib/csv.ts";
import { buildVocabList, sortCsvFiles } from "../src/lib/vocab.ts";

const here = dirname(fileURLToPath(import.meta.url));
const csvDir = join(here, "..", "..", "csv");
const outPath = join(here, "..", "public", "vocab.json");

const files = sortCsvFiles(readdirSync(csvDir).filter((n) => n.toLowerCase().endsWith(".csv")));
const records = files.flatMap((name) => csvRecords(readFileSync(join(csvDir, name), "utf-8")));
const vocabs = buildVocabList(records);

const duplicated = vocabs.filter((v) => !v.key.endsWith("#1")).map((v) => v.key);
writeFileSync(outPath, JSON.stringify({ builtAt: new Date().toISOString(), vocabs }));
console.log(`vocab.json: ${vocabs.length} 語(${files.join(", ")})`);
if (duplicated.length) console.log(`同じ語が複数あります(多義語として扱います): ${duplicated.join(", ")}`);
