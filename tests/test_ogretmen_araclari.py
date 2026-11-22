"""Öğretmen araçları testleri: proje şablonları, takvim, katılım (7 gündür girmeyenler)."""

import re
from datetime import date, timedelta

import pytest

import app as uygulama
import veritabani
from conftest import yol_haritasi_cikar


def gun(fark):
    return (date.today() + timedelta(days=fark)).isoformat()


@pytest.fixture
def sinif(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    hoca.post(f"/ogretmen/sinif/{sinif_id}/proje", data={"proje": "Kütüphane programı"})
    return {"hoca": hoca, "ali": ali, "id": sinif_id, "kod": kod}


SABLON = """Adım 1: Menüyü hazırla
Menüyü döngüyle göster.
Öğrenilecek: while, input

Kitap ekleme
- Kitabı listeye ekle.


Kaydetme
Dosyaya yaz."""


# ---------------------------------------------------------------------------
# Şablonlar
# ---------------------------------------------------------------------------

def test_sablon_adimlari():
    adimlar = uygulama.sablon_adimlari(SABLON)
    assert [b for b, _ in adimlar] == ["Menüyü hazırla", "Kitap ekleme", "Kaydetme"]
    assert adimlar[0][1] == "Menüyü döngüyle göster.\nÖğrenilecek: while, input"
    metin = uygulama.sablondan_yol_haritasi({"ad": "Kütüphane", "adimlar": SABLON})
    parca = veritabani.cevabi_parcala(metin)
    assert [b for b, _ in parca["adimlar"]] == ["Adım 1: Menüyü hazırla", "Adım 2: Kitap ekleme", "Adım 3: Kaydetme"]
    assert "- Menüyü döngüyle göster." in parca["adimlar"][0][1]
    assert "- Kitabı listeye ekle." in parca["adimlar"][1][1]


def test_sablonla_sinif_projesi(sinif, sahte_yapay_zeka):
    hoca, ali = sinif["hoca"], sinif["ali"]
    hoca.post("/ogretmen/sablonlar", data={"ad": "Kütüphane şablonu", "adimlar": SABLON})
    sablon_id = veritabani.ogretmenin_sablonlari(hoca.kullanici["id"])[0]["id"]
    assert "Menüyü hazırla" in hoca.get(f"/ogretmen/sablon/{sablon_id}").text          # Önizleme
    hoca.post(f"/ogretmen/sinif/{sinif['id']}/sablon", data={"sablon_id": str(sablon_id)})
    assert "Şablonum: Kütüphane şablonu" in hoca.get(f"/ogretmen/sinif/{sinif['id']}").text

    kalan_once = uygulama.kalan_yz_hakki(ali.kullanici["id"])
    cevap = ali.post("/yol-haritasi", data={"proje": "Kütüphane programı", "bilgi": "",
                                            "sinif_proje": str(sinif["id"])})
    harita_id = int(cevap.headers["Location"].rsplit("/", 1)[1])
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert "Adım 1: Menüyü hazırla" in sayfa and "Adım 3: Kaydetme" in sayfa
    assert sahte_yapay_zeka["yol_haritasi"] == []                                      # Yapay zekâ çağrılmadı
    assert uygulama.kalan_yz_hakki(ali.kullanici["id"]) == kalan_once                  # Hak harcanmadı
    assert "1 sınıfta kullanılıyor" in hoca.get("/ogretmen/sablonlar").text

    # Sınıf projesi olmadan (kendi projesi) yine yapay zekâ çalışır
    ali.post("/yol-haritasi", data={"proje": "Kendi oyunum", "bilgi": ""})
    assert sahte_yapay_zeka["yol_haritasi"] == ["Kendi oyunum"]


def test_sablon_dogrulama_ve_duzenleme(sinif):
    hoca = sinif["hoca"]
    hoca.post("/ogretmen/sablonlar", data={"ad": "", "adimlar": SABLON})
    hoca.post("/ogretmen/sablonlar", data={"ad": "Boş", "adimlar": "   "})
    hoca.post("/ogretmen/sablonlar", data={"ad": "Çok", "adimlar": "\n\n".join(f"Adım {i}" for i in range(30))})
    assert veritabani.ogretmenin_sablonlari(hoca.kullanici["id"]) == []
    hoca.post("/ogretmen/sablonlar", data={"ad": "İlk", "adimlar": "Tek adım"})
    sablon_id = veritabani.ogretmenin_sablonlari(hoca.kullanici["id"])[0]["id"]
    hoca.post(f"/ogretmen/sablon/{sablon_id}", data={"ad": "Yeni ad", "adimlar": "Bir\n\nİki"})
    assert veritabani.sablon_getir(sablon_id)["ad"] == "Yeni ad"
    hoca.post(f"/ogretmen/sinif/{sinif['id']}/sablon", data={"sablon_id": str(sablon_id)})
    hoca.post(f"/ogretmen/sablon/{sablon_id}", data={"islem": "sil"})
    assert veritabani.sablon_getir(sablon_id) is None
    assert veritabani.sinif_getir(sinif["id"], hoca.kullanici["id"])["sablon_id"] is None


def test_sablon_yetkileri(sinif, kayit_ol):
    sinif["hoca"].post("/ogretmen/sablonlar", data={"ad": "Benim", "adimlar": "Bir"})
    sablon_id = veritabani.ogretmenin_sablonlari(sinif["hoca"].kullanici["id"])[0]["id"]
    baskahoca = kayit_ol("baskahoca", "ogretmen")
    assert baskahoca.get(f"/ogretmen/sablon/{sablon_id}").status_code == 404
    assert baskahoca.post(f"/ogretmen/sablon/{sablon_id}", data={"islem": "sil"}).status_code == 404
    b_id = int(baskahoca.post("/ogretmen/sinif", data={"ad": "B"}).headers["Location"].rsplit("/", 1)[1])
    assert baskahoca.post(f"/ogretmen/sinif/{b_id}/sablon", data={"sablon_id": str(sablon_id)}).status_code == 404
    assert sinif["ali"].get("/ogretmen/sablonlar").status_code == 302


# ---------------------------------------------------------------------------
# Takvim
# ---------------------------------------------------------------------------

def test_ogrenci_takvimi(sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[1]}/hedef", data={"tarih": gun(0)})
    hoca.post(f"/ogretmen/sinif/{sinif['id']}/odev", data={"baslik": "Hesap ödevi", "son_tarih": gun(0)})
    sayfa = ali.get("/takvim").text
    assert "Adım 2: Görev Ekleme" in sayfa and "Ödev: Hesap ödevi" in sayfa
    assert f"/yol-haritasi/{harita_id}#adim-{adimlar[1]}" in sayfa
    assert re.search(r'<td class="[^"]*bugun', sayfa)


def test_takvim_ay_gezinme(kayit_ol):
    ali = kayit_ol("ali")
    assert "Ocak 2027" in ali.get("/takvim?ay=2027-01").text
    sayfa = ali.get("/takvim?ay=2026-12").text
    assert "Aralık 2026" in sayfa and "ay=2026-11" in sayfa and "ay=2027-01" in sayfa
    assert ali.get("/takvim?ay=bozuk").status_code == 200                       # Geçersizse bu ay
    assert ali.get("/takvim?ay=2026-13").status_code == 200


def test_ogretmen_takvimi(sinif):
    sinif["hoca"].post(f"/ogretmen/sinif/{sinif['id']}/odev", data={"baslik": "Proje teslimi", "son_tarih": gun(0)})
    sayfa = sinif["hoca"].get("/takvim").text
    assert "Ödev: Proje teslimi (A)" in sayfa and "/ogretmen/odev/" in sayfa


# ---------------------------------------------------------------------------
# Katılım
# ---------------------------------------------------------------------------

def test_katilim(sinif, kayit_ol):
    hoca, ali = sinif["hoca"], sinif["ali"]
    ayse = kayit_ol("ayse")
    ayse.post("/sinifim/katil", data={"kod": sinif["kod"]})
    # Ali 10 gün önce girmiş gibi yapalım; Ayşe bugün girdi
    baglanti = veritabani.baglan()
    try:
        baglanti.execute("UPDATE kullanicilar SET son_giris = ? WHERE id = ?", (gun(-10), ali.kullanici["id"]))
        baglanti.commit()
    finally:
        baglanti.close()
    sayfa = hoca.get(f"/ogretmen/sinif/{sinif['id']}").text
    assert "1 öğrenci 7 gündür girmedi" in sayfa and "son giriş" in sayfa
    assert "1 öğrenci 7 gündür girmedi" in hoca.get("/ogretmen").text
    assert "7 gündür siteye girmeyenler" in hoca.get(f"/ogretmen/sinif/{sinif['id']}/rapor").text

    ali.get("/")                                                                   # Ali bugün girdi
    assert "7 gündür girmedi" not in hoca.get(f"/ogretmen/sinif/{sinif['id']}").text
    assert veritabani.kullanici_getir(ali.kullanici["id"])["son_giris"] == gun(0)


def test_girmeyenler_hesabi():
    bugun = date(2026, 11, 23)
    ogrenciler = [{"son_giris": None}, {"son_giris": "2026-11-16"}, {"son_giris": "2026-11-17"}]
    assert uygulama.girmeyenler(ogrenciler, bugun) == ogrenciler[:2]
