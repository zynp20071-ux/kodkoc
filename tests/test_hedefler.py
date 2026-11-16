"""
Hedef tarihler, sınıftan çıkarma ve haftalık özet testleri.
"""

import csv
import io
import re
from datetime import date, timedelta

import pytest

import app as uygulama
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


def hedef_koy(s, adim_id, tarih, ogretmen=None):
    k = ogretmen or s["hoca"]
    return k.post(f"/ogretmen/ogrenci/{s['ali_id']}/adim/{adim_id}/hedef", data={"tarih": tarih})


def gun(fark):
    return (date.today() + timedelta(days=fark)).isoformat()


# ---------------------------------------------------------------------------
# hedef_durumu: tarih ve tamamlanma durumuna göre etiket
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hedef, tamamlandi, beklenen", [
    (None, False, None),
    ("2026-11-20", True, "tamam"),            # Bitmişse tarih önemli değil
    ("2026-11-15", False, "gecikti"),
    ("2026-11-16", False, "yaklasiyor"),      # Bugün
    ("2026-11-18", False, "yaklasiyor"),      # 2 gün kaldı
    ("2026-11-19", False, "var"),             # 3 gün kaldı
])
def test_hedef_durumu(hedef, tamamlandi, beklenen):
    assert uygulama.hedef_durumu(hedef, tamamlandi, date(2026, 11, 16)) == beklenen


def test_hafta_basi_pazartesidir():
    assert uygulama.hafta_basi(date(2026, 11, 19)) == date(2026, 11, 16)   # Perşembe -> pazartesi
    assert uygulama.hafta_basi(date(2026, 11, 16)) == date(2026, 11, 16)   # Pazartesi kendisi
    assert uygulama.hafta_basi(date(2026, 11, 22)) == date(2026, 11, 16)   # Pazar -> aynı haftanın pazartesisi


# ---------------------------------------------------------------------------
# Hedef tarih koyma
# ---------------------------------------------------------------------------

def test_ogretmen_hedef_koyar_ogrenci_gorur(sinif):
    adim = sinif["adimlar"][1]
    assert hedef_koy(sinif, adim, gun(5)).status_code == 302
    beklenen = (date.today() + timedelta(days=5)).strftime("%d.%m.%Y")
    # Öğrencinin yol haritasında, o adımın kutusunda
    sayfa = sinif["ali"].get(f"/yol-haritasi/{sinif['harita_id']}").text
    assert f"Hedef: {beklenen}" in adim_bolumu(sayfa, adim)
    # Öğrencinin ana sayfasında "Yaklaşan hedefler"
    ana = sinif["ali"].get("/").text
    assert "Yaklaşan hedefler" in ana and "5 gün kaldı" in ana


def test_uzak_hedef_ana_sayfada_cikmaz(sinif):
    hedef_koy(sinif, sinif["adimlar"][0], gun(20))
    assert "Yaklaşan hedefler" not in sinif["ali"].get("/").text


def test_geciken_adim_her_yerde_gorunur(sinif):
    adim = sinif["adimlar"][0]
    hedef_koy(sinif, adim, gun(-2))
    sayfa = sinif["ali"].get(f"/yol-haritasi/{sinif['harita_id']}").text
    assert "Gecikti" in adim_bolumu(sayfa, adim)
    assert "2 gün gecikti" in sinif["ali"].get("/").text
    assert veritabani.sinif_ozeti(sinif["id"])[0]["geciken_adim"] == 1
    veri = sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}/indir").data.decode("utf-8-sig")
    satirlar = list(csv.reader(io.StringIO(veri), delimiter=";"))
    assert satirlar[0][-1] == "Geciken adım" and satirlar[1][-1] == "1"


def test_biten_adim_gecikmis_sayilmaz(sinif):
    adim = sinif["adimlar"][0]
    hedef_koy(sinif, adim, gun(-2))
    sinif["ali"].post(f"/adim/{adim}", data={"tamamlandi": "1"})
    assert veritabani.sinif_ozeti(sinif["id"])[0]["geciken_adim"] == 0
    assert "Yaklaşan hedefler" not in sinif["ali"].get("/").text


