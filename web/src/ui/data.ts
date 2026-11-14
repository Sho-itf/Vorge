// 記録画面:学習の記録の書き出し/取り込み(バックアップと、PC ⇔ スマホの引っ越し用)。

import type { App } from "../app.ts";
import { formatDateTime, logicalDate } from "../lib/day.ts";
import { masteryLabel } from "../lib/scheduler.ts";
import { esc, toast } from "./dom.ts";

export function renderData(root: HTMLElement, app: App): void {
  const reviews = Object.values(app.store.data.reviews);
  const mastery = (label: string) => reviews.filter((s) => masteryLabel(s.interval) === label).length;
  const studied = app.vocabs.filter((v) => app.store.get(v.key)).length;

  root.innerHTML = `
    <h1>学習の記録</h1>
    <div class="stats">
      <div class="card stat"><span>学習した語彙</span><b>${studied} / ${app.vocabs.length} 語</b></div>
      <div class="card stat"><span>学習中 ・ 定着中 ・ 習得</span><b>${mastery("学習中")} ・ ${mastery("定着中")} ・ ${mastery("習得")}</b></div>
      <div class="card stat"><span>回答の合計</span><b>${app.store.data.log.length} 回</b></div>
    </div>

    <div class="card">
      <h2>記録の保存場所</h2>
      <p>学習の記録は<b>このブラウザの中だけ</b>に保存されます。サーバーには送りません。</p>
      <ul>
        <li>PC とスマホの記録は別々です。引っ越すときは、下の「書き出し」→ もう一方の端末で「取り込み」をしてください。</li>
        <li>ブラウザの「閲覧データを削除」をすると記録も消えます。ときどき書き出してバックアップしておくと安心です。</li>
      </ul>
    </div>

    <div class="card">
      <h2>📤 記録を書き出す</h2>
      <p>復習の予定・回答の履歴・出題の設定を 1 つのファイル(JSON)にします。</p>
      <button class="primary" id="export">記録を書き出す</button>
    </div>

    <div class="card">
      <h2>📥 記録を取り込む</h2>
      <p>書き出したファイルで、<b>今のこの端末の記録を置き換えます</b>。置き換える前の記録はブラウザ内に 1 つだけ退避します。</p>
      <input type="file" id="file" accept="application/json,.json" />
      <label class="switch"><input type="checkbox" id="agree" /> 今の記録がファイルの内容に置き換わることを理解しました</label>
      <button id="import" disabled>取り込む</button>
    </div>

    <p class="muted">語彙データ:${app.vocabs.length} 語(${esc(formatDateTime(new Date(app.builtAt)))} 更新)</p>`;

  root.querySelector("#export")!.addEventListener("click", () => {
    const blob = new Blob([app.store.exportJson()], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `vorge_record_${logicalDate(new Date())}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  });

  const file = root.querySelector<HTMLInputElement>("#file")!;
  const agree = root.querySelector<HTMLInputElement>("#agree")!;
  const button = root.querySelector<HTMLButtonElement>("#import")!;
  const sync = () => {
    button.disabled = !(file.files?.length && agree.checked);
  };
  file.addEventListener("change", sync);
  agree.addEventListener("change", sync);
  button.addEventListener("click", async () => {
    const f = file.files?.[0];
    if (!f) return;
    try {
      app.store.importJson(await f.text());
    } catch (e) {
      toast(`取り込めませんでした:${(e as Error).message}`);
      return;
    }
    toast("記録を取り込みました");
    renderData(root, app);
  });
}
