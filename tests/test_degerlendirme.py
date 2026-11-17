"""
Öğretmen değerlendirmesi, öğrencinin kendi hedefleri ve öğretmen paneli özeti testleri.
"""

import re
from datetime import date, timedelta

import pytest

import veritabani
from conftest import adim_bolumu, yol_haritasi_cikar


@pytest.fixture
def sinif(kayit_ol):
    """Bir öğretmen, bir sınıf ve sınıfa katılmış, yol haritası çıkarmış bir öğrenci (Ali)."""
    hoca = kayit_ol("hoca", "ogretmen")
    cevap = hoca.post("/ogretmen/sinif", data={"ad": "Programlama A"})
    sinif_id = int(cevap.headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    harita_id, adimlar = yol_haritasi_cikar(ali)
    return {"hoca": hoca, "ali": ali, "id": sinif_id, "kod": kod,
            "ali_id": ali.kullanici["id"], "harita_id": harita_id, "adimlar": adimlar}


def degerlendir(s, puan, metin="", ogretmen=None, harita_id=None):
    k = ogretmen or s["hoca"]
    return k.post(f"/ogretmen/ogrenci/{s['ali_id']}/yol-haritasi/{harita_id or s['harita_id']}/degerlendir",
                  data={"puan": puan, "metin": metin})


def harita(s):
    return veritabani.yol_haritasi_getir(s["harita_id"], s["ali_id"])[0]


def gun(fark):
    return (date.today() + timedelta(days=fark)).isoformat()


# ---------------------------------------------------------------------------
# Öğretmen değerlendirmesi
# ---------------------------------------------------------------------------

def test_ogretmen_degerlendirir_ogrenci_gorur(sinif):
    assert degerlendir(sinif, "4", "Dosya kısmını çok iyi çözmüşsün.").status_code == 302
    sayfa = sinif["ali"].get(f"/yol-haritasi/{sinif['harita_id']}").text
    assert "Öğretmen değerlendirmesi · hoca" in sayfa
    assert "4 / 5" in sayfa and "Dosya kısmını çok iyi çözmüşsün." in sayfa
    assert sayfa.count('class="dolu"') == 4 and sayfa.count('class="bos"') == 1
    assert "★ 4/5" in sinif["ali"].get("/gecmis").text                       # Geçmiş listesinde rozet
    assert "★ 4/5" in sinif["hoca"].get(f"/ogretmen/ogrenci/{sinif['ali_id']}").text


def test_degerlendirme_kaldirilabilir(sinif):
    degerlendir(sinif, "5")
    degerlendir(sinif, "")
    assert harita(sinif)["degerlendirme_puan"] is None
    assert "Öğretmen değerlendirmesi" not in sinif["ali"].get(f"/yol-haritasi/{sinif['harita_id']}").text


@pytest.mark.parametrize("puan", ["0", "6", "abc", "4.5", "-1"])
def test_gecersiz_puan_kaydedilmez(sinif, puan):
    degerlendir(sinif, puan)
    assert harita(sinif)["degerlendirme_puan"] is None


def test_cok_uzun_geri_bildirim_kaydedilmez(sinif):
    degerlendir(sinif, "3", "x" * 1001)
    assert harita(sinif)["degerlendirme_puan"] is None


def test_yetkisiz_degerlendirme_yapilamaz(sinif, kayit_ol):
    assert degerlendir(sinif, "1", ogretmen=kayit_ol("baskahoca", "ogretmen")).status_code == 404
    assert degerlendir(sinif, "5", ogretmen=sinif["ali"]).status_code == 302     # Öğretmen sayfası değil
    # Adres çubuğuna başka bir öğrencinin yol haritası yazılırsa
    ayse_harita, _ = yol_haritasi_cikar(kayit_ol("ayse"))
    assert degerlendir(sinif, "1", harita_id=ayse_harita).status_code == 404
    assert harita(sinif)["degerlendirme_puan"] is None


def test_sinif_projesi_sutununda_puan(sinif):
    sinif["hoca"].post(f"/ogretmen/sinif/{sinif['id']}/proje", data={"proje": "Kütüphane programı"})
    cevap = sinif["ali"].post("/yol-haritasi", data={"proje": "Kütüphane programı", "sinif_proje": sinif["id"]})
    proje_haritasi = int(cevap.headers["Location"].rsplit("/", 1)[1])
    degerlendir(sinif, "5", harita_id=proje_haritasi)
    assert "★ 5</span>" in sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}").text


# ---------------------------------------------------------------------------
# Öğrencinin kendi hedefleri
# ---------------------------------------------------------------------------

