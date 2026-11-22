"""
Güvenlik testleri: mesaj bildirme, engelleme, kötü kelime süzgeci, gizlilik sayfası.
"""

import re

import pytest

import app as uygulama
import veritabani


def sinif_ac(hoca, ad):
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": ad}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    return sinif_id, kod


@pytest.fixture
def okul(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    a_id, a_kod = sinif_ac(hoca, "A sınıfı")
    ali, ayse = kayit_ol("ali"), kayit_ol("ayse")
    ali.post("/sinifim/katil", data={"kod": a_kod})
    ayse.post("/sinifim/katil", data={"kod": a_kod})
    baskahoca = kayit_ol("baskahoca", "ogretmen")
    b_id, b_kod = sinif_ac(baskahoca, "B sınıfı")
    veli = kayit_ol("veli")
    veli.post("/sinifim/katil", data={"kod": b_kod})
    return {"hoca": hoca, "ali": ali, "ayse": ayse, "veli": veli, "baskahoca": baskahoca, "a": a_id}


def kid(k):
    return k.kullanici["id"]


def mesaj_idleri(k, adres):
    return [int(x) for x in re.findall(r'id="mesaj-(\d+)"', k.get(adres).text)]


# ---------------------------------------------------------------------------
# Kötü kelime süzgeci
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("metin, beklenen", [
    ("sen çok salaksın değil, salak", "sen çok salaksın değil, s****"),
    ("SALAK", "S****"),
    ("Siktirgit", "S********"),                 # Kökle başlıyor
    ("bu Gerizekalıca bir fikir", "bu G*********** bir fikir"),
    ("Kitabı götür", "Kitabı götür"),          # "göt" kısa; "götür" etkilenmez
    ("Mal varlığı, I got it, pic", "Mal varlığı, I got it, pic"),   # Başka anlamı olanlar listede yok
    ("Döngü bitmiyor", "Döngü bitmiyor"),
])
def test_kufur_suz(metin, beklenen):
    assert uygulama.kufur_suz(metin) == beklenen


def test_mesaj_ve_hakkimda_suzulur(okul):
    okul["ali"].post(f"/sinif/{okul['a']}/sohbet", data={"metin": "ayşe çok aptal"})
    assert "ayşe çok a****" in okul["ayse"].get(f"/sinif/{okul['a']}/sohbet").text
    okul["ali"].post("/profil/hakkimda", data={"hakkimda": "ben salak değilim"})
    assert "ben s**** değilim" in okul["ali"].get("/profil").text


# ---------------------------------------------------------------------------
# Bildirme
# ---------------------------------------------------------------------------

def test_sinif_mesaji_bildirme(okul):
    ali, ayse, hoca = okul["ali"], okul["ayse"], okul["hoca"]
    adres = f"/sinif/{okul['a']}/sohbet"
    ali.post(adres, data={"metin": "seni kimse sevmiyor"})
    m = mesaj_idleri(ayse, adres)[0]
    assert "Öğretmenime bildir" in ayse.get(adres).text
    assert "Öğretmenime bildir" not in ali.get(adres).text          # Kendi mesajını bildiremez

    ayse.post(f"/mesaj/{m}/bildir", data={"sebep": "zorbalik"})
    ayse.post(f"/mesaj/{m}/bildir", data={"sebep": "zorbalik"})       # İkinci kez: tek kayıt
    panel = hoca.get("/ogretmen").text
    assert "Bildirilen mesajlar (1)" in panel and "seni kimse sevmiyor" in panel
    assert "Bildiren: ayse" in panel and "Zorbalık / tehdit" in panel
    assert "Bildirilen mesajlar" not in okul["baskahoca"].get("/ogretmen").text

    sikayet_id = int(re.search(r"/ogretmen/sikayet/(\d+)/sil", panel).group(1))
    assert okul["baskahoca"].post(f"/ogretmen/sikayet/{sikayet_id}/sil").status_code == 404
    hoca.post(f"/ogretmen/sikayet/{sikayet_id}/sil")
    assert "Bildirilen mesajlar" not in hoca.get("/ogretmen").text
    assert "seni kimse sevmiyor" not in ayse.get(adres).text


def test_ozel_mesaj_bildirme_ve_kapatma(okul):
    ali, ayse, hoca = okul["ali"], okul["ayse"], okul["hoca"]
    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "özel kaba mesaj"})
    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "bu bildirilmeyecek"})
    m = mesaj_idleri(ayse, f"/mesaj/{kid(ali)}")[0]
    ayse.post(f"/mesaj/{m}/bildir", data={"sebep": "kufur"})
    panel = hoca.get("/ogretmen").text
    assert "özel kaba mesaj" in panel and "özel mesaj" in panel
    assert "bu bildirilmeyecek" not in panel                         # Sohbetin geri kalanı görünmez

    sikayet_id = int(re.search(r"/ogretmen/sikayet/(\d+)/kapat", panel).group(1))
    hoca.post(f"/ogretmen/sikayet/{sikayet_id}/kapat")
    assert "Bildirilen mesajlar" not in hoca.get("/ogretmen").text
    assert "özel kaba mesaj" in ayse.get(f"/mesaj/{kid(ali)}").text   # Kapatınca mesaj kalır


