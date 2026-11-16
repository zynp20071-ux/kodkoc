"""Adımları düzenleme testleri: ekleme, düzenleme, silme ve numaraların yeniden sıralanması."""

import re

import pytest

import veritabani
from conftest import adim_bolumu, yol_haritasi_cikar


def basliklar(sayfa):
    """Sayfadaki adım başlıklarını sırayla döndürür (etiketler hariç)."""
    return [re.sub(r"<span.*", "", h, flags=re.S).strip()
            for h in re.findall(r"<h3>(.*?)</h3>", sayfa, re.S)]


def test_adim_ekleme(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, _ = yol_haritasi_cikar(ali)
    cevap = ali.post(f"/yol-haritasi/{harita_id}/adim-ekle",
                     data={"baslik": "Adım 99: Renkli menü", "icerik": "Menüyü renklendir."})
    yeni_id = int(cevap.headers["Location"].rsplit("#adim-", 1)[1])
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert basliklar(sayfa)[-1] == "Adım 5: Renkli menü"          # Numarayı sistem verdi
    assert "Senin eklediğin" in adim_bolumu(sayfa, yeni_id)
    assert "0 / 5 adım" in sayfa                                  # İlerleme de güncellendi


def test_adim_duzenleme(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[1]}/duzenle", data={"baslik": "Görev Ekleme ve Doğrulama",
                                                  "icerik": "- Boş görevi kabul etme"})
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert basliklar(sayfa)[1] == "Adım 2: Görev Ekleme ve Doğrulama"
    assert "Boş görevi kabul etme" in adim_bolumu(sayfa, adimlar[1])


@pytest.mark.parametrize("baslik, icerik, mesaj", [
    ("", "x", "1-120 karakter"),
    ("x" * 121, "", "1-120 karakter"),
    ("Adım 3:", "", "1-120 karakter"),          # Sadece numara yazılmışsa başlık boş kalır
    ("Başlık", "x" * 2001, "en fazla 2000"),
])
def test_gecersiz_adim_reddedilir(kayit_ol, baslik, icerik, mesaj):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    assert mesaj in ali.post(f"/adim/{adimlar[0]}/duzenle", data={"baslik": baslik, "icerik": icerik},
                             follow_redirects=True).text
    assert mesaj in ali.post(f"/yol-haritasi/{harita_id}/adim-ekle", data={"baslik": baslik, "icerik": icerik},
                             follow_redirects=True).text
    assert len(veritabani.yol_haritasi_getir(harita_id, ali.kullanici["id"])[1]) == 4


def test_silince_numaralar_kayar(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[1]}/ipucu", data={})                # Silinecek adımın ipucu
    cevap = ali.post(f"/adim/{adimlar[1]}/sil", follow_redirects=True)
    assert "numaralar yeniden sıralandı" in cevap.text
    assert basliklar(cevap.text) == ["Adım 1: Menüyü Planlama", "Adım 2: Görevleri Listeleme",
                                     "Adım 3: Dosyaya Kaydetme"]
    assert veritabani.yol_haritasinin_ipuclari(harita_id) == {}   # İpucu da silindi
    assert [a["sira"] for a in veritabani.yol_haritasi_getir(harita_id, ali.kullanici["id"])[1]] == [1, 2, 3]


def test_son_adim_silinemez(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    for adim_id in adimlar[1:]:
        ali.post(f"/adim/{adim_id}/sil")
    sayfa = ali.post(f"/adim/{adimlar[0]}/sil", follow_redirects=True).text
    assert "en az bir adım kalmalı" in sayfa
    assert "Bu adımı sil" not in sayfa                             # Tek adımda düğme de yok


def test_silinen_adimin_commitleri_baglantisiz_kalir(kayit_ol):
    """Commit GitHub'da hâlâ var; silinmemeli, sadece adıma bağlı olmaktan çıkmalı."""
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    veritabani.commitleri_kaydet(harita_id, [{"sha": "a1", "mesaj": "Adım 2 bitti", "yazar": "ali",
                                              "tarih": "2026-11-10 10:00:00", "url": "https://github.com/a/b/commit/a1"}],
                                 lambda m: 2)
    ali.post(f"/adim/{adimlar[1]}/sil")
    commitler = veritabani.yol_haritasinin_commitleri(harita_id)
    assert len(commitler) == 1 and commitler[0]["adim_id"] is None


def test_baskasi_ve_ogretmen_duzenleyemez(kayit_ol):
    ali, ayse = kayit_ol("ali"), kayit_ol("ayse")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    assert ayse.post(f"/adim/{adimlar[0]}/duzenle", data={"baslik": "x"}).status_code == 404
    assert ayse.post(f"/adim/{adimlar[0]}/sil").status_code == 404
    assert ayse.post(f"/yol-haritasi/{harita_id}/adim-ekle", data={"baslik": "x"}).status_code == 404

    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali.post("/sinifim/katil", data={"kod": kod})
    ali.post(f"/yol-haritasi/{harita_id}/adim-ekle", data={"baslik": "Kendi adımım"})
    sayfa = hoca.get(f"/ogretmen/ogrenci/{ali.kullanici['id']}/yol-haritasi/{harita_id}").text
    assert "Öğrencinin eklediği" in sayfa
    assert "Adımı düzenle" not in sayfa and "Kendi adımını ekle" not in sayfa
    assert hoca.post(f"/adim/{adimlar[0]}/sil").status_code == 404


def test_devam_karti_guncel_numarayi_gosterir(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/sil")
    assert "Sıradaki: <strong>Adım 1: Görev Ekleme</strong>" in ali.get("/").text
