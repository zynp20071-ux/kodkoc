"""
Sınıf projesi ve sınıfın son etkinlikler akışı testleri.
"""

import re

import pytest

import veritabani
from conftest import yol_haritasi_cikar

PROJE = "Python ile kütüphane takip programı: kitap ekleme, ödünç verme, dosyaya kaydetme."


@pytest.fixture
def sinif(kayit_ol):
    """Bir öğretmen, bir sınıf ve sınıfa katılmış bir öğrenci (Ali)."""
    hoca = kayit_ol("hoca", "ogretmen")
    cevap = hoca.post("/ogretmen/sinif", data={"ad": "Programlama A"})
    sinif_id = int(cevap.headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    return {"hoca": hoca, "ali": ali, "id": sinif_id, "kod": kod, "ali_id": ali.kullanici["id"]}


def proje_ver(s, metin=PROJE, ogretmen=None):
    return (ogretmen or s["hoca"]).post(f"/ogretmen/sinif/{s['id']}/proje", data={"proje": metin})


def sinif_projesiyle_baslat(s, ogrenci=None, sinif_id=None):
    """Öğrenci 'Bu projeyle başla' formunu gönderir; yeni yol haritasının id'sini döndürür."""
    k = ogrenci or s["ali"]
    cevap = k.post("/yol-haritasi", data={"proje": PROJE, "bilgi": "",
                                          "sinif_proje": sinif_id or s["id"]})
    return int(cevap.headers["Location"].rsplit("/", 1)[1])


def harita_sinifi(harita_id):
    b = veritabani.baglan()
    try:
        return b.execute("SELECT sinif_id FROM yol_haritalari WHERE id = ?", (harita_id,)).fetchone()[0]
    finally:
        b.close()


# ---------------------------------------------------------------------------
# Sınıf projesi
# ---------------------------------------------------------------------------

def test_ogrenci_sinif_projesini_ana_sayfada_gorur(sinif):
    proje_ver(sinif)
    ana = sinif["ali"].get("/").text
    assert "Öğretmeninin verdiği proje" in ana and "kütüphane takip" in ana
    assert f"sinif_proje={sinif['id']}" in ana                                # "Bu projeyle başla"
    # Bağlantıya tıklayınca form proje metniyle ve gizli sınıf alanıyla dolu gelir
    form = sinif["ali"].get(f"/?sinif_proje={sinif['id']}").text
    assert f'name="sinif_proje" value="{sinif["id"]}"' in form
    assert "kütüphane takip" in form.split('id="form"')[1]


def test_sinif_projesi_yol_haritasi_sinifa_baglanir_ve_ogretmen_ilerlemeyi_gorur(sinif):
    proje_ver(sinif)
    harita_id = sinif_projesiyle_baslat(sinif)
    assert harita_sinifi(harita_id) == sinif["id"]
    # Ana sayfada artık "devam et"
    assert "Yol haritana devam et" in sinif["ali"].get("/").text
    # Bir adım bitince öğretmenin tablosunda %25 (4 adımdan 1'i)
    adimlar = [int(x) for x in re.findall(r'id="adim-(\d+)"', sinif["ali"].get(f"/yol-haritasi/{harita_id}").text)]
    sinif["ali"].post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    tablo = sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}").text
    assert "Sınıf projesi" in tablo and "%25</a>" in tablo


def test_baslamayan_ogrenci_tabloda_baslamadi_gorunur(sinif):
    proje_ver(sinif)
    assert "Başlamadı" in sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}").text


def test_uye_olmadigi_sinifa_yol_haritasi_baglanamaz(sinif, kayit_ol):
    proje_ver(sinif)
    ayse = kayit_ol("ayse")                                # Sınıfa katılmadı
    harita_id = sinif_projesiyle_baslat(sinif, ogrenci=ayse)
    assert harita_sinifi(harita_id) is None
    assert 'name="sinif_proje"' not in ayse.get(f"/?sinif_proje={sinif['id']}").text


