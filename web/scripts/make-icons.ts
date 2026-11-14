// アイコンの元データ(icon/vorge-icon.svg)から、public/ のアイコン一式を書き出す。
// 手で実行する(npm run icons)。書き出した画像は commit し、ビルドの依存にはしない。
//
//   favicon.svg               元の SVG そのまま(角丸の地つき)
//   icon-192.png / -512.png   同じデザインの PNG(角は透明な角丸)
//   icon-maskable-512.png     Android 用。地は全面塗り、本と V を中心のまま 0.75 倍に縮める
//   apple-touch-icon.png      iPhone 用 180×180。地は全面塗りの不透明な正方形(角丸は iPhone がつける)

import { copyFileSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const here = dirname(fileURLToPath(import.meta.url));
const source = join(here, "..", "icon", "vorge-icon.svg");
const out = (name: string) => join(here, "..", "public", name);

const svg = readFileSync(source, "utf-8");
// 1 つ目の rect が地。それ以外(本と V)を中身として取り出す
const background = svg.match(/<rect width="100" height="100"[^>]*\/>/)?.[0];
if (!background) throw new Error("地の rect が見つかりません");
const content = svg.slice(svg.indexOf(background) + background.length, svg.lastIndexOf("</svg>"));

/** 地の角丸と、中身の縮小率を変えた SVG。縮小は中心 (50,50) を基準にする。 */
function variant(rx: number, scale: number): string {
  const bg = background!.replace(/rx="\d+"/, `rx="${rx}"`);
  const offset = 50 * (1 - scale);
  const body = scale === 1 ? content : `<g transform="translate(${offset} ${offset}) scale(${scale})">${content}</g>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">${bg}${body}</svg>`;
}

async function png(svgText: string, size: number, name: string, opaque = false): Promise<void> {
  let image = sharp(Buffer.from(svgText), { density: (72 * size) / 100 * 4 }).resize(size, size);
  if (opaque) image = image.flatten({ background: "#243a57" });
  await image.png().toFile(out(name));
  console.log(`${name}: ${size}×${size}`);
}

copyFileSync(source, out("favicon.svg"));
console.log("favicon.svg: 元の SVG");
await png(variant(22, 1), 192, "icon-192.png");
await png(variant(22, 1), 512, "icon-512.png");
await png(variant(0, 0.75), 512, "icon-maskable-512.png", true);
await png(variant(0, 1), 180, "apple-touch-icon.png", true);
