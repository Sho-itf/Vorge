"""キーボードショートカット(キーを押すと、対応するボタンを押したことにする)。

Streamlit にはキー操作の仕組みが無いので、小さな JavaScript を画面に埋め込み、
「キー → ボタンの文字(先頭部分)」の対応表に従ってボタンをクリックする。
入力欄に文字を打っている間や、Ctrl などを押しているときは反応しない。
"""

import json

import streamlit.components.v1 as components


def keyboard_shortcuts(mapping: dict[str, str]) -> None:
    """mapping:キー(" "・"Enter"・"1" など)→ 押したいボタンの表示文字の先頭部分。"""
    script = """
<script>
(() => {
  const doc = window.parent.document;
  const map = __MAP__;
  if (doc.__vorgeKeyHandler) doc.removeEventListener("keydown", doc.__vorgeKeyHandler);
  doc.__vorgeKeyHandler = (e) => {
    const t = e.target;
    if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
    const label = map[e.key];
    if (!label) return;
    const button = Array.from(doc.querySelectorAll("button"))
      .find((b) => !b.disabled && b.innerText.trim().startsWith(label));
    if (button) {
      e.preventDefault();
      button.click();
    }
  };
  doc.addEventListener("keydown", doc.__vorgeKeyHandler);
})();
</script>
""".replace("__MAP__", json.dumps(mapping, ensure_ascii=False))
    components.html(script, height=0)
