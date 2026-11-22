"""Grup projesi testleri: grup kurma, görev panosu, grup sohbeti, yetkiler, silme."""

import re

import pytest

import veritabani


@pytest.fixture
def sinif(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ogr = {}
    for ad in ("ali", "ayse", "can"):
        ogr[ad] = kayit_ol(ad)
        ogr[ad].post("/sinifim/katil", data={"kod": kod})
    return {"hoca": hoca, "id": sinif_id, **ogr}


def kid(k):
    return k.kullanici["id"]


def grup_kur(s, ad="Kırmızı takım", uyeler=("ali", "ayse")):
    cevap = s["hoca"].post(f"/ogretmen/sinif/{s['id']}/grup",
                           data={"ad": ad, "proje": "Kantin sipariş programı",
                                 "uye": [str(kid(s[u])) for u in uyeler]})
    return int(cevap.headers["Location"].rsplit("/", 1)[1])


def gorev_idleri(k, grup_id):
    return [int(x) for x in re.findall(r'id="gorev-(\d+)"', k.get(f"/grup/{grup_id}").text)]


def test_grup_kurma_ve_gorunurluk(sinif, kayit_ol):
    grup_id = grup_kur(sinif)
    sayfa = sinif["ali"].get(f"/grup/{grup_id}").text
    assert "Kırmızı takım" in sayfa and "Kantin sipariş programı" in sayfa and "ayse" in sayfa
    assert "Kırmızı takım" in sinif["ali"].get("/sinifim").text
    assert "Kırmızı takım" in sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}").text
    assert sinif["hoca"].get(f"/grup/{grup_id}").status_code == 200
    assert sinif["can"].get(f"/grup/{grup_id}").status_code == 404                # Grupta değil
    assert sinif["can"].get(f"/grup/{grup_id}/sohbet").status_code == 404
    assert kayit_ol("baskahoca", "ogretmen").get(f"/grup/{grup_id}").status_code == 404


def test_grup_kurma_dogrulama(sinif, kayit_ol):
    disaridan = kayit_ol("veli")
    hoca = sinif["hoca"]
    hoca.post(f"/ogretmen/sinif/{sinif['id']}/grup", data={"ad": "Boş", "uye": []})
    assert veritabani.sinifin_gruplari(sinif["id"]) == []
    # Sınıfta olmayan öğrenci gruba eklenmez
    cevap = hoca.post(f"/ogretmen/sinif/{sinif['id']}/grup",
                      data={"ad": "B", "uye": [str(kid(sinif["ali"])), str(kid(disaridan))]})
    grup_id = int(cevap.headers["Location"].rsplit("/", 1)[1])
    assert disaridan.get(f"/grup/{grup_id}").status_code == 404
    assert veritabani.sinifin_gruplari(sinif["id"])[0]["uyeler"] == ["ali"]
    assert kayit_ol("baskahoca", "ogretmen").post(f"/ogretmen/sinif/{sinif['id']}/grup",
                                                  data={"ad": "x", "uye": ["1"]}).status_code == 404


def test_gorev_panosu(sinif):
    ali, ayse = sinif["ali"], sinif["ayse"]
    grup_id = grup_kur(sinif)
    ali.post(f"/grup/{grup_id}/gorev", data={"metin": "Menüyü yap", "atanan": str(kid(ali))})
    ali.post(f"/grup/{grup_id}/gorev", data={"metin": "Dosyaya kaydet", "atanan": str(kid(sinif["can"]))})
    gorevler = veritabani.grup_gorevleri(grup_id)
    assert gorevler[0]["atanan_id"] == kid(ali) and gorevler[1]["atanan_id"] is None    # Can grupta değil

    g1, g2 = gorev_idleri(ayse, grup_id)
    ayse.post(f"/gorev/{g1}", data={"durum": "bitti", "atanan": str(kid(ali))})
    ayse.post(f"/gorev/{g2}", data={"durum": "yapiliyor", "atanan": str(kid(ayse))})
    sayfa = ali.get(f"/grup/{grup_id}").text
    assert "1 / 2 görev bitti · %50" in sayfa and "Bitti (1)" in sayfa and "Yapılıyor (1)" in sayfa
    assert "1 / 2 görev bitti" in sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}").text

    assert sinif["can"].post(f"/gorev/{g1}", data={"durum": "yapilacak"}).status_code == 404
    assert sinif["can"].post(f"/grup/{grup_id}/gorev", data={"metin": "x"}).status_code == 404
    ali.post(f"/gorev/{g2}", data={"islem": "sil"})
    assert len(veritabani.grup_gorevleri(grup_id)) == 1


