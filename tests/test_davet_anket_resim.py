"""
Grup davetleri, anketler ve resim paylaşma testleri (10. hafta).
"""

import io
import re

import pytest
from PIL import Image

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


def grup_kur(k, sinif_id, davetliler, ad="Oyun ekibi"):
    cevap = k.post("/grup/yeni", data={"sinif": sinif_id, "ad": ad, "uye": [str(kid(u)) for u in davetliler]})
    return int(re.match(r"/grup/(\d+)/sohbet", cevap.headers["Location"]).group(1))


def uye_adlari(grup_id):
    return {u["kullanici_adi"] for u in veritabani.grup_uyeleri_listesi(grup_id) if u["rol"] == "ogrenci"}


def resim_dosyasi(bicim="PNG", boyut=(50, 40), renk=(200, 30, 30), exif=None):
    """Test için bellekte bir resim üretir (dosyaya yazmadan)."""
    tampon = io.BytesIO()
    resim = Image.new("RGB", boyut, renk)
    if exif is not None:
        resim.save(tampon, bicim, exif=exif)
    else:
        resim.save(tampon, bicim)
    tampon.seek(0)
    return tampon


# ---------------------------------------------------------------------------
# Davetler
# ---------------------------------------------------------------------------

def test_davet_kabul_ve_red(okul):
    ali, ayse, can = okul["ali"], okul["ayse"], okul["can"]
    grup_id = grup_kur(ali, okul["a"], [ayse, can])
    # Davet edilenler henüz üye değil: grubu göremez
    assert uye_adlari(grup_id) == {"ali"}
    assert ayse.get(f"/grup/{grup_id}/sohbet").status_code == 404
    # Davet Mesajlar sayfasında, panelde ve menüdeki sayıda görünür
    sayfa = ayse.get("/mesajlar").text
    assert "Grup davetlerin" in sayfa and "Oyun ekibi" in sayfa
    panel = ayse.get("/mesajlar/panel").get_json()
    assert panel["davetler"][0]["grup"] == "Oyun ekibi" and panel["davetler"][0]["davet_eden"] == "ali"
    assert panel["toplam"] == 1
    # Yönetici bekleyenleri görür
    assert "Davet bekleyenler (2)" in ali.get(f"/grup/{grup_id}").text

    cevap = ayse.post(f"/davet/{grup_id}/kabul")
    assert cevap.headers["Location"] == f"/grup/{grup_id}/sohbet"
    assert "ayse" in uye_adlari(grup_id)
    assert ayse.get(f"/grup/{grup_id}/sohbet").status_code == 200

    assert can.post(f"/davet/{grup_id}/reddet", data={"json": "1"}).get_json() == {"hata": None, "adres": "/mesajlar"}
    assert "can" not in uye_adlari(grup_id)
    assert can.post(f"/davet/{grup_id}/kabul").status_code == 404           # Davet artık yok
    assert can.get("/mesajlar/panel").get_json()["davetler"] == []


