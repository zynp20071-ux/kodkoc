"""
Canlı site için hesap işlemleri testleri:
  - Kalan yapay zekâ hakkı gösterimi ve öğretmen tablosundaki 7 günlük kullanım
  - Öğretmenin öğrenci şifresini sıfırlaması (geçici şifre, zorunlu şifre değiştirme)
  - Kullanıcının kendi hesabını ve bütün verilerini silmesi
"""

import re

import pytest

import app as uygulama
import veritabani
from conftest import yol_haritasi_cikar


@pytest.fixture
def sinif(kayit_ol):
    """Bir öğretmen, bir sınıf ve sınıfa katılmış bir öğrenci (Ali)."""
    hoca = kayit_ol("hoca", "ogretmen")
    cevap = hoca.post("/ogretmen/sinif", data={"ad": "Programlama A"})
    sinif_id = int(cevap.headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    return {"hoca": hoca, "ali": ali, "id": sinif_id, "kod": kod}


def gecici_sifreyi_al(hoca, ogrenci_id):
    sayfa = hoca.post(f"/ogretmen/ogrenci/{ogrenci_id}/sifre-sifirla").text
    return re.search(r"geçici şifre</span>\s*<strong>([a-z0-9]{8})</strong>", sayfa).group(1)


# ---------------------------------------------------------------------------
# Kalan yapay zekâ hakkı ve sınıfın kullanımı
# ---------------------------------------------------------------------------

def test_kalan_hak_ana_sayfada_ve_profilde_gorunur(kayit_ol):
    ali = kayit_ol("ali")
    sinir = uygulama.GUNLUK_YZ_SINIRI
    assert f"{sinir} / {sinir}" in ali.get("/").text
    yol_haritasi_cikar(ali)
    assert f"{sinir - 1} / {sinir}" in ali.get("/").text
    assert f"{sinir - 1} / {sinir}" in ali.get("/profil").text


def test_ogretmen_tablosunda_7_gunluk_yapay_zeka_kullanimi(sinif):
    harita_id, adimlar = yol_haritasi_cikar(sinif["ali"])            # 1 istek
    sinif["ali"].post(f"/adim/{adimlar[0]}/ipucu", data={"soru": ""})  # 2. istek
    satir = veritabani.sinif_ozeti(sinif["id"])[0]
    assert satir["yz_hafta"] == 2
    assert "Yapay zekâ (7 gün)" in sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}").text
    csv_metin = sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}/indir").data.decode("utf-8-sig")
    assert "Yapay zekâ (7 gün)" in csv_metin.splitlines()[0]


def test_7_gunden_eski_kullanim_sayilmaz(sinif):
    b = veritabani.baglan()
    b.execute("INSERT INTO yz_kullanimi (kullanici_id, gun, sayi) VALUES (?, '2020-01-01', 30)",
              (sinif["ali"].kullanici["id"],))
    b.commit()
    b.close()
    assert veritabani.sinif_ozeti(sinif["id"])[0]["yz_hafta"] == 0


# ---------------------------------------------------------------------------
# Öğretmenin şifre sıfırlaması
# ---------------------------------------------------------------------------

def test_ogretmen_gecici_sifre_verir_eski_sifre_calismaz(sinif, istemci):
    ali_id = sinif["ali"].kullanici["id"]
    sifre = gecici_sifreyi_al(sinif["hoca"], ali_id)
    assert veritabani.kullanici_dogrula("ali", "sifre123") is None       # Eski şifre artık geçersiz
    assert veritabani.kullanici_dogrula("ali", sifre) is not None
    assert not set(sifre) & set("01lio")                                 # Karışan karakter yok


def test_gecici_sifre_sayfasi_onbellege_alinmaz(sinif):
    cevap = sinif["hoca"].post(f"/ogretmen/ogrenci/{sinif['ali'].kullanici['id']}/sifre-sifirla")
    assert cevap.headers["Cache-Control"] == "no-store"


def test_gecici_sifreyle_giren_once_sifresini_degistirmeli(sinif, istemci):
    sifre = gecici_sifreyi_al(sinif["hoca"], sinif["ali"].kullanici["id"])
    istemci.post("/giris", data={"kullanici_adi": "ali", "sifre": sifre})
    # Başka sayfaya gidemez, profile yönlendirilir
    cevap = istemci.get("/gecmis")
    assert cevap.status_code == 302 and "/profil" in cevap.headers["Location"]
    assert istemci.post("/yol-haritasi", data={"proje": "x"}).status_code == 302
    assert "geçici şifreyle girdin" in istemci.get("/profil").text
    # Kendi şifresini belirleyince serbest
    istemci.post("/profil/sifre", data={"eski_sifre": sifre, "yeni_sifre": "yeni123",
                                        "yeni_sifre_tekrar": "yeni123"})
    assert istemci.get("/gecmis").status_code == 200
    assert veritabani.kullanici_dogrula("ali", "yeni123")["gecici_sifre"] == 0