def test_bildirme_yetkisi(okul):
    ali, ayse, veli, hoca = okul["ali"], okul["ayse"], okul["veli"], okul["hoca"]
    ali.post(f"/sinif/{okul['a']}/sohbet", data={"metin": "sınıf mesajı"})
    m = mesaj_idleri(ali, f"/sinif/{okul['a']}/sohbet")[0]
    assert veli.post(f"/mesaj/{m}/bildir", data={"sebep": "spam"}).status_code == 404    # Sınıf dışı
    assert ali.post(f"/mesaj/{m}/bildir", data={"sebep": "spam"}).status_code == 404     # Kendisi
    assert hoca.post(f"/mesaj/{m}/bildir", data={"sebep": "spam"}).status_code == 404    # Öğretmen bildirmez

    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "ali'den ayşe'ye"})
    ozel = mesaj_idleri(ali, f"/mesaj/{kid(ayse)}")[0]
    ali2 = okul["ali"]
    assert ali2.post(f"/mesaj/{ozel}/bildir").status_code == 404               # Gönderen
    hoca.post(f"/sinif/{okul['a']}/sohbet", data={"metin": "hoca mesajı"})
    hm = mesaj_idleri(ayse, f"/sinif/{okul['a']}/sohbet")[-1]
    assert "Öğretmenime bildir" not in ayse.get(f"/sinif/{okul['a']}/sohbet").text.split(f'id="mesaj-{hm}"')[1]


# ---------------------------------------------------------------------------
# Engelleme
# ---------------------------------------------------------------------------

def test_engelleme(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    adres = f"/sinif/{okul['a']}/sohbet"
    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "eski özel mesaj"})
    ali.post(adres, data={"metin": "ali'nin grup mesajı"})

    ayse.post(f"/kullanici/{kid(ali)}/engelle", data={"islem": "engelle", "geri": f"/kullanici/{kid(ali)}"})
    assert "Engeli kaldır" in ayse.get(f"/kullanici/{kid(ali)}").text
    assert "ali&#39;nin grup mesajı" not in ayse.get(adres).text                # Grup mesajı gizli
    assert "ali&#39;nin grup mesajı" in okul["hoca"].get(adres).text           # Başkaları görür
    ali.post(adres, data={"metin": "yeni grup mesajı"})
    assert ayse.get(f"/sohbet/yeni?sinif={okul['a']}&sonra=0").get_json()["mesajlar"] == []

    # Özel mesaj iki yönde de kapanır
    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "engelden sonra"})
    assert "engelden sonra" not in ayse.get(f"/mesaj/{kid(ali)}").text
    assert "Engelleme olduğu için" in ali.get(f"/mesaj/{kid(ayse)}").text
    assert f"/mesaj/{kid(ayse)}\"" not in ali.get("/mesajlar").text.split("Yeni sohbet")[-1]
    assert "ali" in ayse.get("/profil").text and "Engellediklerin" in ayse.get("/profil").text

    # Okunmamış sayısı engellenenin mesajlarını saymaz
    assert 'title="' not in re.search(r"Mesajlar(.*?)</a>", ayse.get("/gecmis").text, re.S).group(1)

    ayse.post(f"/kullanici/{kid(ali)}/engelle", data={"islem": "kaldir"})
    assert "ali&#39;nin grup mesajı" in ayse.get(adres).text
    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "barıştık"})
    assert "barıştık" in ayse.get(f"/mesaj/{kid(ali)}").text


def test_engelleme_sinirlari(okul):
    ali, ayse, hoca, veli = okul["ali"], okul["ayse"], okul["hoca"], okul["veli"]
    assert ali.post(f"/kullanici/{kid(hoca)}/engelle").status_code == 404     # Öğretmen engellenemez
    assert hoca.post(f"/kullanici/{kid(ali)}/engelle").status_code == 404     # Öğretmen engellemez
    assert ali.post(f"/kullanici/{kid(ali)}/engelle").status_code == 404      # Kendini
    assert ali.post(f"/kullanici/{kid(veli)}/engelle").status_code == 404     # Tanımadığı biri
    assert "Engelle" not in ali.get(f"/kullanici/{kid(hoca)}").text


def test_geri_adresi_disariya_yonlendirmez(okul):
    cevap = okul["ayse"].post(f"/kullanici/{kid(okul['ali'])}/engelle",
                              data={"islem": "engelle", "geri": "//kotu-site.com/x"})
    assert cevap.headers["Location"] == "/mesajlar"
    cevap = okul["ayse"].post(f"/kullanici/{kid(okul['ali'])}/engelle",
                              data={"islem": "kaldir", "geri": "https://kotu-site.com"})
    assert cevap.headers["Location"] == "/mesajlar"


def test_hesap_silinince_engel_ve_bildirim_gider(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    ali.post(f"/sinif/{okul['a']}/sohbet", data={"metin": "x"})
    m = mesaj_idleri(ayse, f"/sinif/{okul['a']}/sohbet")[0]
    ayse.post(f"/mesaj/{m}/bildir", data={"sebep": "spam"})
    ayse.post(f"/kullanici/{kid(ali)}/engelle", data={"islem": "engelle"})
    ali.post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    baglanti = veritabani.baglan()
    try:
        assert baglanti.execute("SELECT COUNT(*) FROM sikayetler").fetchone()[0] == 0
        assert baglanti.execute("SELECT COUNT(*) FROM engellemeler").fetchone()[0] == 0
    finally:
        baglanti.close()
    assert "Bildirilen" not in okul["hoca"].get("/ogretmen").text


# ---------------------------------------------------------------------------
# Gizlilik sayfası
# ---------------------------------------------------------------------------

def test_gizlilik_sayfasi(istemci, kayit_ol):
    sayfa = istemci.get("/gizlilik")
    assert sayfa.status_code == 200 and "Gizlilik ve verilerin" in sayfa.text
    assert "/gizlilik" in istemci.get("/kayit").text
    assert "/gizlilik" in kayit_ol("ali").get("/").text                        # Altbilgide