def kendi_hedefi(s, adim_id, tarih, ogrenci=None):
    return (ogrenci or s["ali"]).post(f"/adim/{adim_id}/hedef", data={"tarih": tarih})


def ogretmen_hedefi(s, adim_id, tarih):
    return s["hoca"].post(f"/ogretmen/ogrenci/{s['ali_id']}/adim/{adim_id}/hedef", data={"tarih": tarih})


def test_ogrenci_kendine_hedef_koyar(sinif):
    adim = sinif["adimlar"][0]
    kendi_hedefi(sinif, adim, gun(3))
    satir = veritabani.adim_getir(adim, sinif["ali_id"])
    assert satir["hedef_tarih"] == gun(3) and satir["hedef_koyan"] == "ogrenci"
    assert "Hedefin:" in adim_bolumu(sinif["ali"].get(f"/yol-haritasi/{sinif['harita_id']}").text, adim)
    ogretmen_sayfasi = sinif["hoca"].get(f"/ogretmen/ogrenci/{sinif['ali_id']}/yol-haritasi/{sinif['harita_id']}").text
    assert "Öğrencinin hedefi:" in adim_bolumu(ogretmen_sayfasi, adim)
    # Kendi hedefi de "Yaklaşan hedefler"de çıkar
    assert "Yaklaşan hedefler" in sinif["ali"].get("/").text
    # Kaldırabilir
    kendi_hedefi(sinif, adim, "")
    assert veritabani.adim_getir(adim, sinif["ali_id"])["hedef_tarih"] is None


def test_ogrenci_ogretmenin_hedefini_degistiremez(sinif):
    adim = sinif["adimlar"][0]
    ogretmen_hedefi(sinif, adim, gun(2))
    # Form hiç görünmüyor
    assert "Kendime hedef koy" not in adim_bolumu(sinif["ali"].get(f"/yol-haritasi/{sinif['harita_id']}").text, adim)
    # Elle gönderse de olmaz: ne değiştirebilir ne kaldırabilir
    cevap = sinif["ali"].post(f"/adim/{adim}/hedef", data={"tarih": gun(30)}, follow_redirects=True)
    assert "öğretmenin koydu" in cevap.text
    kendi_hedefi(sinif, adim, "")
    satir = veritabani.adim_getir(adim, sinif["ali_id"])
    assert satir["hedef_tarih"] == gun(2) and satir["hedef_koyan"] == "ogretmen"


def test_ogretmen_ogrencinin_hedefini_degistirebilir(sinif):
    adim = sinif["adimlar"][0]
    kendi_hedefi(sinif, adim, gun(10))
    ogretmen_hedefi(sinif, adim, gun(4))
    satir = veritabani.adim_getir(adim, sinif["ali_id"])
    assert satir["hedef_tarih"] == gun(4) and satir["hedef_koyan"] == "ogretmen"


def test_baskasinin_adimina_hedef_konamaz(sinif, kayit_ol):
    ayse = kayit_ol("ayse")
    assert kendi_hedefi(sinif, sinif["adimlar"][0], gun(3), ogrenci=ayse).status_code == 404
    assert veritabani.adim_getir(sinif["adimlar"][0], sinif["ali_id"])["hedef_tarih"] is None


@pytest.mark.parametrize("tarih", ["yarin", "2026-02-30", gun(400)])
def test_ogrencinin_gecersiz_tarihi_kaydedilmez(sinif, tarih):
    kendi_hedefi(sinif, sinif["adimlar"][0], tarih)
    assert veritabani.adim_getir(sinif["adimlar"][0], sinif["ali_id"])["hedef_tarih"] is None


# ---------------------------------------------------------------------------
# Öğretmen paneli özeti
# ---------------------------------------------------------------------------

def test_ogretmen_panelinde_sinif_ozeti(sinif, kayit_ol):
    # Ali: 4 adımdan 2'si bitti (%50) ve 1 geciken adım; Ayşe sınıfta ama başlamadı
    sinif["ali"].post(f"/adim/{sinif['adimlar'][0]}", data={"tamamlandi": "1"})
    sinif["ali"].post(f"/adim/{sinif['adimlar'][1]}", data={"tamamlandi": "1"})
    ogretmen_hedefi(sinif, sinif["adimlar"][2], gun(-1))
    kayit_ol("ayse").post("/sinifim/katil", data={"kod": sinif["kod"]})

    panel = sinif["hoca"].get("/ogretmen").text
    assert "Ortalama ilerleme %50" in panel                 # Başlamayan ortalamaya katılmaz
    assert "1 öğrenci başlamadı" in panel
    assert "1 geciken adım" in panel
