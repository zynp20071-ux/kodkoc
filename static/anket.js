// KodKoç - Anket kartı (10. hafta)
//
// Sohbetteki bir anketi çizer: soru, seçenekler, oy sayısı ve yüzde çubukları, "Oy ver" düğmesi.
// Hem sohbet sayfası hem mesaj paneli bu dosyayı kullanır:  KodKocAnket.ciz(kutu, anket, csrf)
// Oy verince sayfa yenilenmez: /anket/<id>/oy adresine gönderilir, dönen güncel anketle kart yeniden çizilir.
// Bütün yazılar textContent ile yazılır (seçenek metnindeki <script> kod olarak çalışmaz).

window.KodKocAnket = (function () {
  function yeni(etiket, sinif, metin) {
    var o = document.createElement(etiket);
    if (sinif) o.className = sinif;
    if (metin !== undefined) o.textContent = metin;
    return o;
  }

  function gonder(adres, veri, kutu, csrf) {
    veri.append("csrf", csrf);
    return fetch(adres, {method: "POST", body: veri, credentials: "same-origin"})
      .then(function (c) { return c.json(); })
      .then(function (cevap) {
        if (cevap.anket) ciz(kutu, cevap.anket, csrf);
        if (cevap.hata) {
          var not = kutu.querySelector(".anket-not");
          if (not) not.textContent = cevap.hata;
        }
      })
      .catch(function () {
        var not = kutu.querySelector(".anket-not");
        if (not) not.textContent = "Gönderilemedi; internet bağlantını kontrol et.";
      });
  }

  function ciz(kutu, anket, csrf) {
    kutu.textContent = "";
    kutu.className = "anket";
    kutu.appendChild(yeni("p", "anket-soru", "📊 " + anket.soru));
    var bilgi = [anket.coklu ? "Birden çok seçebilirsin" : "Tek seçim",
                 anket.oy_veren + " kişi oy verdi"];
    if (!anket.acik) bilgi.push("Anket bitti");
    else if (anket.bitis) bilgi.push("Son gün: " + anket.bitis);
    kutu.appendChild(yeni("p", "anket-bilgi", bilgi.join(" · ")));

    var form = yeni("form", "anket-formu");
    anket.secenekler.forEach(function (s) {
      var satir = yeni("label", "anket-secenek" + (s.benim ? " benim" : ""));
      var kutucuk = document.createElement("input");
      kutucuk.type = anket.coklu ? "checkbox" : "radio";
      kutucuk.name = "secenek";
      kutucuk.value = s.id;
      kutucuk.checked = s.benim;
      kutucuk.disabled = !anket.acik;
      satir.appendChild(kutucuk);
      satir.appendChild(yeni("span", "anket-metin", s.metin));
      satir.appendChild(yeni("span", "anket-sayi", s.oy + " oy · %" + s.yuzde));
      var cubuk = yeni("span", "anket-cubuk");
      var dolu = yeni("span", "anket-dolu");
      dolu.style.width = s.yuzde + "%";       // Betikle verilen stil, güvenlik başlığına (CSP) takılmaz
      cubuk.appendChild(dolu);
      satir.appendChild(cubuk);
      form.appendChild(satir);
    });

    var dugmeler = yeni("div", "anket-dugmeleri");
    if (anket.acik) {
      var oyDugmesi = yeni("button", "kucuk-dugme", anket.oy_verdi ? "Oyumu değiştir" : "Oy ver");
      oyDugmesi.type = "submit";
      dugmeler.appendChild(oyDugmesi);
    }
    if (anket.kapatabilir) {
      var bitir = yeni("button", "isaret", "Anketi bitir");
      bitir.type = "button";
      bitir.addEventListener("click", function () {
        if (confirm("Anket bitsin mi? Artık oy verilemeyecek, sonuçlar kalacak.")) {
          gonder("/anket/" + anket.id + "/kapat", new FormData(), kutu, csrf);
        }
      });
      dugmeler.appendChild(bitir);
    }
    form.appendChild(dugmeler);
    form.appendChild(yeni("p", "anket-not"));
    form.addEventListener("submit", function (olay) {
      olay.preventDefault();
      gonder("/anket/" + anket.id + "/oy", new FormData(form), kutu, csrf);
    });
    kutu.appendChild(form);
  }

  // Sayfa açılınca sunucunun yazdığı anketleri çiz: <div class="anket" data-anket='{...}'>
  function sayfadakileriCiz(csrf) {
    var kutular = document.querySelectorAll(".anket[data-anket]");
    Array.prototype.forEach.call(kutular, function (kutu) {
      try { ciz(kutu, JSON.parse(kutu.dataset.anket), csrf); } catch (e) {}
    });
  }

  return {ciz: ciz, sayfadakileriCiz: sayfadakileriCiz};
})();
