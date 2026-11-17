"""
"Öğretmenime sor" ve sınıf projesinin adım dağılımı testleri.
"""

import re

import pytest

import app as uygulama
import veritabani
from conftest import adim_bolumu, yol_haritasi_cikar


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


def sor(s, metin="Dosyayı hangi modda açmalıyım?", adim_index=0, ogrenci=None):
    return (ogrenci or s["ali"]).post(f"/adim/{s['adimlar'][adim_index]}/ogretmene-sor", data={"soru": metin})


def soru_idleri(s):
    sorular = veritabani.yol_haritasinin_ogretmen_sorulari(s["harita_id"])
    return [soru["id"] for liste in sorular.values() for soru in liste]


def cevapla(s, soru_id, metin="Okumak için 'r', yazmak için 'w' kullan.", ogretmen=None):
    return (ogretmen or s["hoca"]).post(f"/ogretmen/soru/{soru_id}/cevap", data={"cevap": metin})


def ali_sayfasi(s):
    return s["ali"].get(f"/yol-haritasi/{s['harita_id']}").text


# ---------------------------------------------------------------------------
# Soru sorma ve cevaplama
# ---------------------------------------------------------------------------

def test_ogrenci_sorar_ogretmen_panelde_gorur_ve_cevaplar(sinif):
    adim = sinif["adimlar"][0]
    assert f"/adim/{adim}/ogretmene-sor" in adim_bolumu(ali_sayfasi(sinif), adim)      # Form var
    sor(sinif)
    assert "Cevap bekleniyor" in ali_sayfasi(sinif)

    panel = sinif["hoca"].get("/ogretmen").text
    assert "Cevap bekleyen sorular (1)" in panel and "Dosyayı hangi modda" in panel
    assert f"#adim-{sinif['adimlar'][0]}" in panel

    soru_id = soru_idleri(sinif)[0]
    assert cevapla(sinif, soru_id).status_code == 302
    assert "Cevap bekleyen sorular" not in sinif["hoca"].get("/ogretmen").text

    # Öğrencide bildirim: menü rozeti 1, açınca bir kez "Yeni", sonra kaybolur
    assert veritabani.okunmamis_bildirim_sayisi(sinif["ali_id"]) == 1
    sayfa = ali_sayfasi(sinif)
    assert "Okumak için" in sayfa and "Cevap · hoca" in sayfa and "Yeni</span>" in sayfa
    assert veritabani.okunmamis_bildirim_sayisi(sinif["ali_id"]) == 0
    assert "Yeni</span>" not in ali_sayfasi(sinif)


def test_ogretmen_cevabi_duzeltebilir(sinif):
    sor(sinif)
    soru_id = soru_idleri(sinif)[0]
    cevapla(sinif, soru_id, "İlk cevap")
    cevapla(sinif, soru_id, "Düzeltilmiş cevap")
    sayfa = ali_sayfasi(sinif)
    assert "Düzeltilmiş cevap" in sayfa and "İlk cevap" not in sayfa


def test_sinifi_olmayan_ogrenci_soramaz(kayit_ol):
    ayse = kayit_ol("ayse")
    harita_id, adimlar = yol_haritasi_cikar(ayse)
    assert "/ogretmene-sor" not in ayse.get(f"/yol-haritasi/{harita_id}").text       # Form yok
    cevap = ayse.post(f"/adim/{adimlar[0]}/ogretmene-sor", data={"soru": "Merhaba"}, follow_redirects=True)
    assert "önce bir sınıfa katıl" in cevap.text
    assert veritabani.acik_soru_sayisi(ayse.kullanici["id"]) == 0


def test_en_fazla_acik_soru_siniri(sinif):
    for i in range(uygulama.EN_FAZLA_ACIK_SORU):
        sor(sinif, f"Soru {i}")
    cevap = sinif["ali"].post(f"/adim/{sinif['adimlar'][0]}/ogretmene-sor", data={"soru": "Bir tane daha"},
                              follow_redirects=True)
    assert "Cevap bekleyen 5 sorun var" in cevap.text
    assert veritabani.acik_soru_sayisi(sinif["ali_id"]) == uygulama.EN_FAZLA_ACIK_SORU
    # Biri cevaplanınca yenisi sorulabilir
    cevapla(sinif, soru_idleri(sinif)[0])
    sor(sinif, "Bir tane daha")
    assert veritabani.acik_soru_sayisi(sinif["ali_id"]) == uygulama.EN_FAZLA_ACIK_SORU


@pytest.mark.parametrize("metin", ["", "   ", "x" * 501])
def test_bos_ya_da_uzun_soru_kaydedilmez(sinif, metin):
    sor(sinif, metin)
    assert soru_idleri(sinif) == []


def test_bos_cevap_kaydedilmez(sinif):
    sor(sinif)
    cevapla(sinif, soru_idleri(sinif)[0], "  ")
    assert veritabani.acik_soru_sayisi(sinif["ali_id"]) == 1


def test_baskasinin_adimina_soru_sorulamaz(sinif, kayit_ol):
    ayse = kayit_ol("ayse")
    ayse.post("/sinifim/katil", data={"kod": sinif["kod"]})
    assert sor(sinif, ogrenci=ayse).status_code == 404


