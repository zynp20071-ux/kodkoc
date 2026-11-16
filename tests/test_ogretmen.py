"""Öğretmen paneli testleri: sınıflar, katılım kodu, ilerleme tablosu, gizlilik ve yorumlar."""

import re

import pytest

import veritabani
from conftest import adim_bolumu, yol_haritasi_cikar


@pytest.fixture
def sinif(kayit_ol):
    """Bir öğretmen, bir sınıf ve sınıfa katılmış bir öğrenci (Ali) hazırlar."""
    hoca = kayit_ol("hoca", "ogretmen")
    cevap = hoca.post("/ogretmen/sinif", data={"ad": "Programlama A"})
    sinif_id = int(cevap.headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    return {"hoca": hoca, "ali": ali, "id": sinif_id, "kod": kod}


def test_ogretmen_kaydi_panele_gider(istemci):
    cevap = istemci.post("/kayit", data={"kullanici_adi": "hoca", "sifre": "sifre123",
                                         "sifre_tekrar": "sifre123", "rol": "ogretmen"})
    assert cevap.headers["Location"].endswith("/ogretmen")


def test_gecersiz_rol_ogrenci_sayilir(kayit_ol):
    k = kayit_ol("hileci", "admin")
    assert veritabani.kullanici_getir(k.kullanici["id"])["rol"] == "ogrenci"


def test_katilim_kodunda_karisan_karakter_yok(sinif):
    assert not set(sinif["kod"]) & set("01OI")


def test_ogrenci_ogretmen_sayfalarini_acamaz(sinif):
    ali = sinif["ali"]
    assert "sadece öğretmenler" in ali.get("/ogretmen", follow_redirects=True).text
    assert ali.get(f"/ogretmen/sinif/{sinif['id']}").status_code == 302
    ali.post("/ogretmen/sinif", data={"ad": "Sahte sınıf"})
    assert veritabani.ogretmenin_siniflari(ali.kullanici["id"]) == []


def test_kod_kucuk_harf_ve_bosluklu_da_calisir(kayit_ol, sinif):
    ayse = kayit_ol("ayse")
    kod = sinif["kod"].lower()
    cevap = ayse.post("/sinifim/katil", data={"kod": kod[:3] + " " + kod[3:]}, follow_redirects=True)
    assert "sınıfına katıldın" in cevap.text
    assert "Zaten" in ayse.post("/sinifim/katil", data={"kod": sinif["kod"]}, follow_redirects=True).text
    assert "bulunamadı" in ayse.post("/sinifim/katil", data={"kod": "YANLIS"}, follow_redirects=True).text


def test_ilerleme_tablosu_ve_takilanlar(sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    ali.post(f"/adim/{adimlar[1]}/ipucu", data={})
    ali.post(f"/adim/{adimlar[1]}/ipucu", data={})        # 2 ipucu -> "takıldı"
    ali.post(f"/adim/{adimlar[2]}/ipucu", data={})        # 1 ipucu -> listede değil

    sayfa = hoca.get(f"/ogretmen/sinif/{sinif['id']}").text
    assert "1 / 4 · %25" in sayfa
    assert "Yardıma ihtiyacı olabilir" in sayfa
    assert f"#adim-{adimlar[1]}" in sayfa and f"#adim-{adimlar[2]}" not in sayfa

    ali.post(f"/adim/{adimlar[1]}", data={"tamamlandi": "1"})
    assert "Yardıma ihtiyacı olabilir" not in hoca.get(f"/ogretmen/sinif/{sinif['id']}").text


def test_salt_okunur_gorunum(sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/not", data={"not_metni": "input() öğrendim"})
    sayfa = hoca.get(f"/ogretmen/ogrenci/{ali.kullanici['id']}/yol-haritasi/{harita_id}").text
    assert "salt okunur" in sayfa and "input() öğrendim" in sayfa
    for dugme in ["Tamamladım", "Takıldım", "Not al", "Bu yol haritasını sil"]:
        assert dugme not in sayfa
    # Sunucu da reddediyor
    assert hoca.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"}).status_code == 404
    assert hoca.get(f"/yol-haritasi/{harita_id}").status_code == 404


def test_sinifa_katilmayan_ogrenci_gorulemez(kayit_ol, sinif):
    ayse = kayit_ol("ayse")
    harita_id, _ = yol_haritasi_cikar(ayse, "Ayşe'nin gizli projesi")
    hoca = sinif["hoca"]
    assert "ayse" not in hoca.get(f"/ogretmen/sinif/{sinif['id']}").text
    assert hoca.get(f"/ogretmen/ogrenci/{ayse.kullanici['id']}").status_code == 404
    assert hoca.get(f"/ogretmen/ogrenci/{ayse.kullanici['id']}/yol-haritasi/{harita_id}").status_code == 404
    # Ali'nin adresiyle Ayşe'nin yol haritası açılamaz
    assert hoca.get(f"/ogretmen/ogrenci/{sinif['ali'].kullanici['id']}/yol-haritasi/{harita_id}").status_code == 404


def test_baska_ogretmen_sinifa_erisemez(kayit_ol, sinif):
    hoca2 = kayit_ol("hoca2", "ogretmen")
    assert hoca2.get(f"/ogretmen/sinif/{sinif['id']}").status_code == 404
    assert hoca2.get(f"/ogretmen/ogrenci/{sinif['ali'].kullanici['id']}").status_code == 404
    assert hoca2.post(f"/ogretmen/sinif/{sinif['id']}/sil").status_code == 404
    assert hoca2.post("/sinifim/katil", data={"kod": sinif["kod"]}).status_code == 404


def test_ayrilinca_erisim_kapanir(sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    ali.post(f"/sinifim/{sinif['id']}/ayril")
    assert hoca.get(f"/ogretmen/ogrenci/{ali.kullanici['id']}").status_code == 404


def test_sinif_silinince_ogrenci_verisi_kalir(sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    yol_haritasi_cikar(ali, "Ali'nin projesi")
    hoca.post(f"/ogretmen/sinif/{sinif['id']}/sil")
    assert hoca.get(f"/ogretmen/sinif/{sinif['id']}").status_code == 404
    assert "Ali&#39;nin projesi" in ali.get("/gecmis").text


# --- Öğretmen yorumları ---

def test_ogretmen_yorumu_ogrenciye_ulasir(sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ogrenci_id = ali.kullanici["id"]

    cevap = hoca.post(f"/ogretmen/ogrenci/{ogrenci_id}/adim/{adimlar[1]}/yorum",
                      data={"metin": "Döngün doğru, şimdi hata kontrolünü düşün."}, follow_redirects=True)
    assert "öğrenciye iletildi" in cevap.text

    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert "Döngün doğru" in adim_bolumu(sayfa, adimlar[1])
    assert "Öğretmen yorumu · hoca" in sayfa
    assert "Sil</button>" not in adim_bolumu(sayfa, adimlar[1])          # Öğrenci silemez
    assert "1 öğretmen yorumu" in ali.get("/gecmis").text


def test_yorum_kurallari_ve_yetki(kayit_ol, sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    harita_id, adimlar = yol_haritasi_cikar(ali)
    adres = f"/ogretmen/ogrenci/{ali.kullanici['id']}/adim/{adimlar[0]}/yorum"

    assert "1-1000 karakter" in hoca.post(adres, data={"metin": "  "}, follow_redirects=True).text
    assert "1-1000 karakter" in hoca.post(adres, data={"metin": "x" * 1001}, follow_redirects=True).text

    hoca2 = kayit_ol("hoca2", "ogretmen")                     # Sınıfı olmayan öğretmen
    assert hoca2.post(adres, data={"metin": "merhaba"}).status_code == 404

    ayse = kayit_ol("ayse")                                   # Başka öğrencinin adımı
    _, ayse_adimlar = yol_haritasi_cikar(ayse)
    adres2 = f"/ogretmen/ogrenci/{ali.kullanici['id']}/adim/{ayse_adimlar[0]}/yorum"
    assert hoca.post(adres2, data={"metin": "x"}).status_code == 404


def test_ogretmen_sadece_kendi_yorumunu_siler(kayit_ol, sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    harita_id, adimlar = yol_haritasi_cikar(ali)
    hoca.post(f"/ogretmen/ogrenci/{ali.kullanici['id']}/adim/{adimlar[0]}/yorum", data={"metin": "Güzel!"})
    yorum_id = veritabani.yol_haritasinin_yorumlari(harita_id)[adimlar[0]][0]["id"]

    hoca2 = kayit_ol("hoca2", "ogretmen")
    assert hoca2.post(f"/ogretmen/yorum/{yorum_id}/sil").status_code == 404
    assert "Yorum silindi" in hoca.post(f"/ogretmen/yorum/{yorum_id}/sil", follow_redirects=True).text
    assert "Güzel!" not in ali.get(f"/yol-haritasi/{harita_id}").text


def test_yol_haritasi_silinince_yorumlar_da_silinir(sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    harita_id, adimlar = yol_haritasi_cikar(ali)
    hoca.post(f"/ogretmen/ogrenci/{ali.kullanici['id']}/adim/{adimlar[0]}/yorum", data={"metin": "x"})
    ali.post(f"/yol-haritasi/{harita_id}/sil")
    assert veritabani.yol_haritasinin_yorumlari(harita_id) == {}
