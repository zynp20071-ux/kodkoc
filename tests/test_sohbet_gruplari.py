"""
Sohbet grupları ve mesaj paneli testleri (10. hafta):
  - öğrencinin sınıf arkadaşlarıyla grup kurması, kurallar (engel, özel mesaj ayarı, başka sınıf)
  - yöneticinin kişi ekleyip çıkarması, ad değiştirmesi, grubu silmesi; üyenin ayrılması
  - yöneticilik devri (yönetici ayrılınca / sınıftan çıkınca / hesabını silince)
  - öğretmenin görmesi ama mesaj listesinin şişmemesi
  - her sayfadaki mesaj panelinin JSON uçları
"""

import re

import pytest

import veritabani


def sinif_ac(hoca, ad):
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": ad}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    return sinif_id, kod


@pytest.fixture
def okul(kayit_ol):
    """A sınıfı: hoca + ali + ayse + can. B sınıfı: baskahoca + veli."""
    hoca = kayit_ol("hoca", "ogretmen")
    a_id, a_kod = sinif_ac(hoca, "A sınıfı")
    ogr = {}
    for ad in ("ali", "ayse", "can"):
        ogr[ad] = kayit_ol(ad)
        ogr[ad].post("/sinifim/katil", data={"kod": a_kod})
    baskahoca = kayit_ol("baskahoca", "ogretmen")
    b_id, b_kod = sinif_ac(baskahoca, "B sınıfı")
    veli = kayit_ol("veli")
    veli.post("/sinifim/katil", data={"kod": b_kod})
    return {"hoca": hoca, "baskahoca": baskahoca, "veli": veli, "a": a_id, "b": b_id, **ogr}


def kid(k):
    return k.kullanici["id"]


def grup_kur(k, sinif_id, uyeler, ad="Oyun ekibi"):
    """Grubu kurar, grubun id'sini döndürür (kurulamadıysa None)."""
    cevap = k.post("/grup/yeni", data={"sinif": sinif_id, "ad": ad, "uye": [str(kid(u)) for u in uyeler]})
    m = re.match(r"/grup/(\d+)/sohbet", cevap.headers.get("Location", ""))
    return int(m.group(1)) if m else None


def grup_sayisi():
    baglanti = veritabani.baglan()
    try:
        return baglanti.execute("SELECT COUNT(*) FROM gruplar").fetchone()[0]
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# Grup kurma
# ---------------------------------------------------------------------------

def test_ogrenci_grup_kurar_ve_uyeler_yazisir(okul):
    ali, ayse, can = okul["ali"], okul["ayse"], okul["can"]
    # Tek sınıfı olduğu için form doğrudan o sınıfın kişilerini gösterir
    form = ali.get("/grup/yeni").text
    assert "ayse" in form and "can" in form and "veli" not in form
    assert "Yeni grup kur" in ali.get("/mesajlar").text

    grup_id = grup_kur(ali, okul["a"], [ayse])
    assert grup_id
    ali.post(f"/grup/{grup_id}/sohbet", data={"metin": "Selam ekip"})
    assert "Selam ekip" in ayse.get(f"/grup/{grup_id}/sohbet").text
    assert "Oyun ekibi" in ayse.get("/mesajlar").text and "Sohbet grubu" in ayse.get("/mesajlar").text
    # Grupta olmayan sınıf arkadaşı ve başka sınıftan biri göremez
    assert can.get(f"/grup/{grup_id}/sohbet").status_code == 404
    assert okul["veli"].get(f"/grup/{grup_id}").status_code == 404
    assert okul["baskahoca"].get(f"/grup/{grup_id}/sohbet").status_code == 404
    # Yönetici etiketi ve öğretmenin görebileceği notu grup sayfasında
    sayfa = ayse.get(f"/grup/{grup_id}").text
    assert "Yönetici" in sayfa and "öğretmeni bu grubu görebilir" in sayfa
    # Sohbet grupları "Sınıfım"daki proje grupları arasında görünmez
    assert "Oyun ekibi" not in ali.get("/sinifim").text