def test_sifre_sifirlama_kilidi_da_acar(sinif, istemci):
    for _ in range(uygulama.EN_FAZLA_YANLIS_GIRIS):
        istemci.post("/giris", data={"kullanici_adi": "ali", "sifre": "tahmin"})
    sifre = gecici_sifreyi_al(sinif["hoca"], sinif["ali"].kullanici["id"])
    assert istemci.post("/giris", data={"kullanici_adi": "ali", "sifre": sifre}).status_code == 302


def test_baska_sinifin_ogrencisinin_sifresi_sifirlanamaz(sinif, kayit_ol):
    baska_hoca = kayit_ol("baskahoca", "ogretmen")
    ali_id = sinif["ali"].kullanici["id"]
    assert baska_hoca.post(f"/ogretmen/ogrenci/{ali_id}/sifre-sifirla").status_code == 404
    assert veritabani.kullanici_dogrula("ali", "sifre123") is not None   # Şifre değişmedi


def test_ogrenci_sifre_sifirlayamaz(sinif, kayit_ol):
    ayse = kayit_ol("ayse")
    cevap = ayse.post(f"/ogretmen/ogrenci/{sinif['ali'].kullanici['id']}/sifre-sifirla")
    assert cevap.status_code == 302                                       # Öğretmen sayfası, geri gönderilir
    assert veritabani.kullanici_dogrula("ali", "sifre123") is not None


def test_ogretmen_sinifa_katilmis_ogretmenin_sifresini_sifirlayamaz(sinif, kayit_ol):
    # Bir öğretmen hesabı kodla sınıfa katılmış olsa bile şifresi sıfırlanamaz
    diger = kayit_ol("digerhoca", "ogretmen")
    diger.post("/sinifim/katil", data={"kod": sinif["kod"]})
    cevap = sinif["hoca"].post(f"/ogretmen/ogrenci/{diger.kullanici['id']}/sifre-sifirla")
    assert cevap.status_code == 404
    assert veritabani.kullanici_dogrula("digerhoca", "sifre123") is not None


# ---------------------------------------------------------------------------
# Hesap silme
# ---------------------------------------------------------------------------

def tablo_sayisi(tablo):
    b = veritabani.baglan()
    try:
        return b.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0]
    finally:
        b.close()


def test_ogrenci_hesabini_ve_butun_verilerini_siler(sinif):
    ali = sinif["ali"]
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/ipucu", data={"soru": ""})
    ali.post(f"/adim/{adimlar[0]}/soru", data={"soru": "Liste nedir?"})
    ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": "print(1)"})
    sinif["hoca"].post(f"/ogretmen/ogrenci/{ali.kullanici['id']}/adim/{adimlar[0]}/yorum",
                       data={"metin": "Güzel gidiyorsun"})

    cevap = ali.post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    assert cevap.status_code == 302
    assert veritabani.kullanici_dogrula("ali", "sifre123") is None
    for tablo in ("yol_haritalari", "adimlar", "ipuclari", "koc_sorulari", "kod_incelemeleri",
                  "ogretmen_yorumlari", "sinif_uyeleri", "yz_kullanimi"):
        assert tablo_sayisi(tablo) == 0, f"{tablo} tablosunda veri kaldı"
    assert ali.get("/").status_code == 302                       # Oturum kapandı
    # Öğretmen ve sınıfı yerinde duruyor
    assert veritabani.kullanici_dogrula("hoca", "sifre123") is not None
    assert tablo_sayisi("siniflar") == 1


def test_ogretmen_hesabini_silince_siniflari_da_silinir(sinif):
    sinif["hoca"].post(f"/ogretmen/sinif/{sinif['id']}/duyuru", data={"metin": "Merhaba sınıf"})
    assert sinif["hoca"].post("/profil/sil", data={"sifre": "sifre123", "onay": "sil"}).status_code == 302
    assert tablo_sayisi("siniflar") == 0 and tablo_sayisi("duyurular") == 0
    assert tablo_sayisi("sinif_uyeleri") == 0
    assert veritabani.kullanici_dogrula("ali", "sifre123") is not None   # Öğrenci etkilenmedi


def test_yanlis_sifre_ya_da_onay_yoksa_silinmez(kayit_ol):
    ali = kayit_ol("ali")
    yol_haritasi_cikar(ali)
    assert "yanlış" in ali.post("/profil/sil", data={"sifre": "yanlis", "onay": "SİL"},
                                follow_redirects=True).text
    assert "SİL" in ali.post("/profil/sil", data={"sifre": "sifre123", "onay": "evet"},
                             follow_redirects=True).text
    assert veritabani.kullanici_dogrula("ali", "sifre123") is not None
    assert tablo_sayisi("yol_haritalari") == 1


def test_baskasinin_verisine_dokunmaz(kayit_ol):
    ali, ayse = kayit_ol("ali"), kayit_ol("ayse")
    yol_haritasi_cikar(ali)
    yol_haritasi_cikar(ayse)
    ali.post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    assert len(veritabani.tum_yol_haritalari(ayse.kullanici["id"])) == 1


def test_silinen_kullanici_adi_yeniden_alinabilir(kayit_ol):
    ali = kayit_ol("ali")
    ali.post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    assert kayit_ol("ali", sifre="baska123").kullanici is not None
