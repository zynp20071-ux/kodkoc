"""
Telefona yüklenebilir uygulama (PWA), bildirim sayıları, e-postayla şifre sıfırlama ve yedek testleri.
E-posta gerçekten gönderilmez: eposta_gonder sahte bir fonksiyonla değiştirilir.
"""

import json
import re
from datetime import date, timedelta

import pytest

import app as uygulama
import veritabani
import yedek_al


# ---------------------------------------------------------------------------
# PWA ve bildirim sayıları
# ---------------------------------------------------------------------------

def test_pwa_dosyalari(istemci, kayit_ol):
    kayit_ol("ilk")                                                # Hiç kullanıcı yoksa /giris -> /kayit
    manifest = istemci.get("/static/manifest.webmanifest")
    assert manifest.status_code == 200
    veri = json.loads(manifest.get_data(as_text=True))
    assert veri["start_url"] == "/" and {i["sizes"] for i in veri["icons"]} == {"192x192", "512x512"}
    for ikon in veri["icons"]:
        assert istemci.get(ikon["src"]).status_code == 200
    sw = istemci.get("/sw.js")
    assert sw.status_code == 200 and sw.mimetype == "text/javascript" and "caches" in sw.get_data(as_text=True)
    assert istemci.get("/cevrimdisi").status_code == 200
    sayfa = istemci.get("/giris").text
    assert "manifest.webmanifest" in sayfa and 'register("/sw.js")' in sayfa
    assert "/bildirim-sayilari" not in sayfa                       # Giriş yapmamışsa yoklama yok


