"""Kullanıcı girişi testleri: kayıt kuralları, giriş/çıkış ve herkesin sadece kendi verisini görmesi."""

import pytest

import veritabani
from conftest import yol_haritasi_cikar


@pytest.mark.parametrize("yol", ["/", "/gecmis", "/sinifim", "/yol-haritasi/1"])
def test_girissiz_sayfalar_kapali(istemci, yol):
    """parametrize: aynı testi 4 farklı adresle 4 kez çalıştırır."""
    cevap = istemci.get(yol)
    assert cevap.status_code == 302 and "/giris" in cevap.headers["Location"]


def test_hic_kullanici_yoksa_kayit_sayfasina_gider(istemci):
    assert "/kayit" in istemci.get("/giris").headers["Location"]


@pytest.mark.parametrize("ad, sifre, tekrar, beklenen", [
    ("ab", "sifre123", "sifre123", "3-20 karakter"),          # çok kısa ad
    ("ali veli", "sifre123", "sifre123", "3-20 karakter"),    # boşluklu ad
    ("zeynep", "123", "123", "en az 6"),                      # kısa şifre
    ("zeynep", "sifre123", "baska123", "aynısı değil"),       # şifreler farklı
])
def test_kayit_kurallari(istemci, ad, sifre, tekrar, beklenen):
    cevap = istemci.post("/kayit", data={"kullanici_adi": ad, "sifre": sifre, "sifre_tekrar": tekrar})
    assert beklenen in cevap.text
    assert veritabani.kullanici_sayisi() == 0


def test_sifre_acik_metin_olarak_saklanmiyor(kayit_ol):
    kayit_ol("zeynep", sifre="gizli123")
    b = veritabani.baglan()          # SQLite da olsa PostgreSQL de olsa çalışır
    hash_ = b.execute("SELECT sifre_hash FROM kullanicilar").fetchone()[0]
    assert "gizli123" not in hash_
    assert hash_.startswith(("scrypt:", "pbkdf2:"))


def test_ayni_ad_buyuk_kucuk_harf_farkiyla_alinamaz(kayit_ol, istemci):
    kayit_ol("zeynep")
    cevap = istemci.post("/kayit", data={"kullanici_adi": "ZEYNEP", "sifre": "sifre123",
                                         "sifre_tekrar": "sifre123"})
    assert "alınmış" in cevap.text


def test_giris_ve_cikis(kayit_ol, istemci):
    kayit_ol("zeynep", sifre="gizli123")
    assert "yanlış" in istemci.post("/giris", data={"kullanici_adi": "zeynep", "sifre": "x"}).text
    # Olmayan kullanıcıda da AYNI mesaj: hangi adların var olduğu belli olmasın
    assert "Kullanıcı adı ya da şifre yanlış" in istemci.post(
        "/giris", data={"kullanici_adi": "yok", "sifre": "gizli123"}).text
    assert istemci.post("/giris", data={"kullanici_adi": "Zeynep", "sifre": "gizli123"}).status_code == 302
    assert istemci.get("/gecmis").status_code == 200

    assert istemci.get("/cikis").status_code == 405          # Çıkış sadece POST ile
    istemci.post("/cikis")
    assert "/giris" in istemci.get("/gecmis").headers["Location"]


def test_ilk_kullanici_eski_kayitlari_devralir(istemci):
    veritabani.yol_haritasi_ekle("Girişten önceki proje", "", "### Adım 1: A\n- x")   # sahipsiz
    cevap = istemci.post("/kayit", data={"kullanici_adi": "zeynep", "sifre": "sifre123",
                                         "sifre_tekrar": "sifre123"}, follow_redirects=True)
    assert "1 yol haritası hesabına aktarıldı" in cevap.text
    assert "Girişten önceki proje" in istemci.get("/gecmis").text


def test_herkes_sadece_kendi_verisini_gorur(kayit_ol):
    zeynep, ayse = kayit_ol("zeynep"), kayit_ol("ayse")
    harita_id, adimlar = yol_haritasi_cikar(zeynep, "Zeynep'in projesi")

    assert "Zeynep" not in ayse.get("/gecmis").text
    assert ayse.get(f"/yol-haritasi/{harita_id}").status_code == 404
    assert ayse.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"}).status_code == 404
    assert ayse.post(f"/adim/{adimlar[0]}/ipucu", data={}).status_code == 404
    assert ayse.post(f"/adim/{adimlar[0]}/not", data={"not_metni": "x"}).status_code == 404
    assert ayse.post(f"/yol-haritasi/{harita_id}/sil").status_code == 404
    assert ayse.post(f"/yol-haritasi/{harita_id}/github", data={"depo": "a/b"}).status_code == 404
    # Zeynep'in verisi değişmedi
    assert "0 / 4 adım" in zeynep.get(f"/yol-haritasi/{harita_id}").text


def test_bulunamadi_sayfasi_tasarimli(kayit_ol):
    cevap = kayit_ol("zeynep").get("/yol-haritasi/999")
    assert cevap.status_code == 404 and "Sayfa bulunamadı" in cevap.text
