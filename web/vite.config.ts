import { defineConfig } from "vitest/config";

export default defineConfig({
  // GitHub Pages ではリポジトリ名のサブパス(/Vorge/)で配信されるので、相対パスにしておく
  base: "./",
  test: { include: ["tests/**/*.test.ts"] },
});