def test_bildirim_sayilari(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    assert ali.get("/bildirim-sayilari").get_json()["toplam"] == 0
    hoca.post(f"/sinif/{sinif_id}/sohbet", data={"metin": "Merhaba"})
    hoca.post(f"/ogretmen/sinif/{sinif_id}/odev", data={"baslik": "Ödev", "son_tarih": (date.today() + timedelta(days=3)).isoformat()})
    sayilar = ali.get("/bildirim-sayilari").get_json()
    assert sayilar["mesaj"] == 1 and sayilar["odev"] == 1 and sayilar["toplam"] == 2
    assert "/bildirim-sayilari" in ali.get("/").text


# ---------------------------------------------------------------------------
# E-postayla şifre sıfırlama
# ---------------------------------------------------------------------------

@pytest.fixture
def eposta(monkeypatch):
    giden = []
    monkeypatch.setenv("SMTP_SUNUCU", "smtp.ornek.com")
    monkeypatch.setattr(uygulama, "eposta_gonder", lambda alici, konu, metin: giden.append((alici, metin)))
    return giden


def baglanti_bul(metin):
    return re.search(r"http://localhost(/sifre-sifirla/\S+)", metin).group(1)


def test_eposta_kapaliyken(istemci, kayit_ol, monkeypatch):
    monkeypatch.delenv("SMTP_SUNUCU", raising=False)
    kayit_ol("ilk")
    assert "öğretmenine söyle" in istemci.get("/sifremi-unuttum").text
    assert "Şifremi unuttum" in istemci.get("/giris").text
    assert 'id="eposta"' not in kayit_ol("ali").get("/profil").text          # E-posta kutusu yok


def test_sifre_sifirlama_akisi(istemci, kayit_ol, eposta):
    ali = kayit_ol("ali")
    ali.post("/profil/eposta", data={"eposta": "ali@ornek.com"})
    assert "ali@ornek.com" in ali.get("/profil").text

    cevap = istemci.post("/sifremi-unuttum", data={"kullanici_adi": "ALI"}, follow_redirects=True)
    assert "sıfırlama bağlantısını gönderdik" in cevap.text
    assert len(eposta) == 1 and eposta[0][0] == "ali@ornek.com"
    adres = baglanti_bul(eposta[0][1])

    assert "Yeni şifreni belirle" in istemci.get(adres).text
    istemci.post(adres, data={"yeni_sifre": "kisa", "yeni_sifre_tekrar": "kisa"})       # Kısa: olmaz
    istemci.post(adres, data={"yeni_sifre": "yenisifre1", "yeni_sifre_tekrar": "yenisifre1"})
    assert veritabani.kullanici_dogrula("ali", "yenisifre1") is not None
    assert veritabani.kullanici_dogrula("ali", "sifre123") is None
    # Bağlantı bir kez kullanılır
    assert "süresi dolmuş ya da kullanılmış" in istemci.get(adres, follow_redirects=True).text


def test_ayni_cevap_bilgi_sizdirmaz(istemci, kayit_ol, eposta):
    kayit_ol("ayse")                                                         # E-postası yok
    for ad in ("ayse", "boyle_biri_yok"):
        cevap = istemci.post("/sifremi-unuttum", data={"kullanici_adi": ad}, follow_redirects=True)
        assert "sıfırlama bağlantısını gönderdik" in cevap.text
    assert eposta == []


def test_sifirlama_siniri_ve_sure(istemci, kayit_ol, eposta):
    ali = kayit_ol("ali")
    ali.post("/profil/eposta", data={"eposta": "ali@ornek.com"})
    for _ in range(uygulama.EN_FAZLA_SIFIRLAMA_SAAT + 2):
        istemci.post("/sifremi-unuttum", data={"kullanici_adi": "ali"})
    assert len(eposta) == uygulama.EN_FAZLA_SIFIRLAMA_SAAT
    # Süresi dolmuş jeton geçersiz
    adres = baglanti_bul(eposta[0][1])
    baglanti = veritabani.baglan()
    try:
        baglanti.execute("UPDATE sifre_sifirlama SET son_gecerlilik = '2000-01-01 00:00:00'")
        baglanti.commit()
    finally:
        baglanti.close()
    assert "süresi dolmuş" in istemci.get(adres, follow_redirects=True).text
    assert istemci.get("/sifre-sifirla/uydurma-jeton").status_code == 302


def test_jetonun_kendisi_saklanmaz(istemci, kayit_ol, eposta):
    ali = kayit_ol("ali")
    ali.post("/profil/eposta", data={"eposta": "ali@ornek.com"})
    istemci.post("/sifremi-unuttum", data={"kullanici_adi": "ali"})
    jeton = baglanti_bul(eposta[0][1]).rsplit("/", 1)[1]
    yedek = json.dumps(veritabani.tablonun_satirlari("sifre_sifirlama"))
    assert jeton not in yedek and uygulama.jeton_ozeti(jeton) in yedek


def test_eposta_dogrulama(kayit_ol, eposta):
    ali = kayit_ol("ali")
    ali.post("/profil/eposta", data={"eposta": "mail-degil"})
    assert veritabani.eposta_getir(ali.kullanici["id"]) is None
    ali.post("/profil/eposta", data={"eposta": "ali@ornek.com"})
    ali.post("/profil/eposta", data={"eposta": ""})                           # Boş: silinir
    assert veritabani.eposta_getir(ali.kullanici["id"]) is None


# ---------------------------------------------------------------------------
# Yedek
# ---------------------------------------------------------------------------

def test_yedek_al_ve_geri_yukle(kayit_ol, tmp_path):
    from conftest import yol_haritasi_cikar
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/not", data={"not_metni": "yedekte olmalı"})
    yol = yedek_al.yedek_al(str(tmp_path))
    with open(yol, encoding="utf-8") as dosya:
        veri = json.load(dosya)
    assert veri["tablolar"]["kullanicilar"][0]["kullanici_adi"] == "ali"
    assert any(a["not_metni"] == "yedekte olmalı" for a in veri["tablolar"]["adimlar"])
    assert set(yedek_al.SIRA) <= set(veri["tablolar"])                       # Her tablo sıralı listede

    # Dolu veritabanına geri yükleme yapılmaz
    with pytest.raises(SystemExit):
        yedek_al.geri_yukle(yol)

    # Boşalt, geri yükle, aynı veriler gelsin
    baglanti = veritabani.baglan()
    try:
        for tablo in reversed(yedek_al.SIRA):
            baglanti.execute(f"DELETE FROM {tablo}")
        baglanti.commit()
    finally:
        baglanti.close()
    sayilar = yedek_al.geri_yukle(yol)
    assert sayilar["kullanicilar"] == 1 and sayilar["adimlar"] == 4
    assert "yedekte olmalı" in ali.get(f"/yol-haritasi/{harita_id}").text   # Oturum ve id'ler aynı
    kayit_ol("yeni")                                                          # Sayaç bozulmadı (id çakışmaz)
