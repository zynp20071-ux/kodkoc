// KodKoç service worker (9. hafta)
//
// Ne işe yarar?
//  1) Tarayıcı, service worker'ı olan siteyi "uygulama olarak yükle" diye önerebilir (PWA).
//  2) İnternet yokken boş bir hata yerine "Çevrimdışısın" sayfası gösterilir.
//
// Bilerek YAPMADIĞIMIZ: Sayfaları önbelleğe almak. Sayfalarda kişisel veriler (mesajlar, notlar)
// var; ortak bir bilgisayarda çıkış yaptıktan sonra önbellekte kalmasınlar. Sadece tasarım
// dosyaları ve çevrimdışı sayfası saklanır.

const ONBELLEK = "kodkoc-v1";
const SAKLANACAKLAR = ["/cevrimdisi", "/static/style.css", "/static/ikon-192.png"];

self.addEventListener("install", function (olay) {
  olay.waitUntil(caches.open(ONBELLEK).then(function (o) { return o.addAll(SAKLANACAKLAR); }));
  self.skipWaiting();
});

self.addEventListener("activate", function (olay) {
  // Eski sürümün önbelleklerini temizle
  olay.waitUntil(caches.keys().then(function (adlar) {
    return Promise.all(adlar.filter(function (a) { return a !== ONBELLEK; })
                            .map(function (a) { return caches.delete(a); }));
  }));
  self.clients.claim();
});

self.addEventListener("fetch", function (olay) {
  const istek = olay.request;
  if (istek.method !== "GET") return;                     // Formlara karışma
  if (istek.mode === "navigate") {
    // Sayfa: her zaman internetten; olmazsa çevrimdışı sayfası
    olay.respondWith(fetch(istek).catch(function () { return caches.match("/cevrimdisi"); }));
    return;
  }
  if (SAKLANACAKLAR.indexOf(new URL(istek.url).pathname) !== -1) {
    // Tasarım dosyası: önce internetten (güncel olsun), olmazsa önbellekten
    olay.respondWith(fetch(istek).catch(function () { return caches.match(istek); }));
  }
});