def test_grup_sohbeti(sinif):
    ali, ayse, hoca = sinif["ali"], sinif["ayse"], sinif["hoca"]
    grup_id = grup_kur(sinif)
    ali.post(f"/grup/{grup_id}/sohbet", data={"metin": "Yarın toplanalım mı?"})
    assert "Grup sohbetleri" in ayse.get("/mesajlar").text
    assert "Yarın toplanalım mı?" in ayse.get("/mesajlar").text
    sayfa = ayse.get(f"/grup/{grup_id}/sohbet").text
    assert "Yarın toplanalım mı?" in sayfa and "Grup sohbeti" in sayfa and "Sohbet ayarları" not in sayfa
    veri = hoca.get(f"/sohbet/yeni?grup={grup_id}&sonra=0").get_json()
    assert veri["mesajlar"][0]["metin"] == "Yarın toplanalım mı?"
    assert sinif["can"].get(f"/sohbet/yeni?grup={grup_id}&sonra=0").status_code == 404
    assert "Yarın toplanalım" not in sinif["can"].get("/mesajlar").text
    # Sınıf sohbetinde görünmez
    assert "Yarın toplanalım" not in sinif["can"].get(f"/sinif/{sinif['id']}/sohbet").text


def test_grup_mesaji_bildir_ve_ogretmen_siler(sinif):
    ali, ayse, hoca = sinif["ali"], sinif["ayse"], sinif["hoca"]
    grup_id = grup_kur(sinif)
    ali.post(f"/grup/{grup_id}/sohbet", data={"metin": "kaba söz"})
    m = int(re.search(r'id="mesaj-(\d+)"', ayse.get(f"/grup/{grup_id}/sohbet").text).group(1))
    assert sinif["can"].post(f"/mesaj/{m}/bildir", data={"sebep": "kufur"}).status_code == 404
    ayse.post(f"/mesaj/{m}/bildir", data={"sebep": "kufur"})
    panel = hoca.get("/ogretmen").text
    assert "kaba söz" in panel and "Kırmızı takım grubu" in panel
    hoca.post(f"/mesaj/{m}/sil")
    assert "kaba söz" not in ayse.get(f"/grup/{grup_id}/sohbet").text


def test_siniftan_ayrilan_gruptan_cikar(sinif):
    grup_id = grup_kur(sinif)
    sinif["ali"].post(f"/sinifim/{sinif['id']}/ayril")
    assert sinif["ali"].get(f"/grup/{grup_id}").status_code == 404
    assert veritabani.sinifin_gruplari(sinif["id"])[0]["uyeler"] == ["ayse"]


def test_grup_ve_sinif_silme(sinif):
    grup_id = grup_kur(sinif)
    sinif["ali"].post(f"/grup/{grup_id}/gorev", data={"metin": "x"})
    sinif["ali"].post(f"/grup/{grup_id}/sohbet", data={"metin": "y"})
    assert sinif["ali"].post(f"/ogretmen/grup/{grup_id}/sil").status_code == 302   # Öğrenci silemez
    assert veritabani.grup_getir(grup_id) is not None
    sinif["hoca"].post(f"/ogretmen/grup/{grup_id}/sil")
    assert veritabani.grup_getir(grup_id) is None
    grup_kur(sinif, "İkinci")
    sinif["hoca"].post(f"/ogretmen/sinif/{sinif['id']}/sil")
    baglanti = veritabani.baglan()
    try:
        for tablo in ("gruplar", "grup_uyeleri", "gorevler", "mesajlar"):
            assert baglanti.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0] == 0, tablo
    finally:
        baglanti.close()


def test_hesap_silinince(sinif):
    grup_id = grup_kur(sinif)
    sinif["ali"].post(f"/grup/{grup_id}/gorev", data={"metin": "benim görevim", "atanan": str(kid(sinif["ali"]))})
    sinif["ali"].post(f"/grup/{grup_id}/sohbet", data={"metin": "ali yazdı"})
    sinif["ali"].post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    gorev = veritabani.grup_gorevleri(grup_id)[0]
    assert gorev["atanan_id"] is None and gorev["metin"] == "benim görevim"        # Görev grupta kalır
    assert "ali yazdı" not in sinif["ayse"].get(f"/grup/{grup_id}/sohbet").text
