"""Ödev testleri: ödev verme, teslim, güncelleme, puanlama, geç teslim, yetkiler, menü rozeti."""

import re
from datetime import date, timedelta

import pytest

import veritabani


def gun(fark):
    return (date.today() + timedelta(days=fark)).isoformat()


@pytest.fixture
def sinif(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali, ayse = kayit_ol("ali"), kayit_ol("ayse")
    ali.post("/sinifim/katil", data={"kod": kod})
    ayse.post("/sinifim/katil", data={"kod": kod})
    return {"hoca": hoca, "ali": ali, "ayse": ayse, "id": sinif_id}


def odev_ver(s, baslik="Hesap makinesi", tarih=None):
    s["hoca"].post(f"/ogretmen/sinif/{s['id']}/odev",
                   data={"baslik": baslik, "aciklama": "Dört işlem yapsın.", "son_tarih": tarih or gun(3)})
    return veritabani.sinifin_odevleri(s["id"])[0]["id"]


def menu_odev(k):
    m = re.search(r'Ödevler\s*<span class="menu-rozeti"[^>]*>(\d+)</span>', k.get("/gecmis").text)
    return int(m.group(1)) if m else 0


def test_odev_akisi(sinif):
    ali, hoca = sinif["ali"], sinif["hoca"]
    odev_id = odev_ver(sinif)
    assert menu_odev(ali) == 1
    liste = ali.get("/odevler").text
    assert "Hesap makinesi" in liste and "3 gün kaldı" in liste

    ali.post(f"/odev/{odev_id}", data={"baglanti": "https://github.com/ali/hesap", "metin": "print(2+2)"})
    assert menu_odev(ali) == 0
    assert "Teslim edildi" in ali.get("/odevler").text
    ali.post(f"/odev/{odev_id}", data={"baglanti": "", "metin": "print(3+3)"})        # Güncelle
    assert "print(3+3)" in ali.get(f"/odev/{odev_id}").text

    sayfa = hoca.get(f"/ogretmen/odev/{odev_id}").text
    assert "1 / 2 öğrenci teslim etti" in sayfa and "print(3+3)" in sayfa and "Teslim etmedi" in sayfa
    assert "1 / 2 teslim · <strong>1 puan bekliyor</strong>" in hoca.get(f"/ogretmen/sinif/{sinif['id']}").text

    teslim_id = int(re.search(r"/ogretmen/teslim/(\d+)/puan", sayfa).group(1))
    hoca.post(f"/ogretmen/teslim/{teslim_id}/puan", data={"puan": "85", "yorum": "Güzel olmuş"})
    assert menu_odev(ali) == 1                                                      # Yeni puan
    sayfa = ali.get(f"/odev/{odev_id}").text
    assert "85" in sayfa and "Güzel olmuş" in sayfa and "Yeni" in sayfa
    assert menu_odev(ali) == 0                                                      # Görüldü

    ali.post(f"/odev/{odev_id}", data={"metin": "değiştirdim"})                    # Puanlandı: değişmez
    assert "değiştirdim" not in ali.get(f"/odev/{odev_id}").text


def test_gec_teslim_ve_gecmis_odev(sinif):
    odev_id = odev_ver(sinif, tarih=gun(-1))
    assert menu_odev(sinif["ali"]) == 0                                            # Süresi geçen sayılmaz
    assert "Süre geçti" in sinif["ali"].get("/odevler").text
    cevap = sinif["ali"].post(f"/odev/{odev_id}", data={"metin": "geç kaldım"}, follow_redirects=True)
    assert "geç teslim" in cevap.text
    assert "geç teslim" in sinif["hoca"].get(f"/ogretmen/odev/{odev_id}").text


def test_teslim_dogrulama(sinif):
    ali = sinif["ali"]
    odev_id = odev_ver(sinif)
    assert "bir açıklama/kod ya da bağlantı" in ali.post(f"/odev/{odev_id}", data={}, follow_redirects=True).text
    cevap = ali.post(f"/odev/{odev_id}", data={"baglanti": "javascript:alert(1)"}, follow_redirects=True)
    assert "https:// ile başlayan" in cevap.text
    assert veritabani.teslim_getir(odev_id, ali.kullanici["id"]) is None


def test_odev_verme_dogrulama(sinif):
    hoca = sinif["hoca"]
    hoca.post(f"/ogretmen/sinif/{sinif['id']}/odev", data={"baslik": "", "son_tarih": gun(2)})
    hoca.post(f"/ogretmen/sinif/{sinif['id']}/odev", data={"baslik": "x", "son_tarih": "yarın"})
    assert veritabani.sinifin_odevleri(sinif["id"]) == []


def test_yetkiler(sinif, kayit_ol):
    odev_id = odev_ver(sinif)
    baskahoca = kayit_ol("baskahoca", "ogretmen")
    disaridan = kayit_ol("veli")
    assert disaridan.get(f"/odev/{odev_id}").status_code == 404
    assert disaridan.post(f"/odev/{odev_id}", data={"metin": "x"}).status_code == 404
    assert baskahoca.get(f"/ogretmen/odev/{odev_id}").status_code == 404
    assert baskahoca.post(f"/ogretmen/sinif/{sinif['id']}/odev", data={"baslik": "x", "son_tarih": gun(1)}).status_code == 404
    assert sinif["hoca"].get(f"/odev/{odev_id}").status_code == 404                # Öğretmen teslim etmez
    sinif["ali"].post(f"/odev/{odev_id}", data={"metin": "x"})
    teslim = veritabani.teslim_getir(odev_id, sinif["ali"].kullanici["id"])
    assert baskahoca.post(f"/ogretmen/teslim/{teslim['id']}/puan", data={"puan": "100"}).status_code == 404
    assert sinif["ali"].post(f"/ogretmen/teslim/{teslim['id']}/puan", data={"puan": "100"}).status_code == 302
    sinif["hoca"].post(f"/ogretmen/teslim/{teslim['id']}/puan", data={"puan": "150"})   # Geçersiz puan
    assert veritabani.teslim_getir(odev_id, sinif["ali"].kullanici["id"])["puan"] is None


def test_odev_ve_sinif_silme(sinif):
    odev_id = odev_ver(sinif)
    sinif["ali"].post(f"/odev/{odev_id}", data={"metin": "x"})
    sinif["hoca"].post(f"/ogretmen/odev/{odev_id}/sil")
    assert veritabani.odev_getir(odev_id) is None
    odev_ver(sinif, "İkinci")
    sinif["hoca"].post(f"/ogretmen/sinif/{sinif['id']}/sil")
    baglanti = veritabani.baglan()
    try:
        assert baglanti.execute("SELECT COUNT(*) FROM odevler").fetchone()[0] == 0
        assert baglanti.execute("SELECT COUNT(*) FROM teslimler").fetchone()[0] == 0
    finally:
        baglanti.close()


def test_hesap_silinince_teslim_gider(sinif):
    odev_id = odev_ver(sinif)
    sinif["ali"].post(f"/odev/{odev_id}", data={"metin": "x"})
    sinif["ali"].post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    assert "0 / 1 öğrenci teslim etti" in sinif["hoca"].get(f"/ogretmen/odev/{odev_id}").text


def test_bos_liste(kayit_ol):
    assert "Henüz ödevin yok" in kayit_ol("ali").get("/odevler").text
