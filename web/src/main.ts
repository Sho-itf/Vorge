// 画面の切り替え(URL の # 以降で決める。GitHub Pages のサブパスでも動くように)。
//   #/cards        単語カード
//   #/library      語彙ライブラリ
//   #/library/鍵   語彙の詳細
//   #/data         学習の記録(書き出し/取り込み)

import "./style.css";
import { loadApp, type App } from "./app.ts";
import { esc } from "./ui/dom.ts";
import { leaveFlashcard, renderFlashcard } from "./ui/flashcard.ts";
import { renderData } from "./ui/data.ts";
import { renderLibrary, renderVocabDetail } from "./ui/library.ts";

const root = document.querySelector<HTMLElement>("#app")!;

function route(app: App): void {
  const [, page = "cards", arg] = location.hash.split("/");
  leaveFlashcard();
  document.querySelectorAll<HTMLAnchorElement>(".tabs a").forEach((a) =>
    a.classList.toggle("active", a.dataset.tab === page),
  );
  if (page === "library" && arg) renderVocabDetail(root, app, decodeURIComponent(arg));
  else if (page === "library") renderLibrary(root, app);
  else if (page === "data") renderData(root, app);
  else renderFlashcard(root, app);
  if (!(page === "cards")) window.scrollTo({ top: 0 });
}

async function main(): Promise<void> {
  root.innerHTML = `<p class="muted">読み込み中…</p>`;
  try {
    const app = await loadApp();
    window.addEventListener("hashchange", () => route(app));
    route(app);
  } catch (e) {
    root.innerHTML = `<p class="ng">${esc((e as Error).message)}</p>`;
  }
  // ホーム画面に追加したとき、通信できなくても開けるようにする(本番のビルドだけ)
  if (import.meta.env.PROD && "serviceWorker" in navigator) {
    navigator.serviceWorker.register("./sw.js").catch(() => {});
  }
}

main();