def test_bos_tarih_hedefi_kaldirir(sinif):
    adim = sinif["adimlar"][0]
    hedef_koy(sinif, adim, gun(3))
    hedef_koy(sinif, adim, "")
    assert veritabani.adim_getir(adim, sinif["ali_id"])["hedef_tarih"] is None


@pytest.mark.parametrize("tarih", ["31.12.2026", "yarin", "2026-02-30", gun(400), gun(-400)])
def test_gecersiz_tarih_kaydedilmez(sinif, tarih):
    adim = sinif["adimlar"][0]
    hedef_koy(sinif, adim, tarih)
    assert veritabani.adim_getir(adim, sinif["ali_id"])["hedef_tarih"] is None


def test_baska_ogretmen_ve_ogrenci_hedef_koyamaz(sinif, kayit_ol):
    adim = sinif["adimlar"][0]
    assert hedef_koy(sinif, adim, gun(3), ogretmen=kayit_ol("baskahoca", "ogretmen")).status_code == 404
    assert hedef_koy(sinif, adim, gun(3), ogretmen=sinif["ali"]).status_code == 302     # Öğretmen sayfası değil
    assert veritabani.adim_getir(adim, sinif["ali_id"])["hedef_tarih"] is None


def test_baska_ogrencinin_adimina_hedef_konamaz(sinif, kayit_ol):
    # Öğretmen Ali'yi görebiliyor ama adres çubuğuna Ayşe'nin adımını yazarsa
    ayse = kayit_ol("ayse")
    _, ayse_adimlari = yol_haritasi_cikar(ayse)
    assert hedef_koy(sinif, ayse_adimlari[0], gun(3)).status_code == 404


# ---------------------------------------------------------------------------
# Sınıftan çıkarma
# ---------------------------------------------------------------------------

def test_ogretmen_ogrenciyi_siniftan_cikarir(sinif):
    cevap = sinif["hoca"].post(f"/ogretmen/sinif/{sinif['id']}/ogrenci/{sinif['ali_id']}/cikar")
    assert cevap.status_code == 302
    assert veritabani.sinif_ozeti(sinif["id"]) == []
    assert not veritabani.ogretmen_gorebilir_mi(sinif["hoca"].kullanici["id"], sinif["ali_id"])
    assert len(veritabani.tum_yol_haritalari(sinif["ali_id"])) == 1       # Yol haritası duruyor
    # Kodla yeniden katılabilir
    sinif["ali"].post("/sinifim/katil", data={"kod": sinif["kod"]})
    assert len(veritabani.sinif_ozeti(sinif["id"])) == 1


def test_baska_ogretmenin_sinifindan_cikarilamaz(sinif, kayit_ol):
    baska = kayit_ol("baskahoca", "ogretmen")
    assert baska.post(f"/ogretmen/sinif/{sinif['id']}/ogrenci/{sinif['ali_id']}/cikar").status_code == 404
    assert len(veritabani.sinif_ozeti(sinif["id"])) == 1


# ---------------------------------------------------------------------------
# Haftalık özet
# ---------------------------------------------------------------------------

def test_haftalik_ozet(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    assert "Bu hafta" not in ali.get("/").text                 # Hiç adım bitmemişken gösterilmez
    for adim in adimlar[:3]:
        ali.post(f"/adim/{adim}", data={"tamamlandi": "1"})
    # Birini geçen haftaya taşı
    gecen = (uygulama.hafta_basi(date.today()) - timedelta(days=3)).isoformat() + " 10:00:00"
    b = veritabani.baglan()
    b.execute("UPDATE adimlar SET tamamlanma_zamani = ? WHERE id = ?", (gecen, adimlar[0]))
    b.commit()
    b.close()
    sayfa = ali.get("/").text
    assert "Bu hafta <strong>2</strong> adım bitirdin" in sayfa and "geçen hafta 1" in sayfa
    assert "Geçen haftayı geçtin" in sayfa
