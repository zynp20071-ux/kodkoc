"""
Sınıf raporu ve "Bugün ne yapayım?" önerisi testleri.
"""

import re
from datetime import date, timedelta

import pytest

import app as uygulama
from conftest import yol_haritasi_cikar


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


def gun(fark):
    return (date.today() + timedelta(days=fark)).isoformat()


# ---------------------------------------------------------------------------
# "Bugün ne yapayım?" kuralları (veritabanı olmadan, tek tek)
# ---------------------------------------------------------------------------

DEVAM = {"harita_id": 1, "adim_id": 10, "baslik": "Adım 2: Görev Ekleme", "sira": 2}


def hedef(kalan, baslik="Adım 3: Listeleme", sira=3):
    return {"harita_id": 1, "adim_id": 11, "baslik": baslik, "sira": sira, "kalan": kalan}


def oneri(hedefler=(), devam=DEVAM, ipucu=0, sinifta=False, seri=0, bugun_calisti=False):
    with uygulama.app.test_request_context():
        return uygulama.bugun_onerisi(list(hedefler), devam, ipucu, sinifta, seri, bugun_calisti)


def test_oncelik_1_gecmis_hedef():
    sonuc = oneri([hedef(1), hedef(-2)], ipucu=3, seri=5)
    assert "2 gün önce geçti" in sonuc["metin"] and "Adım 3: Listeleme" in sonuc["metin"]
    assert sonuc["adres"].endswith("#adim-11")


def test_oncelik_2_bugun_ya_da_yarin_biten_hedef():
    assert "hedefi yarın" in oneri([hedef(5), hedef(1)], ipucu=3)["metin"]
    assert "hedefi bugün" in oneri([hedef(0)])["metin"]


def test_uzak_hedef_oneri_olmaz():
    assert "Sıradaki adımın" in oneri([hedef(5)])["metin"]


def test_oncelik_3_takildigi_adim():
    assert "öğretmenine sor" in oneri(ipucu=2, sinifta=True)["metin"]
    assert "koça bir soru sor" in oneri(ipucu=2, sinifta=False)["metin"]


def test_oncelik_4_seri():
    sonuc = oneri(seri=4, bugun_calisti=False)
    assert "Serin 4 gün" in sonuc["metin"] and sonuc["adres"].endswith("#adim-10")
    assert "Serin" not in oneri(seri=4, bugun_calisti=True)["metin"]   # Bugün çalıştıysa seri uyarısı yok


def test_oncelik_5_ve_6():
    assert "Sıradaki adımın: “Adım 2: Görev Ekleme”" in oneri()["metin"]
    sonuc = oneri(devam=None)
    assert "Devam eden bir yol haritan yok" in sonuc["metin"] and sonuc["adres"] == "#form"


def test_ana_sayfada_oneri_karti(kayit_ol):
    ali = kayit_ol("ali")
    assert "Devam eden bir yol haritan yok" in ali.get("/").text
    yol_haritasi_cikar(ali)
    sayfa = ali.get("/").text
    assert "Bugün ne yapayım?" in sayfa and "Sıradaki adımın" in sayfa


def test_ana_sayfada_takilma_onerisi(sinif):
    adim = sinif["adimlar"][0]
    sinif["ali"].post(f"/adim/{adim}/ipucu", data={})
    sinif["ali"].post(f"/adim/{adim}/ipucu", data={})
    assert "2 ipucu aldın" in sinif["ali"].get("/").text


# ---------------------------------------------------------------------------
# Sınıf raporu
# ---------------------------------------------------------------------------

def test_sinif_raporu(sinif, kayit_ol):
    ali, hoca = sinif["ali"], sinif["hoca"]
    ali.post(f"/adim/{sinif['adimlar'][0]}", data={"tamamlandi": "1"})
    ali.post(f"/adim/{sinif['adimlar'][1]}/ipucu", data={})
    ali.post(f"/adim/{sinif['adimlar'][1]}/ipucu", data={})                     # Takılan
    hoca.post(f"/ogretmen/ogrenci/{sinif['ali_id']}/adim/{sinif['adimlar'][2]}/hedef",
              data={"tarih": gun(-1)})                                          # Geciken
    kayit_ol("ayse").post("/sinifim/katil", data={"kod": sinif["kod"]})         # Başlamayan

    assert f"/ogretmen/sinif/{sinif['id']}/rapor" in hoca.get(f"/ogretmen/sinif/{sinif['id']}").text
    rapor = hoca.get(f"/ogretmen/sinif/{sinif['id']}/rapor").text
    assert "Programlama A · Sınıf raporu" in rapor
    assert "1 / 4 · %25" in rapor and "Başlamadı" in rapor
    assert "Yardıma ihtiyacı olabilir" in rapor
    assert "Hedefi geçen adımı olanlar" in rapor
    # Sınıf sayfasındaki formlar (duyuru, çıkarma, proje) raporda yok; sadece menüdeki "Çıkış" formu var
    assert rapor.count("<form") == 1 and "Duyuruyu gönder" not in rapor and "/cikar" not in rapor


def test_rapor_yetkisi(sinif, kayit_ol):
    adres = f"/ogretmen/sinif/{sinif['id']}/rapor"
    assert kayit_ol("baskahoca", "ogretmen").get(adres).status_code == 404
    assert sinif["ali"].get(adres).status_code == 302                          # Öğrenci giremez


def test_bos_sinif_raporu(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "Boş sınıf"}).headers["Location"].rsplit("/", 1)[1])
    assert "henüz kimse katılmadı" in hoca.get(f"/ogretmen/sinif/{sinif_id}/rapor").text
