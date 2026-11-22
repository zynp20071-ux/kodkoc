"""
Profil ve mesajlaşma testleri: sınıf sohbeti, özel mesaj, okunmamış sayısı, yetkiler, silme.
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
    """A sınıfı: hoca + ali + ayse. B sınıfı: baskahoca + veli (A'dakilerle ortak sınıfı yok)."""
    hoca = kayit_ol("hoca", "ogretmen")
    a_id, a_kod = sinif_ac(hoca, "A sınıfı")
    ali, ayse = kayit_ol("ali"), kayit_ol("ayse")
    ali.post("/sinifim/katil", data={"kod": a_kod})
    ayse.post("/sinifim/katil", data={"kod": a_kod})
    baskahoca = kayit_ol("baskahoca", "ogretmen")
    b_id, b_kod = sinif_ac(baskahoca, "B sınıfı")
    veli = kayit_ol("veli")
    veli.post("/sinifim/katil", data={"kod": b_kod})
    return {"hoca": hoca, "ali": ali, "ayse": ayse, "veli": veli, "baskahoca": baskahoca,
            "a": a_id, "b": b_id}


def kid(k):
    return k.kullanici["id"]


def menu_sayisi(k):
    m = re.search(r'Mesajlar\s*<span class="menu-rozeti"[^>]*>(\d+)</span>', k.get("/gecmis").text)
    return int(m.group(1)) if m else 0


# ---------------------------------------------------------------------------
# Sınıf sohbeti
# ---------------------------------------------------------------------------

def test_sinif_sohbeti_ve_okunmamis(okul):
    ali, ayse, hoca = okul["ali"], okul["ayse"], okul["hoca"]
    adres = f"/sinif/{okul['a']}/sohbet"
    assert "Henüz mesaj yok" in ali.get(adres).text
    ali.post(adres, data={"metin": "Merhaba arkadaşlar!"})
    ali.post(adres, data={"metin": "Döngü konusunu anlayan var mı?"})

    assert menu_sayisi(ayse) == 2 and menu_sayisi(hoca) == 2
    assert menu_sayisi(ali) == 0                                # Kendi mesajı okunmamış sayılmaz
    liste = ayse.get("/mesajlar").text
    assert "A sınıfı" in liste and "Döngü konusunu anlayan var mı?" in liste

    sayfa = ayse.get(adres).text
    assert "Merhaba arkadaşlar!" in sayfa and "3 kişi" in sayfa
    assert menu_sayisi(ayse) == 0                               # Açınca okundu
    assert menu_sayisi(hoca) == 2


def test_sinif_disindaki_giremez(okul):
    adres = f"/sinif/{okul['a']}/sohbet"
    assert okul["veli"].get(adres).status_code == 404
    assert okul["veli"].post(adres, data={"metin": "selam"}).status_code == 404
    assert okul["baskahoca"].get(adres).status_code == 404
    assert okul["veli"].get(f"/sohbet/yeni?sinif={okul['a']}&sonra=0").status_code == 404
    assert "A sınıfı" not in okul["veli"].get("/mesajlar").text


def test_yoklama_json_ve_kacis(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    ali.post(f"/sinif/{okul['a']}/sohbet", data={"metin": "<script>alert(1)</script>"})
    veri = ayse.get(f"/sohbet/yeni?sinif={okul['a']}&sonra=0").get_json()
    assert len(veri["mesajlar"]) == 1
    m = veri["mesajlar"][0]
    assert m["metin"] == "<script>alert(1)</script>" and m["gonderen"] == "ali" and not m["benim"]
    assert ayse.get(f"/sohbet/yeni?sinif={okul['a']}&sonra={m['id']}").get_json() == {"mesajlar": []}
    assert menu_sayisi(ayse) == 0                               # Yoklama da okundu sayar
    # HTML sayfada kaçışlı görünür, kod olarak çalışmaz
    sayfa = ayse.get(f"/sinif/{okul['a']}/sohbet").text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in sayfa and "<script>alert(1)" not in sayfa


def test_kilitli_sohbet(okul):
    hoca, ali = okul["hoca"], okul["ali"]
    adres = f"/sinif/{okul['a']}/sohbet"
    assert "Sohbet ayarları" in hoca.get(adres).text and "Sohbet ayarları" not in ali.get(adres).text
    hoca.post(f"/ogretmen/sinif/{okul['a']}/sohbet-ayar", data={"kilitli": "1", "ozel_mesaj": "1"})
    ali.post(adres, data={"metin": "yazabilir miyim?"})
    hoca.post(adres, data={"metin": "Yarın sınav var."})
    sayfa = ali.get(adres).text
    assert "yazabilir miyim?" not in sayfa and "Yarın sınav var." in sayfa
    assert "sadece o yazabiliyor" in sayfa and 'id="metin"' not in sayfa
    # Başka öğretmen bu sınıfın ayarını değiştiremez, öğrenci hiç değiştiremez
    assert okul["baskahoca"].post(f"/ogretmen/sinif/{okul['a']}/sohbet-ayar", data={}).status_code == 404
    assert ali.post(f"/ogretmen/sinif/{okul['a']}/sohbet-ayar", data={}).status_code == 302


# ---------------------------------------------------------------------------
# Özel mesaj
# ---------------------------------------------------------------------------

def test_ozel_mesaj(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "Ödevi bitirdin mi?"})
    assert menu_sayisi(ayse) == 1
    liste = ayse.get("/mesajlar").text
    assert "Ödevi bitirdin mi?" in liste and f"/mesaj/{kid(ali)}" in liste
    assert "Sen: Ödevi bitirdin mi?" in ali.get("/mesajlar").text
    assert "Ödevi bitirdin mi?" in ayse.get(f"/mesaj/{kid(ali)}").text
    assert menu_sayisi(ayse) == 0
    # Üçüncü kişi (hoca dahil) bu sohbeti göremez: hoca için bu "hoca ile ali" sohbeti
    assert "Ödevi bitirdin mi?" not in okul["hoca"].get(f"/mesaj/{kid(ali)}").text


def test_ogretmen_ogrenci_ozel_mesaj(okul):
    okul["hoca"].post(f"/mesaj/{kid(okul['ali'])}", data={"metin": "Ali, yarın konuşalım."})
    okul["ali"].post(f"/mesaj/{kid(okul['hoca'])}", data={"metin": "Tamam hocam."})
    sayfa = okul["ali"].get(f"/mesaj/{kid(okul['hoca'])}").text
    assert "Ali, yarın konuşalım." in sayfa and "Tamam hocam." in sayfa and "Öğretmen" in sayfa


def test_ortak_sinif_yoksa_mesaj_yok(okul):
    ali, veli = okul["ali"], okul["veli"]
    assert ali.get(f"/mesaj/{kid(veli)}").status_code == 404
    assert ali.post(f"/mesaj/{kid(veli)}", data={"metin": "selam"}).status_code == 404
    assert okul["baskahoca"].get(f"/mesaj/{kid(ali)}").status_code == 404
    assert ali.get(f"/mesaj/{kid(ali)}").status_code == 404                  # Kendine
    assert ali.get("/mesaj/99999").status_code == 404
    yeni = ali.get("/mesajlar").text
    assert "ayse" in yeni and "hoca" in yeni and "veli" not in yeni


def test_ogretmen_ozel_mesaji_kapatir(okul):
    ali, ayse, hoca = okul["ali"], okul["ayse"], okul["hoca"]
    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "ilk mesaj"})
    hoca.post(f"/ogretmen/sinif/{okul['a']}/sohbet-ayar", data={"ozel_mesaj": ""})
    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "ikinci mesaj"})
    sayfa = ali.get(f"/mesaj/{kid(ayse)}").text
    assert "ilk mesaj" in sayfa and "ikinci mesaj" not in sayfa              # Eskiler okunur
    assert "özel mesajı kapattı" in sayfa
    ali.post(f"/mesaj/{kid(hoca)}", data={"metin": "hocam bir sorum var"})   # Öğretmene hâlâ yazılır
    assert "hocam bir sorum var" in hoca.get(f"/mesaj/{kid(ali)}").text


