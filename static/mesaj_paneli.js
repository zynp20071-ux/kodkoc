// KodKoç - Mesaj paneli (10. hafta)
//
// Her sayfanın sağ altındaki "Mesajlar" düğmesi küçük bir pencere açar. Sayfadan çıkmadan:
//   1) sohbet listesini (sınıf, grup, özel) okunmamış sayılarıyla görürsün,
//   2) bir sohbete tıklayıp mesajları okur ve yazarsın.
// Sunucuyla JSON ile konuşur:
//   GET  /mesajlar/panel                 -> sohbet listesi
//   GET  /sohbet/yeni?grup=3&sonra=120   -> o sohbetin yeni mesajları (sohbet sayfasındakiyle aynı)
//   POST /sohbet/gonder                  -> mesaj gönder (CSRF jetonuyla)
// Başka sayfaya geçince panel açık kalsın diye durumu sessionStorage'da tutar (sekme kapanınca silinir).
//
// Güvenlik: Mesajlar innerHTML ile DEĞİL textContent ile yazılır; mesajdaki <script> gibi yazılar
// kod olarak çalışmaz, düz yazı olarak görünür (XSS koruması).

(function () {
  var panel = document.getElementById("mesaj-paneli");
  var dugme = document.getElementById("panel-dugmesi");
  if (!panel || !dugme || !window.fetch) return;

  var liste = document.getElementById("panel-liste");
  var sohbetAlani = document.getElementById("panel-sohbet");
  var mesajlar = document.getElementById("panel-mesajlar");
  var bilgi = document.getElementById("panel-not");
  var form = document.getElementById("panel-form");
  var kutu = document.getElementById("panel-metin");
  var baslik = document.getElementById("panel-baslik");
  var geri = document.getElementById("panel-geri");
  var tamEkran = document.getElementById("panel-tam");
  var saniye = parseInt(panel.dataset.saniye, 10) * 1000 || 5000;
  var resimSec = document.getElementById("panel-resim-sec");
  var resimDosyasi = document.getElementById("panel-resim");

  var acikSohbet = null;      // {tur, id, ad, sayfa}
  var sonId = 0;
  var zamanlayici = null;
  var odakIste = false;       // Sohbet açılınca yazı kutusuna geçilsin mi? (sayfa yüklenirken hayır)

  // --- Küçük yardımcılar ---
  function yeni(etiket, sinif, metin) {
    var o = document.createElement(etiket);
    if (sinif) o.className = sinif;
    if (metin !== undefined) o.textContent = metin;
    return o;
  }
  function durumuKaydet() {
    try {
      sessionStorage.setItem("kodkoc-panel", JSON.stringify({acik: !panel.hidden, sohbet: acikSohbet}));
    } catch (e) {}
  }
  function durdur() {
    if (zamanlayici) clearInterval(zamanlayici);
    zamanlayici = null;
  }
  function rozetiYaz(sayi) {
    var rozet = document.getElementById("panel-rozeti");
    rozet.textContent = sayi;
    rozet.hidden = !sayi;
  }

  // --- Sohbet listesi ---
  function listeyiGoster() {
    durdur();
    acikSohbet = null;
    durumuKaydet();
    baslik.textContent = "Mesajlar";
    geri.hidden = true;
    tamEkran.href = "/mesajlar";
    sohbetAlani.hidden = true;
    form.hidden = true;
    liste.hidden = false;
    listeyiYukle();
    zamanlayici = setInterval(listeyiYukle, 15000);
  }

  function listeyiYukle() {
    if (document.visibilityState !== "visible") return;
    fetch("/mesajlar/panel", {credentials: "same-origin"})
      .then(function (c) { return c.ok ? c.json() : null; })
      .then(function (veri) {
        if (!veri || acikSohbet) return;
        rozetiYaz(veri.toplam);
        liste.textContent = "";
        if (!veri.sohbetler.length && !veri.yeni_kisiler.length) {
          liste.appendChild(yeni("p", "ipucu-yazi", "Henüz bir sohbetin yok. Bir sınıfa katılınca burada görünür."));
        }
        if (veri.davetler.length) {
          liste.appendChild(yeni("p", "ipucu-etiket", "Grup davetlerin"));
          var davetler = yeni("ul", "panel-listesi");
          veri.davetler.forEach(function (d) {
            var li = yeni("li", "panel-davet");
            li.appendChild(yeni("span", "", d.davet_eden + " seni “" + d.grup + "” grubuna davet etti (" + d.sinif + ")"));
            var kabul = yeni("button", "kucuk-dugme", "Kabul et");
            var ret = yeni("button", "isaret", "Reddet");
            kabul.type = ret.type = "button";
            kabul.addEventListener("click", function () { davetiCevapla(d.grup_id, "kabul", d.grup); });
            ret.addEventListener("click", function () { davetiCevapla(d.grup_id, "reddet"); });
            li.appendChild(kabul);
            li.appendChild(ret);
            davetler.appendChild(li);
          });
          liste.appendChild(davetler);
        }
        var ul = yeni("ul", "panel-listesi");
        veri.sohbetler.forEach(function (s) {
          var li = yeni("li");
          var b = yeni("button", "panel-ogesi");
          b.type = "button";
          var ust = yeni("span", "panel-oge-ust");
          ust.appendChild(yeni("span", "sohbet-adi", s.ad));
          if (s.okunmamis) ust.appendChild(yeni("span", "menu-rozeti", String(s.okunmamis)));
          b.appendChild(ust);
          b.appendChild(yeni("span", "panel-oge-alt", s.alt + (s.zaman ? " · " + s.zaman : "")));
          b.appendChild(yeni("span", "sohbet-son", s.son));
          b.addEventListener("click", function () {
            sohbetiAc({tur: s.tur, id: s.id, ad: s.ad, sayfa: s.sayfa}, true);
          });
          li.appendChild(b);
          ul.appendChild(li);
        });
        liste.appendChild(ul);

        if (veri.yeni_kisiler.length) {
          var ayrinti = yeni("details", "panel-yeni");
          ayrinti.appendChild(yeni("summary", "", "Yeni sohbet başlat"));
          var kisiler = yeni("ul", "panel-listesi");
          veri.yeni_kisiler.forEach(function (k) {
            var li = yeni("li");
            var b = yeni("button", "panel-ogesi kisa", k.ad + (k.ogretmen ? " (Öğretmen)" : ""));
            b.type = "button";
            b.addEventListener("click", function () {
              sohbetiAc({tur: "kisi", id: k.id, ad: k.ad, sayfa: "/mesaj/" + k.id}, true);
            });
            li.appendChild(b);
            kisiler.appendChild(li);
          });
          ayrinti.appendChild(kisiler);
          liste.appendChild(ayrinti);
        }
        var grupLinki = yeni("a", "panel-grup-kur", "+ Yeni grup kur");
        grupLinki.href = "/grup/yeni";
        liste.appendChild(grupLinki);
      })
      .catch(function () {});
  }

  function davetiCevapla(grupId, islem, grupAdi) {
    var veri = new FormData();
    veri.append("csrf", panel.dataset.csrf);
    veri.append("json", "1");
    fetch("/davet/" + grupId + "/" + islem, {method: "POST", body: veri, credentials: "same-origin"})
      .then(function (c) { return c.json(); })
      .then(function (cevap) {
        if (cevap.hata) { alert(cevap.hata); listeyiYukle(); return; }
        if (islem === "kabul") sohbetiAc({tur: "grup", id: grupId, ad: grupAdi, sayfa: cevap.adres}, true);
        else listeyiYukle();
      })
      .catch(function () {});
  }

  // --- Bir sohbet ---
  function mesajiEkle(m) {
    if (document.getElementById("panel-mesaj-" + m.id)) return;
    var li = yeni("li", "mesaj" + (m.benim ? " benim" : "") + (m.silindi ? " silindi" : ""));
    li.id = "panel-mesaj-" + m.id;
    var ust = yeni("span", "mesaj-ust");
    var ad = yeni("a", "", m.gonderen);
    ad.href = m.profil;
    ust.appendChild(ad);
    if (m.ogretmen) {
      ust.appendChild(document.createTextNode(" "));
      ust.appendChild(yeni("span", "ogretmen-etiketi", "Öğretmen"));
    }
    ust.appendChild(document.createTextNode(" · " + m.zaman));
    li.appendChild(ust);
    if (m.anket && window.KodKocAnket) {
      var kutu = yeni("div");
      li.appendChild(kutu);
      KodKocAnket.ciz(kutu, m.anket, panel.dataset.csrf);
    } else if (m.silindi || m.metin) {
      li.appendChild(yeni("p", "mesaj-metni", m.silindi ? "Bu mesaj silindi." : m.metin));
    }
    if (m.resim) {
      var bag = yeni("a");
      bag.href = m.resim;
      bag.target = "_blank";
      bag.rel = "noopener";
      var resim = yeni("img", "mesaj-resmi");
      resim.src = m.resim;
      resim.alt = m.gonderen + " bir resim paylaştı";
      resim.addEventListener("load", function () {
        // Resim yüklenince boyu değişir; en alttaysak yine en alta kay
        if (sohbetAlani.scrollHeight - sohbetAlani.scrollTop - sohbetAlani.clientHeight < 400) {
          sohbetAlani.scrollTop = sohbetAlani.scrollHeight;
        }
      });
      bag.appendChild(resim);
      li.appendChild(bag);
    }
    mesajlar.appendChild(li);
  }

  function yokla(ilk) {
    if (!acikSohbet || (!ilk && document.visibilityState !== "visible")) return;
    var s = acikSohbet;
    fetch("/sohbet/yeni?" + s.tur + "=" + s.id + "&sonra=" + (ilk ? 0 : sonId), {credentials: "same-origin"})
      .then(function (c) { return c.ok ? c.json() : null; })
      .then(function (veri) {
        if (acikSohbet !== s) return;                 // Bu arada başka sohbete geçildi
        if (!veri) {
          if (ilk) bilgi.textContent = "Bu sohbet açılamadı.";
          return;
        }
        var enAltta = sohbetAlani.scrollTop + sohbetAlani.clientHeight >= sohbetAlani.scrollHeight - 60;
        veri.mesajlar.forEach(function (m) { mesajiEkle(m); sonId = m.id; });
        if (ilk) {
          form.hidden = !veri.yazabilir;
          resimSec.hidden = !veri.resim_izni;
          resimDosyasi.value = "";
          bilgi.textContent = veri.yazabilir ? (veri.mesajlar.length ? "" : "Henüz mesaj yok. İlk mesajı sen yaz!")
                                             : veri.sebep;
          if (veri.yazabilir && odakIste) kutu.focus();
        } else if (veri.mesajlar.length) {
          bilgi.textContent = "";
        }
        if (ilk || (veri.mesajlar.length && enAltta)) sohbetAlani.scrollTop = sohbetAlani.scrollHeight;
      })
      .catch(function () {});
  }

  function sohbetiAc(s, odak) {
    durdur();
    odakIste = !!odak;
    acikSohbet = s;
    sonId = 0;
    durumuKaydet();
    baslik.textContent = s.ad;
    geri.hidden = false;
    tamEkran.href = s.sayfa;
    liste.hidden = true;
    mesajlar.textContent = "";
    bilgi.textContent = "Yükleniyor…";
    sohbetAlani.hidden = false;
    form.hidden = true;
    yokla(true);
    zamanlayici = setInterval(function () { yokla(false); }, saniye);
  }

  form.addEventListener("submit", function (olay) {
    olay.preventDefault();
    var metin = kutu.value.trim();
    var dosya = resimSec.hidden ? null : resimDosyasi.files[0];
    if ((!metin && !dosya) || !acikSohbet) return;
    var veri = new FormData();
    veri.append("csrf", panel.dataset.csrf);
    veri.append("tur", acikSohbet.tur);
    veri.append("id", acikSohbet.id);
    veri.append("metin", metin);
    if (dosya) veri.append("resim", dosya);
    var gonderDugmesi = form.querySelector("button");
    gonderDugmesi.disabled = true;
    fetch("/sohbet/gonder", {method: "POST", body: veri, credentials: "same-origin"})
      .then(function (c) { return c.json().catch(function () { return {hata: "Gönderilemedi, tekrar dene."}; }); })
      .then(function (cevap) {
        if (cevap.hata) {
          bilgi.textContent = cevap.hata;
        } else {
          kutu.value = "";
          resimDosyasi.value = "";
          bilgi.textContent = "";
          yokla(false);
        }
      })
      .catch(function () { bilgi.textContent = "İnternet bağlantını kontrol et."; })
      .then(function () { gonderDugmesi.disabled = false; kutu.focus(); });
  });

  resimDosyasi.addEventListener("change", function () {
    bilgi.textContent = resimDosyasi.files.length ? "Seçilen resim: " + resimDosyasi.files[0].name + " (Gönder'e bas)" : "";
  });

  // Enter: gönder, Shift+Enter: yeni satır
  kutu.addEventListener("keydown", function (o) {
    if (o.key === "Enter" && !o.shiftKey) {
      o.preventDefault();
      form.requestSubmit ? form.requestSubmit() : form.dispatchEvent(new Event("submit", {cancelable: true}));
    }
  });

  // --- Aç / kapat ---
  function ac(sohbet, odak) {
    panel.hidden = false;
    dugme.setAttribute("aria-expanded", "true");
    if (sohbet) sohbetiAc(sohbet, odak); else listeyiGoster();
  }
  function kapat() {
    durdur();
    panel.hidden = true;
    dugme.setAttribute("aria-expanded", "false");
    durumuKaydet();
    dugme.focus();
  }
  dugme.addEventListener("click", function () { panel.hidden ? ac(acikSohbet, true) : kapat(); });
  // "Tam ekran"a geçince panel bir sonraki sayfada kendiliğinden açılmasın
  tamEkran.addEventListener("click", function () {
    try { sessionStorage.setItem("kodkoc-panel", JSON.stringify({acik: false, sohbet: null})); } catch (e) {}
  });
  document.getElementById("panel-kapat").addEventListener("click", kapat);
  geri.addEventListener("click", listeyiGoster);
  document.addEventListener("keydown", function (o) {
    if (o.key === "Escape" && !panel.hidden) kapat();
  });

  dugme.hidden = false;           // JavaScript çalışıyor, düğmeyi göster

  // Önceki sayfada panel açıktıysa aynı yerden devam et. Telefonda panel bütün ekranı kapladığı için
  // orada kendiliğinden açılmaz (yoksa öğrenci tıkladığı sayfayı göremezdi).
  try {
    var kayitli = JSON.parse(sessionStorage.getItem("kodkoc-panel") || "null");
    if (kayitli && kayitli.sohbet) acikSohbet = kayitli.sohbet;
    if (kayitli && kayitli.acik && window.innerWidth > 600) ac(kayitli.sohbet, false);
  } catch (e) {}
})();
