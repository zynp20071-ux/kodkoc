"""demo_veri.py testleri: sunum için örnek veri doğru kuruluyor ve temizce siliniyor mu?"""

import pytest

import demo_veri
import veritabani

SIFRE = "demo-sifre-123"


def giris(istemci, ad):
    istemci.post("/giris", data={"kullanici_adi": ad, "sifre": SIFRE})
    return istemci


def test_demo_veri_kurulur(istemci):
    ozet = demo_veri.olustur(SIFRE)
    hoca = giris(istemci, "demo_ogretmen")
    panel = hoca.get("/ogretmen").text
    assert "Demo Sınıfı" in panel and "append yazınca" in panel             # Bekleyen soru

    rapor = hoca.get(f"/ogretmen/sinif/{ozet['sinif_id']}/rapor").text
    assert "demo_elif" in rapor and "4 / 5 · %80" in rapor
    assert "Başlamadı" in rapor                                               # demo_deniz
    assert "Yardıma ihtiyacı olabilir" in rapor and "demo_can" in rapor     # 3 ipucu
    assert "Hedefi geçen adımı olanlar" in rapor


def test_demo_ogrenci_gorunumu(istemci):
    demo_veri.olustur(SIFRE)
    elif_ = giris(istemci, "demo_elif")
    assert "★ 5/5 · Yeni" in elif_.get("/gecmis").text                      # Öğretmen değerlendirmesi
    assert "3 not" in elif_.get("/notlarim").text
    assert "Serin 4 gün" in elif_.get("/").text                              # 4 gün önceden düne kadar çalıştı


def test_iki_kez_kurulmaz_ve_kisa_sifre(istemci):
    with pytest.raises(SystemExit):
        demo_veri.olustur("1234")
    assert veritabani.kullanici_sayisi() == 0
    demo_veri.olustur(SIFRE)
    with pytest.raises(SystemExit):
        demo_veri.olustur(SIFRE)
    assert veritabani.kullanici_sayisi() == 4


def test_demo_veri_silinir(istemci, kayit_ol):
    kayit_ol("gercek_ogrenci")                       # Demo olmayan hesaba dokunulmamalı
    demo_veri.olustur(SIFRE)
    assert demo_veri.sil("yanlis-sifre") == 0
    assert demo_veri.sil(SIFRE) == 4
    assert veritabani.kullanici_sayisi() == 1
    demo_veri.olustur(SIFRE)                         # Silindikten sonra yeniden kurulabilir