def test_baska_ogretmen_goremez_ve_cevaplayamaz(sinif, kayit_ol):
    sor(sinif)
    baska = kayit_ol("baskahoca", "ogretmen")
    assert "Cevap bekleyen sorular" not in baska.get("/ogretmen").text
    assert cevapla(sinif, soru_idleri(sinif)[0], ogretmen=baska).status_code == 404
    assert veritabani.acik_soru_sayisi(sinif["ali_id"]) == 1


def test_siniftan_ayrilinca_ogretmen_cevaplayamaz(sinif):
    sor(sinif)
    sinif["ali"].post(f"/sinifim/{sinif['id']}/ayril")
    assert "Cevap bekleyen sorular" not in sinif["hoca"].get("/ogretmen").text
    assert cevapla(sinif, soru_idleri(sinif)[0]).status_code == 404


def test_iki_sinifta_olan_ogrencinin_sorusu_bir_kez_gelir(sinif):
    cevap = sinif["hoca"].post("/ogretmen/sinif", data={"ad": "Programlama B"})
    ikinci = int(cevap.headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", sinif["hoca"].get(f"/ogretmen/sinif/{ikinci}").text).group(1)
    sinif["ali"].post("/sinifim/katil", data={"kod": kod})
    sor(sinif)
    assert len(veritabani.ogretmenin_bekleyen_sorulari(sinif["hoca"].kullanici["id"])) == 1


# ---------------------------------------------------------------------------
# Silme: soru tablosu adımlara bağlı, silme sırası doğru olmalı
# ---------------------------------------------------------------------------

def test_sorulu_adim_ve_yol_haritasi_silinebilir(sinif):
    sor(sinif, adim_index=0)
    sor(sinif, adim_index=1)
    sinif["ali"].post(f"/adim/{sinif['adimlar'][0]}/sil")
    assert len(soru_idleri(sinif)) == 1
    assert sinif["ali"].post(f"/yol-haritasi/{sinif['harita_id']}/sil").status_code == 302
    assert veritabani.acik_soru_sayisi(sinif["ali_id"]) == 0


def test_sorusu_olan_ogrenci_hesabini_silebilir(sinif):
    sor(sinif)
    assert sinif["ali"].post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"}).status_code == 302
    assert veritabani.kullanici_dogrula("ali", "sifre123") is None


def test_ogretmen_hesabini_silince_cevap_ogrencide_kalir(sinif):
    sor(sinif)
    cevapla(sinif, soru_idleri(sinif)[0], "Kalıcı cevap")
    sinif["hoca"].post("/profil/sil", data={"sifre": "sifre123", "onay": "SİL"})
    sayfa = ali_sayfasi(sinif)
    assert "Kalıcı cevap" in sayfa and "Cevap · hoca" not in sayfa


# ---------------------------------------------------------------------------
# Sınıf projesinin adım dağılımı
# ---------------------------------------------------------------------------

def projeye_basla(s, ogrenci):
    cevap = ogrenci.post("/yol-haritasi", data={"proje": "Kütüphane programı", "sinif_proje": s["id"]})
    harita_id = int(cevap.headers["Location"].rsplit("/", 1)[1])
    return [int(x) for x in re.findall(r'id="adim-(\d+)"', ogrenci.get(f"/yol-haritasi/{harita_id}").text)]


def test_proje_adim_dagilimi(sinif, kayit_ol):
    sinif["hoca"].post(f"/ogretmen/sinif/{sinif['id']}/proje", data={"proje": "Kütüphane programı"})
    ayse = kayit_ol("ayse")
    ayse.post("/sinifim/katil", data={"kod": sinif["kod"]})
    ali_adimlari = projeye_basla(sinif, sinif["ali"])
    ayse_adimlari = projeye_basla(sinif, ayse)
    # Ali 1. adımı bitirdi, 2. adımda 2 ipucu aldı (takıldı). Ayşe hiç bitirmedi (1. adımda).
    sinif["ali"].post(f"/adim/{ali_adimlari[0]}", data={"tamamlandi": "1"})
    sinif["ali"].post(f"/adim/{ali_adimlari[1]}/ipucu", data={})
    sinif["ali"].post(f"/adim/{ali_adimlari[1]}/ipucu", data={})

    dagilim = {a["sira"]: a for a in uygulama.proje_adim_dagilimi(sinif["id"])}
    assert len(dagilim) == 4
    assert (dagilim[1]["biten"], dagilim[1]["burada"], dagilim[1]["oran"]) == (1, 1, 50)
    assert (dagilim[2]["biten"], dagilim[2]["burada"], dagilim[2]["takilan"]) == (0, 1, 1)
    assert dagilim[3]["burada"] == 0 and len(ayse_adimlari) == 4

    sayfa = sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}").text
    assert "Sınıf projesi: adım adım" in sayfa and "1 öğrenci · %50" in sayfa


def test_proje_yoksa_dagilim_gosterilmez(sinif):
    assert "Sınıf projesi: adım adım" not in sinif["hoca"].get(f"/ogretmen/sinif/{sinif['id']}").text
