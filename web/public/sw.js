// 通信できないときでも開けるようにするための Service Worker。
// 画面(HTML)と語彙データは「まず通信、だめなら保存済み」、それ以外のファイルは「保存済みを優先」。
// 学習の記録は localStorage にあるので、ここでは扱わない。

// アイコンなど同じ名前のまま中身を変えたファイルがあるときは、名前を上げて保存済みを捨てる
// (v2:アイコンを新デザインに差し替え)
const CACHE = "vorge-web-v2";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) =>
  event.waitUntil(
    (async () => {
      // 古い名前の保存済み(前のアイコンなど)を消す
      for (const name of await caches.keys()) if (name !== CACHE) await caches.delete(name);
      await self.clients.claim();
    })(),
  ),
);

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;

  const networkFirst = req.mode === "navigate" || req.url.endsWith("/vocab.json");
  event.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const fetchAndStore = async () => {
        const res = await fetch(req);
        if (res.ok) cache.put(req, res.clone());
        return res;
      };
      if (networkFirst) {
        try {
          return await fetchAndStore();
        } catch {
          return (await cache.match(req)) ?? Response.error();
        }
      }
      return (await cache.match(req)) ?? fetchAndStore();
    }),
  );
});
