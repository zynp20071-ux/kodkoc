"""Yeni yorum bildirimi ve sınıfı CSV olarak dışa aktarma testleri."""

import csv
import io
import re

import pytest

from conftest import yol_haritasi_cikar


@pytest.fixture
def sinif(kayit_ol):
    """Öğretmen + sınıf + sınıfa katılmış, bir yol haritası çıkarmış öğrenci (Ali)."""
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "Programlama A / Şube-1"})
                   .headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    harita_id, adimlar = yol_haritasi_cikar(ali)
    return {"hoca": hoca, "ali": ali, "id": sinif_id, "harita_id": harita_id, "adimlar": adimlar}


def yorum_yaz(sinif, adim_sirasi, metin):
    ali = sinif["ali"]
    sinif["hoca"].post(f"/ogretmen/ogrenci/{ali.kullanici['id']}/adim/{sinif['adimlar'][adim_sirasi]}/yorum",
                       data={"metin": metin})


# --- Yeni yorum bildirimi ---

def test_yorum_gelince_menude_rozet_cikar(sinif):
    ali = sinif["ali"]
    assert "menu-rozeti" not in ali.get("/gecmis").text
    yorum_yaz(sinif, 0, "Birinci yorum")
    yorum_yaz(sinif, 1, "İkinci yorum")

    sayfa = ali.get("/gecmis").text
    assert re.search(r'class="menu-rozeti"[^>]*>2</span>', sayfa)
    assert "2 yeni öğretmen yorumu" in sayfa


def test_sayfa_acilinca_yorumlar_okundu_olur(sinif):
    ali = sinif["ali"]
    yorum_yaz(sinif, 0, "Güzel gidiyorsun")

    sayfa = ali.get(f"/yol-haritasi/{sinif['harita_id']}").text
    assert "Yeni</span>" in sayfa                   # İlk açılışta "Yeni" etiketi
    assert "menu-rozeti" not in sayfa               # Aynı sayfada rozet hemen kayboldu

    sayfa = ali.get(f"/yol-haritasi/{sinif['harita_id']}").text
    assert "Güzel gidiyorsun" in sayfa and "Yeni</span>" not in sayfa   # İkinci açılışta yok
    assert "1 öğretmen yorumu" in ali.get("/gecmis").text


def test_ogretmenin_baktigi_sayfa_okundu_yapmaz(sinif):
    """Öğretmen öğrencinin sayfasına bakınca yorum öğrenci için 'yeni' kalmalı."""
    yorum_yaz(sinif, 0, "Bakalım")
    ali, hoca = sinif["ali"], sinif["hoca"]
    hoca.get(f"/ogretmen/ogrenci/{ali.kullanici['id']}/yol-haritasi/{sinif['harita_id']}")
    assert "1 yeni öğretmen yorumu" in ali.get("/gecmis").text


def test_ogretmende_rozet_yok(sinif):
    yorum_yaz(sinif, 0, "x")
    assert "menu-rozeti" not in sinif["hoca"].get("/ogretmen").text


# --- CSV dışa aktarma ---

def test_sinif_csv_olarak_indirilir(sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    ali.post(f"/adim/{sinif['adimlar'][0]}", data={"tamamlandi": "1"})
    ali.post(f"/adim/{sinif['adimlar'][1]}/ipucu", data={})

    cevap = hoca.get(f"/ogretmen/sinif/{sinif['id']}/indir")
    assert cevap.status_code == 200
    assert cevap.mimetype == "text/csv"
    baslik = cevap.headers["Content-Disposition"]
    assert "attachment" in baslik and ".csv" in baslik
    # Sınıf adındaki "/" dosya adına geçmemeli (dosya adında klasör ayracı olamaz)
    assert "/" not in baslik and "%2F" not in baslik

    veri = cevap.data
    assert veri.startswith("\ufeff".encode("utf-8"))           # Excel için BOM
    satirlar = list(csv.reader(io.StringIO(veri.decode("utf-8-sig")), delimiter=";"))
    assert satirlar[0][0] == "Öğrenci" and satirlar[0][4] == "İlerleme (%)"
    assert satirlar[1][:7] == ["ali", "1", "1", "4", "25", "1", "0"]
    assert satirlar[0][7] == "Yapay zekâ (7 gün)" and satirlar[1][7] == "2"   # 1 yol haritası + 1 ipucu
    assert re.match(r"\d\d\.\d\d\.\d{4} \d\d:\d\d", satirlar[1][8])


def test_csv_sadece_kendi_sinifinin_ogretmeni_indirir(kayit_ol, sinif):
    assert kayit_ol("hoca2", "ogretmen").get(f"/ogretmen/sinif/{sinif['id']}/indir").status_code == 404
    assert sinif["ali"].get(f"/ogretmen/sinif/{sinif['id']}/indir").status_code == 302     # öğrenci