def test_grup_kurma_kurallari(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    assert grup_kur(ali, okul["a"], []) is None                        # Kimse seçilmedi
    assert grup_kur(ali, okul["a"], [ayse], ad="") is None               # Ad boş
    assert grup_kur(ali, okul["a"], [ayse], ad="x" * 41) is None         # Ad çok uzun
    # Başka sınıftaki biri sessizce atılır; kimse kalmayınca grup kurulmaz
    assert grup_kur(ali, okul["a"], [okul["veli"]]) is None
    # Üyesi olmadığı sınıfta grup kuramaz
    assert ali.get(f"/grup/yeni?sinif={okul['b']}").status_code == 404
    assert grup_kur(ali, okul["b"], [okul["veli"]]) is None
    assert grup_sayisi() == 0


def test_engelli_kisi_eklenemez(okul):
    ali, ayse, can = okul["ali"], okul["ayse"], okul["can"]
    ayse.post(f"/kullanici/{kid(ali)}/engelle", data={"islem": "engelle"})
    assert "ayse" not in ali.get("/grup/yeni").text
    grup_id = grup_kur(ali, okul["a"], [ayse, can])
    uyeler = {u["kullanici_adi"] for u in veritabani.grup_uyeleri_listesi(grup_id)}
    assert "ayse" not in uyeler and {"ali", "can"} <= uyeler


def test_ozel_mesaj_kapaliysa_ogrenci_grup_kuramaz(okul):
    ali, hoca = okul["ali"], okul["hoca"]
    hoca.post(f"/ogretmen/sinif/{okul['a']}/sohbet-ayar", data={"kilitli": "0"})   # özel mesaj kapalı
    assert "Grup kurabileceğin bir sınıf yok" in ali.get("/grup/yeni").text
    assert "Yeni grup kur" not in ali.get("/mesajlar").text
    assert grup_kur(ali, okul["a"], [okul["ayse"]]) is None
    # Öğretmen yine de kurabilir
    assert grup_kur(hoca, okul["a"], [okul["ayse"], okul["can"]], ad="Hoca grubu")


def test_kurulabilecek_grup_siniri(okul, monkeypatch):
    import app as uygulama
    monkeypatch.setattr(uygulama, "EN_FAZLA_KURULAN_GRUP", 2)
    ali, ayse = okul["ali"], okul["ayse"]
    assert grup_kur(ali, okul["a"], [ayse], ad="1")
    assert grup_kur(ali, okul["a"], [ayse], ad="2")
    assert grup_kur(ali, okul["a"], [ayse], ad="3") is None


# ---------------------------------------------------------------------------
# Yönetme: ekle, çıkar, ad, ayrıl, sil
# ---------------------------------------------------------------------------

def test_yonetici_kisi_ekler_cikarir_ad_degistirir(okul):
    ali, ayse, can = okul["ali"], okul["ayse"], okul["can"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    # Üye (yönetici olmayan) yönetemez
    assert ayse.post(f"/grup/{grup_id}/uye-ekle", data={"uye": [str(kid(can))]}).status_code == 404
    assert ayse.post(f"/grup/{grup_id}/ad", data={"ad": "Benim"}).status_code == 404
    assert ayse.post(f"/grup/{grup_id}/cikar", data={"uye": kid(ali)}).status_code == 404
    assert ayse.post(f"/ogretmen/grup/{grup_id}/sil").status_code == 404

    ali.post(f"/grup/{grup_id}/uye-ekle", data={"uye": [str(kid(can)), str(kid(okul["veli"]))]})
    adlar = {u["kullanici_adi"] for u in veritabani.grup_uyeleri_listesi(grup_id)}
    assert "can" in adlar and "veli" not in adlar
    ali.post(f"/grup/{grup_id}/ad", data={"ad": "Yeni ad"})
    assert veritabani.grup_getir(grup_id)["ad"] == "Yeni ad"
    ali.post(f"/grup/{grup_id}/cikar", data={"uye": kid(can)})
    assert can.get(f"/grup/{grup_id}/sohbet").status_code == 404
    assert ali.post(f"/grup/{grup_id}/cikar", data={"uye": kid(ali)}).status_code == 404   # Kendini çıkaramaz


def test_ayrilma_ve_yoneticilik_devri(okul):
    ali, ayse, can = okul["ali"], okul["ayse"], okul["can"]
    grup_id = grup_kur(ali, okul["a"], [ayse, can])
    ali.post(f"/grup/{grup_id}/ayril")
    assert ali.get(f"/grup/{grup_id}").status_code == 404
    yeni_yonetici = veritabani.grup_getir(grup_id)["olusturan_id"]
    assert yeni_yonetici in (kid(ayse), kid(can))
    # Son üye de ayrılınca grup silinir
    ayse.post(f"/grup/{grup_id}/ayril")
    can.post(f"/grup/{grup_id}/ayril")
    assert veritabani.grup_getir(grup_id) is None


def test_siniftan_ayrilinca_ve_hesap_silinince_devir(okul):
    ali, ayse, can = okul["ali"], okul["ayse"], okul["can"]
    g1 = grup_kur(ali, okul["a"], [ayse], ad="G1")
    g2 = grup_kur(ayse, okul["a"], [can], ad="G2")
    ali.post(f"/sinifim/{okul['a']}/ayril")
    assert veritabani.grup_getir(g1)["olusturan_id"] == kid(ayse)
    ayse.post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    # ayse'nin iki grubu da can'a ya da (kimse kalmadıysa) silinmeye gider
    assert veritabani.grup_getir(g1) is None                          # g1'de başka kimse kalmadı
    assert veritabani.grup_getir(g2)["olusturan_id"] == kid(can)


def test_yonetici_grubu_siler(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    ali.post(f"/grup/{grup_id}/sohbet", data={"metin": "x"})
    cevap = ali.post(f"/ogretmen/grup/{grup_id}/sil")
    assert cevap.headers["Location"] == "/mesajlar"
    assert veritabani.grup_getir(grup_id) is None


def test_proje_grubu_sohbet_grubu_islemleriyle_degismez(okul):
    """Öğretmenin kurduğu proje grubundan öğrenci ayrılamaz, kişi ekleyemez."""
    hoca, ali = okul["hoca"], okul["ali"]
    cevap = hoca.post(f"/ogretmen/sinif/{okul['a']}/grup", data={"ad": "Proje", "uye": [str(kid(ali))]})
    grup_id = int(cevap.headers["Location"].rsplit("/", 1)[1])
    assert ali.post(f"/grup/{grup_id}/ayril").status_code == 404
    assert hoca.post(f"/grup/{grup_id}/uye-ekle", data={"uye": [str(kid(okul["can"]))]}).status_code == 404
    assert ali.post(f"/ogretmen/grup/{grup_id}/sil").status_code == 404


# ---------------------------------------------------------------------------
# Öğretmen
# ---------------------------------------------------------------------------

def test_ogretmen_sohbet_gruplarini_gorur_ama_listesi_sismez(okul):
    hoca, ali, ayse = okul["hoca"], okul["ali"], okul["ayse"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    ali.post(f"/grup/{grup_id}/sohbet", data={"metin": "gizli değil"})
    # Öğretmenin mesaj listesinde ve okunmamış sayısında yok
    assert "Oyun ekibi" not in hoca.get("/mesajlar").text
    assert hoca.get("/bildirim-sayilari").get_json()["mesaj"] == 0
    # Ama sınıf sayfasında listelenir ve açıp okuyabilir, mesaj silebilir
    assert "Öğrencilerin kurduğu sohbet grupları" in hoca.get(f"/ogretmen/sinif/{okul['a']}").text
    assert "gizli değil" in hoca.get(f"/grup/{grup_id}/sohbet").text
    mesaj_id = int(re.search(r'id="mesaj-(\d+)"', hoca.get(f"/grup/{grup_id}/sohbet").text).group(1))
    hoca.post(f"/mesaj/{mesaj_id}/sil")
    assert "Bu mesaj silindi" in ayse.get(f"/grup/{grup_id}/sohbet").text
    # Yönetebilir: grubu silebilir
    hoca.post(f"/ogretmen/grup/{grup_id}/sil")
    assert veritabani.grup_getir(grup_id) is None


# ---------------------------------------------------------------------------
# Mesaj paneli (JSON)
# ---------------------------------------------------------------------------

def test_panel_her_sayfada_ama_sohbet_sayfalarinda_degil(okul):
    ali = okul["ali"]
    assert 'id="mesaj-paneli"' in ali.get("/gecmis").text
    assert 'id="mesaj-paneli"' not in ali.get("/mesajlar").text
    assert 'id="mesaj-paneli"' not in ali.get(f"/sinif/{okul['a']}/sohbet").text


def test_panel_listesi_ve_gonderme(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    cevap = ali.post("/sohbet/gonder", data={"tur": "grup", "id": grup_id, "metin": "panelden"})
    assert cevap.get_json() == {"tamam": True}
    ali.post("/sohbet/gonder", data={"tur": "kisi", "id": kid(ayse), "metin": "özel <b>selam</b>"})

    veri = ayse.get("/mesajlar/panel").get_json()
    turler = {(s["tur"], s["ad"]): s for s in veri["sohbetler"]}
    assert turler[("grup", "Oyun ekibi")]["okunmamis"] == 1
    assert turler[("kisi", "ali")]["son"] == "özel <b>selam</b>"       # Ham metin; betik textContent ile yazar
    assert ("sinif", "A sınıfı") in turler
    assert veri["toplam"] == 2
    # En yeni mesajın sohbeti en üstte
    assert veri["sohbetler"][0]["tur"] == "kisi"
    # Yeni sohbet başlatılabilecekler: konuşulmamış kişiler (can, hoca)
    assert {k["ad"] for k in veri["yeni_kisiler"]} == {"can", "hoca"}

    # Sohbeti açmak (sonra=0) yazılabilir mi bilgisini de verir ve okundu yapar
    acilis = ayse.get(f"/sohbet/yeni?grup={grup_id}&sonra=0").get_json()
    assert acilis["yazabilir"] is True and acilis["mesajlar"][0]["metin"] == "panelden"
    assert ayse.get("/mesajlar/panel").get_json()["toplam"] == 1


def test_panel_gonderme_kurallari(okul):
    ali, hoca, veli = okul["ali"], okul["hoca"], okul["veli"]
    # Tanımadığı biri ve göremediği sınıf: 404
    assert ali.post("/sohbet/gonder", data={"tur": "kisi", "id": kid(veli), "metin": "x"}).status_code == 404
    assert ali.post("/sohbet/gonder", data={"tur": "sinif", "id": okul["b"], "metin": "x"}).status_code == 404
    assert ali.post("/sohbet/gonder", data={"tur": "yanlis", "id": 1, "metin": "x"}).status_code == 404
    # Kilitli sınıf sohbeti: öğrenci yazamaz, sebebi JSON'da döner
    hoca.post(f"/ogretmen/sinif/{okul['a']}/sohbet-ayar", data={"kilitli": "1", "ozel_mesaj": "1"})
    cevap = ali.post("/sohbet/gonder", data={"tur": "sinif", "id": okul["a"], "metin": "x"})
    assert cevap.status_code == 403 and "duyuru kanalı" in cevap.get_json()["hata"]
    assert ali.get(f"/sohbet/yeni?sinif={okul['a']}&sonra=0").get_json()["yazabilir"] is False
    # Çok uzun mesaj
    cevap = ali.post("/sohbet/gonder", data={"tur": "kisi", "id": kid(hoca), "metin": "a" * 1001})
    assert cevap.status_code == 400
    # CSRF jetonu olmadan gönderilemez
    cevap = ali.post("/sohbet/gonder", data={"tur": "kisi", "id": kid(hoca), "metin": "x", "csrf": "yanlis"})
    assert cevap.status_code == 400
    assert veritabani.ozel_mesajlar(kid(ali), kid(hoca)) == []


def test_panel_kufur_suzer(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    ali.post("/sohbet/gonder", data={"tur": "kisi", "id": kid(ayse), "metin": "sen bir aptal"})
    assert veritabani.ozel_mesajlar(kid(ali), kid(ayse))[0]["metin"] == "sen bir a****"