def test_projesi_olmayan_sinifa_baglanmaz(sinif):
    harita_id = sinif_projesiyle_baslat(sinif)              # Öğretmen proje vermedi
    assert harita_sinifi(harita_id) is None


def test_baska_ogretmen_proje_veremez_uzun_proje_kaydedilmez(sinif, kayit_ol):
    assert proje_ver(sinif, ogretmen=kayit_ol("baskahoca", "ogretmen")).status_code == 404
    proje_ver(sinif, metin="x" * 1001)
    assert veritabani.sinif_getir(sinif["id"], sinif["hoca"].kullanici["id"])["proje"] is None


def test_bos_metin_projeyi_kaldirir(sinif):
    proje_ver(sinif)
    proje_ver(sinif, metin="")
    assert "Öğretmeninin verdiği proje" not in sinif["ali"].get("/").text


def test_sinif_silinince_yol_haritasi_ogrencide_kalir(sinif):
    proje_ver(sinif)
    harita_id = sinif_projesiyle_baslat(sinif)
    sinif["hoca"].post(f"/ogretmen/sinif/{sinif['id']}/sil")
    assert harita_sinifi(harita_id) is None
    assert len(veritabani.tum_yol_haritalari(sinif["ali_id"])) == 1


def test_ogretmen_hesabini_silince_yol_haritasi_ogrencide_kalir(sinif):
    proje_ver(sinif)
    harita_id = sinif_projesiyle_baslat(sinif)
    sinif["hoca"].post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    assert harita_sinifi(harita_id) is None
    assert sinif["ali"].get(f"/yol-haritasi/{harita_id}").status_code == 200


def test_sinifim_sayfasinda_proje_gorunur(sinif):
    proje_ver(sinif)
    assert "Sınıf projesi:" in sinif["ali"].get("/sinifim").text


# ---------------------------------------------------------------------------
# Son etkinlikler akışı
# ---------------------------------------------------------------------------

def test_etkinlik_akisi_sinifin_olaylarini_gosterir(sinif):
    ali = sinif["ali"]
    harita_id, adimlar = yol_haritasi_cikar(ali, "Hesap makinesi")
    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    ali.post(f"/adim/{adimlar[1]}/ipucu", data={"soru": ""})
    ali.post(f"/adim/{adimlar[1]}/soru", data={"soru": "Liste nedir?"})
    ali.post(f"/adim/{adimlar[1]}/incele", data={"kod": "print(1)"})

    akis = veritabani.sinif_etkinlik_akisi(sinif["id"])
    assert {e["tur"] for e in akis} == {"harita", "adim", "ipucu", "soru", "inceleme"}
    sayfa = sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}").text
    for metin in ("yeni yol haritası çıkardı", "bir adımı bitirdi", "ipucu aldı",
                  "koça soru sordu", "kodunu incelettirdi"):
        assert metin in sayfa
    assert f"#adim-{adimlar[1]}" in sayfa                          # Olaydan adıma bağlantı


def test_akista_baska_sinifin_ogrencisi_gorunmez(sinif, kayit_ol):
    yol_haritasi_cikar(kayit_ol("ayse"), "Ayşe'nin gizli projesi")   # Sınıfta değil
    yol_haritasi_cikar(sinif["ali"], "Ali'nin projesi")
    akis = veritabani.sinif_etkinlik_akisi(sinif["id"])
    assert [e["kullanici_adi"] for e in akis] == ["ali"]


def test_akis_en_yeniden_eskiye_ve_sinirli(sinif):
    for i in range(3):
        yol_haritasi_cikar(sinif["ali"], f"Proje {i}")
    b = veritabani.baglan()
    b.execute("UPDATE yol_haritalari SET olusturma_zamani = '2020-01-01 10:00:00' WHERE proje = 'Proje 0'")
    b.commit()
    b.close()
    akis = veritabani.sinif_etkinlik_akisi(sinif["id"], sinir=2)
    assert len(akis) == 2 and "Proje 0" not in [e["baslik"] for e in akis]