def test_davet_edilmeyen_katilamaz_ve_geri_cekme(okul):
    ali, ayse, can = okul["ali"], okul["ayse"], okul["can"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    assert can.post(f"/davet/{grup_id}/kabul").status_code == 404
    assert okul["veli"].post(f"/davet/{grup_id}/kabul").status_code == 404
    # Üye olmayan / yönetici olmayan geri çekemez, yönetici çeker
    assert can.post(f"/grup/{grup_id}/davet-iptal", data={"kisi": kid(ayse)}).status_code == 404
    ali.post(f"/grup/{grup_id}/davet-iptal", data={"kisi": kid(ayse)})
    assert ayse.post(f"/davet/{grup_id}/kabul").status_code == 404
    # Davet edilmiş kişi listede yeniden davet edilebilecekler arasında çıkmaz
    ali.post(f"/grup/{grup_id}/davet", data={"uye": [str(kid(can))]})
    assert all(k["kullanici_adi"] != "can"
               for k in veritabani.grup_eklenebilecekler(kid(ali), okul["a"], grup_id))


def test_engelleyince_bekleyen_davet_silinir(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    ayse.post(f"/kullanici/{kid(ali)}/engelle", data={"islem": "engelle"})
    assert veritabani.davet_getir(grup_id, kid(ayse)) is None


def test_siniftan_ayrilan_daveti_kabul_edemez(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    ayse.post(f"/sinifim/{okul['a']}/ayril")
    assert ayse.post(f"/davet/{grup_id}/kabul").status_code == 404           # Ayrılınca davet de silindi


def test_yonetici_devri(okul):
    ali, ayse, can = okul["ali"], okul["ayse"], okul["can"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    ayse.post(f"/davet/{grup_id}/kabul")
    assert ayse.post(f"/grup/{grup_id}/yonetici", data={"uye": kid(ali)}).status_code == 404  # Yönetici değil
    assert ali.post(f"/grup/{grup_id}/yonetici", data={"uye": kid(can)}).status_code == 404   # Üye değil
    ali.post(f"/grup/{grup_id}/yonetici", data={"uye": kid(ayse)})
    assert veritabani.grup_getir(grup_id)["olusturan_id"] == kid(ayse)
    assert ali.post(f"/grup/{grup_id}/ad", data={"ad": "X"}).status_code == 404               # Artık yönetemez


# ---------------------------------------------------------------------------
# Anketler
# ---------------------------------------------------------------------------

def anket_ac(k, tur, hedef_id, soru="Hangi gün?", secenekler=("Pazartesi", "Salı", ""), **ekstra):
    k.post("/anket/yeni", data={"tur": tur, "id": hedef_id, "soru": soru, "secenek": list(secenekler), **ekstra})
    baglanti = veritabani.baglan()
    try:
        satir = baglanti.execute("SELECT MAX(id) FROM anketler").fetchone()
        return satir[0]
    finally:
        baglanti.close()


def sinif_anketi(k, sinif_id):
    """Sınıf sohbetini açan kişinin gördüğü ilk anket (JSON'dan)."""
    for m in k.get(f"/sohbet/yeni?sinif={sinif_id}&sonra=0").get_json()["mesajlar"]:
        if m["anket"]:
            return m["anket"]
    return None


def test_anket_olusturma_oy_ve_sonuclar(okul):
    ali, ayse, hoca = okul["ali"], okul["ayse"], okul["hoca"]
    anket_id = anket_ac(ali, "sinif", okul["a"])
    anket = sinif_anketi(ayse, okul["a"])
    assert anket["soru"] == "Hangi gün?" and [s["metin"] for s in anket["secenekler"]] == ["Pazartesi", "Salı"]
    assert anket["acik"] and not anket["coklu"] and anket["oy_veren"] == 0
    assert anket["kapatabilir"] is False                                        # Kuran ali, öğretmen değil
    assert sinif_anketi(ali, okul["a"])["kapatabilir"] is True
    assert sinif_anketi(hoca, okul["a"])["kapatabilir"] is True
    # Sohbet sayfasında anket kutusu ve oluşturma formu var
    sayfa = ayse.get(f"/sinif/{okul['a']}/sohbet").text
    assert 'class="anket" data-anket=' in sayfa and "Anket oluştur" in sayfa

    pzt, sali = [s["id"] for s in anket["secenekler"]]
    cevap = ayse.post(f"/anket/{anket_id}/oy", data={"secenek": [str(pzt), str(sali)]}).get_json()["anket"]
    # Tek seçimli: sadece ilki sayılır
    assert [s["oy"] for s in cevap["secenekler"]] == [1, 0] and cevap["oy_verdi"]
    ali.post(f"/anket/{anket_id}/oy", data={"secenek": [str(sali)]})
    hoca.post(f"/anket/{anket_id}/oy", data={"secenek": [str(sali)]})
    son = sinif_anketi(ayse, okul["a"])
    assert [s["oy"] for s in son["secenekler"]] == [1, 2] and [s["yuzde"] for s in son["secenekler"]] == [33, 67]
    assert son["oy_veren"] == 3
    # Oy değiştirme ve geri çekme
    ayse.post(f"/anket/{anket_id}/oy", data={"secenek": [str(sali)]})
    assert [s["oy"] for s in sinif_anketi(ayse, okul["a"])["secenekler"]] == [0, 3]
    ayse.post(f"/anket/{anket_id}/oy", data={})
    assert sinif_anketi(ayse, okul["a"])["oy_verdi"] is False
    # Başka anketin seçeneği sayılmaz
    assert ayse.post(f"/anket/{anket_id}/oy", data={"secenek": ["999"]}).status_code == 200
    assert sinif_anketi(ayse, okul["a"])["oy_veren"] == 2


def test_coklu_secim_ve_bitirme(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    anket_id = anket_ac(ali, "sinif", okul["a"], secenekler=("A", "B", "C"), coklu="1")
    ids = [s["id"] for s in sinif_anketi(ayse, okul["a"])["secenekler"]]
    ayse.post(f"/anket/{anket_id}/oy", data={"secenek": [str(ids[0]), str(ids[2])]})
    assert [s["oy"] for s in sinif_anketi(ayse, okul["a"])["secenekler"]] == [1, 0, 1]
    assert ayse.post(f"/anket/{anket_id}/kapat").status_code == 404             # Kuran değil
    anket = ali.post(f"/anket/{anket_id}/kapat").get_json()["anket"]
    assert anket["acik"] is False
    cevap = ayse.post(f"/anket/{anket_id}/oy", data={"secenek": [str(ids[1])]})
    assert cevap.status_code == 400 and cevap.get_json()["hata"] == "Bu anket bitti."
    assert [s["oy"] for s in sinif_anketi(ayse, okul["a"])["secenekler"]] == [1, 0, 1]   # Sonuçlar kaldı


def test_anket_kurallari(okul):
    ali, hoca, veli = okul["ali"], okul["hoca"], okul["veli"]
    assert anket_ac(ali, "sinif", okul["a"], secenekler=("Tek",)) is None      # En az 2 seçenek
    assert anket_ac(ali, "sinif", okul["a"], soru="") is None
    assert anket_ac(ali, "sinif", okul["a"], bitis="2000-01-01") is None        # Geçmiş tarih
    assert ali.post("/anket/yeni", data={"tur": "kisi", "id": kid(hoca), "soru": "x",
                                         "secenek": ["a", "b"]}).status_code == 404   # Özel sohbette anket yok
    assert ali.post("/anket/yeni", data={"tur": "sinif", "id": okul["b"], "soru": "x",
                                         "secenek": ["a", "b"]}).status_code == 404   # Başka sınıf
    # Kilitli sınıf sohbetinde öğrenci anket açamaz
    hoca.post(f"/ogretmen/sinif/{okul['a']}/sohbet-ayar", data={"kilitli": "1", "ozel_mesaj": "1"})
    assert anket_ac(ali, "sinif", okul["a"]) is None
    # Başka sınıftaki biri oy veremez
    anket_id = anket_ac(hoca, "sinif", okul["a"], bitis="2099-12-31")
    assert sinif_anketi(ali, okul["a"])["bitis"] == "31.12.2099"
    assert veli.post(f"/anket/{anket_id}/oy", data={"secenek": ["1"]}).status_code == 404


def test_grup_anketi_ve_mesaj_silinince_anket_gider(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    ayse.post(f"/davet/{grup_id}/kabul")
    anket_id = anket_ac(ali, "grup", grup_id)
    mesajlar = ayse.get(f"/sohbet/yeni?grup={grup_id}&sonra=0").get_json()["mesajlar"]
    assert mesajlar[0]["anket"]["id"] == anket_id
    # Mesaj listesinde özet
    assert "📊 Anket: Hangi gün?" in ayse.get("/mesajlar").text
    ayse.post(f"/anket/{anket_id}/oy", data={"secenek": [str(mesajlar[0]["anket"]["secenekler"][0]["id"])]})
    ali.post(f"/mesaj/{mesajlar[0]['id']}/sil")
    baglanti = veritabani.baglan()
    try:
        for tablo in ("anketler", "anket_secenekleri", "anket_oylari"):
            assert baglanti.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0] == 0
    finally:
        baglanti.close()
    assert ali.post(f"/anket/{anket_id}/oy", data={}).status_code == 404


def test_anket_metni_kod_olarak_calismaz(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    anket_ac(ali, "sinif", okul["a"], soru="<script>alert(1)</script>", secenekler=("<b>a</b>", "b'c"))
    sayfa = ayse.get(f"/sinif/{okul['a']}/sohbet").text
    assert "<script>alert(1)</script>" not in sayfa
    assert "<b>a</b>" not in sayfa
    # data-anket özniteliği tek tırnaklı; içindeki ' kaçışlanmış olmalı
    veri = re.search(r"data-anket='([^']*)'", sayfa).group(1)
    assert "\\u003cscript" in veri and "\\u0027" in veri


# ---------------------------------------------------------------------------
# Resimler
# ---------------------------------------------------------------------------

def resim_gonder(k, adres, dosya, ad="foto.png", metin=""):
    return k.post(adres, data={"metin": metin, "resim": (dosya, ad)}, content_type="multipart/form-data")


def test_resim_paylasma_kucultme_ve_exif(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    adres = f"/sinif/{okul['a']}/sohbet"
    # Konum bilgisi (EXIF) olan büyük bir fotoğraf
    exif = Image.Exif()
    exif[0x010F] = "Telefon Markasi"          # Make
    buyuk = resim_dosyasi("JPEG", boyut=(3000, 2000), exif=exif.tobytes())
    resim_gonder(ali, adres, buyuk, "tatil.jpg", metin="Proje ekranı")

    mesaj = ayse.get(f"/sohbet/yeni?sinif={okul['a']}&sonra=0").get_json()["mesajlar"][0]
    assert mesaj["metin"] == "Proje ekranı" and mesaj["resim"].startswith("/resim/")
    cevap = ayse.get(mesaj["resim"])
    assert cevap.status_code == 200 and cevap.headers["Content-Type"] == "image/jpeg"
    assert "private" in cevap.headers["Cache-Control"]
    resim = Image.open(io.BytesIO(cevap.data))
    assert max(resim.size) == 1280                                   # Küçültüldü, oran korundu
    assert resim.size == (1280, 853)
    assert len(resim.getexif()) == 0                                 # Konum ve telefon bilgisi silindi
    assert len(cevap.data) <= 300 * 1024
    assert "<img" in ayse.get(adres).text
    assert "📷 Proje ekranı" in ayse.get("/mesajlar").text


def test_saydam_png_ve_sadece_resim(okul):
    ali = okul["ali"]
    tampon = io.BytesIO()
    Image.new("RGBA", (20, 20), (0, 0, 0, 0)).save(tampon, "PNG")
    tampon.seek(0)
    cevap = ali.post("/sohbet/gonder", data={"tur": "sinif", "id": okul["a"], "metin": "", "resim": (tampon, "s.png")},
                     content_type="multipart/form-data")
    assert cevap.get_json() == {"tamam": True}
    mesaj = ali.get(f"/sohbet/yeni?sinif={okul['a']}&sonra=0").get_json()["mesajlar"][0]
    resim = Image.open(io.BytesIO(ali.get(mesaj["resim"]).data))
    assert resim.getpixel((5, 5)) == (255, 255, 255) or sum(resim.getpixel((5, 5))) > 740   # Beyaz zemin
    assert "📷 Resim" in okul["ayse"].get("/mesajlar").text


def test_resim_olmayan_dosya_reddedilir(okul):
    ali = okul["ali"]
    sahte = io.BytesIO(b"MZ\x90\x00 bu bir program dosyasi, resim degil")
    cevap = ali.post("/sohbet/gonder", data={"tur": "sinif", "id": okul["a"], "metin": "", "resim": (sahte, "virus.png")},
                     content_type="multipart/form-data")
    assert cevap.status_code == 400 and "açılamadı" in cevap.get_json()["hata"]
    bmp = resim_dosyasi("BMP")
    cevap = ali.post("/sohbet/gonder", data={"tur": "sinif", "id": okul["a"], "metin": "", "resim": (bmp, "a.bmp")},
                     content_type="multipart/form-data")
    assert cevap.status_code == 400 and "Sadece" in cevap.get_json()["hata"]
    baglanti = veritabani.baglan()
    try:
        assert baglanti.execute("SELECT COUNT(*) FROM resimler").fetchone()[0] == 0
    finally:
        baglanti.close()


def test_cok_buyuk_dosya(okul):
    ali = okul["ali"]
    iri = io.BytesIO(b"0" * (7 * 1024 * 1024))
    cevap = ali.post("/sohbet/gonder", data={"tur": "sinif", "id": okul["a"], "resim": (iri, "iri.png")},
                     content_type="multipart/form-data")
    assert cevap.status_code == 413 and "MB" in cevap.get_json()["hata"]


def test_resim_yetkileri(okul, kayit_ol):
    ali, ayse, can, hoca, veli = okul["ali"], okul["ayse"], okul["can"], okul["hoca"], okul["veli"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    ayse.post(f"/davet/{grup_id}/kabul")
    resim_gonder(ali, f"/grup/{grup_id}/sohbet", resim_dosyasi())
    adres = ayse.get(f"/sohbet/yeni?grup={grup_id}&sonra=0").get_json()["mesajlar"][0]["resim"]
    assert ayse.get(adres).status_code == 200
    assert hoca.get(adres).status_code == 200                       # Sınıfın öğretmeni görür
    assert can.get(adres).status_code == 404                        # Grupta değil
    assert veli.get(adres).status_code == 404
    assert okul["baskahoca"].get(adres).status_code == 404


def test_ogrenciler_arasi_ozel_mesajda_resim_yok(okul):
    ali, ayse, hoca = okul["ali"], okul["ayse"], okul["hoca"]
    cevap = ali.post("/sohbet/gonder", data={"tur": "kisi", "id": kid(ayse), "metin": "",
                                             "resim": (resim_dosyasi(), "a.png")}, content_type="multipart/form-data")
    assert cevap.status_code == 400 and "özel sohbette resim" in cevap.get_json()["hata"]
    assert ali.get(f"/sohbet/yeni?kisi={kid(ayse)}&sonra=0").get_json()["resim_izni"] is False
    assert 'name="resim"' not in ali.get(f"/mesaj/{kid(ayse)}").text
    # Öğretmenle özel sohbette olur
    cevap = ali.post("/sohbet/gonder", data={"tur": "kisi", "id": kid(hoca), "metin": "",
                                             "resim": (resim_dosyasi(), "a.png")}, content_type="multipart/form-data")
    assert cevap.get_json() == {"tamam": True}
    adres = hoca.get(f"/sohbet/yeni?kisi={kid(ali)}&sonra=0").get_json()["mesajlar"][0]["resim"]
    assert hoca.get(adres).status_code == 200
    assert ayse.get(adres).status_code == 404


def test_mesaj_silinince_resim_silinir_ve_gunluk_sinir(okul, monkeypatch):
    import app as uygulama
    ali = okul["ali"]
    adres = f"/sinif/{okul['a']}/sohbet"
    resim_gonder(ali, adres, resim_dosyasi())
    mesaj = ali.get(f"/sohbet/yeni?sinif={okul['a']}&sonra=0").get_json()["mesajlar"][0]
    ali.post(f"/mesaj/{mesaj['id']}/sil")
    assert ali.get(mesaj["resim"]).status_code == 404
    baglanti = veritabani.baglan()
    try:
        assert baglanti.execute("SELECT COUNT(*) FROM resimler").fetchone()[0] == 0
    finally:
        baglanti.close()

    monkeypatch.setattr(uygulama, "GUNLUK_RESIM", 1)
    resim_gonder(ali, adres, resim_dosyasi())
    cevap = ali.post("/sohbet/gonder", data={"tur": "sinif", "id": okul["a"], "resim": (resim_dosyasi(), "b.png")},
                     content_type="multipart/form-data")
    assert cevap.status_code == 400 and "Bugün" in cevap.get_json()["hata"]


def test_hesap_silinince_resim_anket_davet_gider(okul):
    ali, ayse = okul["ali"], okul["ayse"]
    grup_id = grup_kur(ali, okul["a"], [ayse])
    resim_gonder(ali, f"/sinif/{okul['a']}/sohbet", resim_dosyasi())
    anket_id = anket_ac(ali, "sinif", okul["a"])
    secenek = sinif_anketi(ayse, okul["a"])["secenekler"][0]["id"]
    ayse.post(f"/anket/{anket_id}/oy", data={"secenek": [str(secenek)]})
    ali.post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    baglanti = veritabani.baglan()
    try:
        for tablo in ("resimler", "anketler", "anket_secenekleri", "anket_oylari", "grup_davetleri"):
            assert baglanti.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0] == 0, tablo
    finally:
        baglanti.close()
    assert veritabani.grup_getir(grup_id) is None


def test_yedekte_resim_bozulmaz(okul, tmp_path):
    import json

    import yedek_al
    ali = okul["ali"]
    resim_gonder(ali, f"/sinif/{okul['a']}/sohbet", resim_dosyasi())
    yol = yedek_al.yedek_al(str(tmp_path))
    with open(yol, encoding="utf-8") as dosya:
        satir = json.load(dosya)["tablolar"]["resimler"][0]
    veri = yedek_al._jsondan(satir["veri"])
    assert Image.open(io.BytesIO(veri)).format == "JPEG"