def test_siniftan_ayrilinca(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "görüşürüz"})
    ali.post(f"/sinifim/{okul['a']}/ayril")
    assert ali.get(f"/sinif/{okul['a']}/sohbet").status_code == 404
    sayfa = ali.get(f"/mesaj/{kid(ayse)}").text
    assert "görüşürüz" in sayfa and 'id="metin"' not in sayfa


# ---------------------------------------------------------------------------
# Silme, sınırlar
# ---------------------------------------------------------------------------

def mesaj_idleri(k, adres):
    return [int(x) for x in re.findall(r'id="mesaj-(\d+)"', k.get(adres).text)]


def test_mesaj_silme_yetkileri(okul):
    ali, ayse, hoca = okul["ali"], okul["ayse"], okul["hoca"]
    adres = f"/sinif/{okul['a']}/sohbet"
    ali.post(adres, data={"metin": "ali yazdı"})
    ayse.post(adres, data={"metin": "ayşe yazdı"})
    ali_m, ayse_m = mesaj_idleri(ali, adres)

    assert ayse.post(f"/mesaj/{ali_m}/sil").status_code == 404               # Başkasınınkini silemez
    ali.post(f"/mesaj/{ali_m}/sil")
    hoca.post(f"/mesaj/{ayse_m}/sil")                                         # Öğretmen sınıfta silebilir
    sayfa = ayse.get(adres).text
    assert "ali yazdı" not in sayfa and "ayşe yazdı" not in sayfa and sayfa.count('<p class="mesaj-metni">Bu mesaj silindi.</p>') == 2

    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "özel"})
    ozel_m = mesaj_idleri(ali, f"/mesaj/{kid(ayse)}")[0]
    assert hoca.post(f"/mesaj/{ozel_m}/sil").status_code == 404              # Özel mesaja karışamaz
    assert menu_sayisi(ayse) == 1
    ali.post(f"/mesaj/{ozel_m}/sil")
    assert menu_sayisi(ayse) == 0                                             # Silinen okunmamış sayılmaz


def test_bos_uzun_ve_hizli_mesaj(okul, monkeypatch):
    ali = okul["ali"]
    adres = f"/sinif/{okul['a']}/sohbet"
    ali.post(adres, data={"metin": "   "})
    ali.post(adres, data={"metin": "x" * (uygulama.EN_UZUN_MESAJ + 1)})
    assert mesaj_idleri(ali, adres) == []
    monkeypatch.setattr(uygulama, "EN_FAZLA_MESAJ_DAKIKA", 3)
    for i in range(4):
        ali.post(adres, data={"metin": f"mesaj {i}"})
    assert len(mesaj_idleri(ali, adres)) == 3
    assert "Çok hızlı mesaj gönderiyorsun" in ali.post(adres, data={"metin": "bir daha"},
                                                       follow_redirects=True).text


def test_hesap_ve_sinif_silinince_mesajlar_gider(okul):
    ali, ayse, hoca = okul["ali"], okul["ayse"], okul["hoca"]
    ali.post(f"/sinif/{okul['a']}/sohbet", data={"metin": "ali'nin sınıf mesajı"})
    ali.post(f"/mesaj/{kid(ayse)}", data={"metin": "ali'nin özel mesajı"})
    ali.post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    assert veritabani.kullanici_getir(kid(ali)) is None
    assert "ali&#39;nin sınıf mesajı" not in ayse.get(f"/sinif/{okul['a']}/sohbet").text
    assert "ali&#39;nin" not in ayse.get("/mesajlar").text and menu_sayisi(ayse) == 0

    hoca.post(f"/sinif/{okul['a']}/sohbet", data={"metin": "hoca mesajı"})
    hoca.post(f"/ogretmen/sinif/{okul['a']}/sil")
    assert ayse.get(f"/sinif/{okul['a']}/sohbet").status_code == 404
    baglanti = veritabani.baglan()
    try:
        assert baglanti.execute("SELECT COUNT(*) FROM mesajlar").fetchone()[0] == 0
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# Profil
# ---------------------------------------------------------------------------

def test_profil_gorunurlugu(okul):
    ali, ayse, hoca, veli = okul["ali"], okul["ayse"], okul["hoca"], okul["veli"]
    ali.post("/profil/hakkimda", data={"hakkimda": "Python öğreniyorum, oyun yapmayı seviyorum."})
    sayfa = ayse.get(f"/kullanici/{kid(ali)}").text
    assert "Python öğreniyorum" in sayfa and "Öğrenci" in sayfa and "A sınıfı" in sayfa
    assert f"/mesaj/{kid(ali)}" in sayfa and "İlerlemesini gör" not in sayfa
    assert "İlerlemesini gör" in hoca.get(f"/kullanici/{kid(ali)}").text
    assert veli.get(f"/kullanici/{kid(ali)}").status_code == 404             # Sınıf dışı göremez
    assert okul["baskahoca"].get(f"/kullanici/{kid(ali)}").status_code == 404
    assert ali.get("/kullanici/99999").status_code == 404
    assert "Profilimi düzenle" in ali.get(f"/kullanici/{kid(ali)}").text       # Kendi profili
    assert "Öğretmen" in ali.get(f"/kullanici/{kid(hoca)}").text


def test_hakkimda_sinir(okul):
    ali = okul["ali"]
    ali.post("/profil/hakkimda", data={"hakkimda": "x" * (uygulama.EN_UZUN_HAKKIMDA + 1)})
    assert "x" * 50 not in ali.get("/profil").text
    ali.post("/profil/hakkimda", data={"hakkimda": "kısa yazı"})
    assert "kısa yazı" in ali.get("/profil").text
    ali.post("/profil/hakkimda", data={"hakkimda": ""})                       # Boş: silinir
    assert "kısa yazı" not in ali.get(f"/kullanici/{kid(ali)}").text


def test_rozetler_profilde(okul):
    from conftest import yol_haritasi_cikar
    ali = okul["ali"]
    _, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    assert "İlk Adım" in okul["ayse"].get(f"/kullanici/{kid(ali)}").text


def test_giris_gerekli(istemci):
    for adres in ("/mesajlar", "/mesaj/1", "/sinif/1/sohbet", "/sohbet/yeni?sinif=1", "/kullanici/1"):
        assert istemci.get(adres).status_code == 302
