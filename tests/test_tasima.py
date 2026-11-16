"""
SQLite'tan PostgreSQL'e taşıma testleri.
Sadece testler PostgreSQL ile çalıştırılırken (TEST_DATABASE_URL verilince) çalışır.
"""

import sqlite3

import pytest

import tasima
import veritabani

pytestmark = pytest.mark.skipif(not veritabani.POSTGRES, reason="Sadece PostgreSQL ile çalışır")


@pytest.fixture
def eski_db(tmp_path):
    """Bilgisayardaki kodkoc.db'yi taklit eden küçük bir SQLite dosyası (eski sürüm: bazı sütunlar yok)."""
    from werkzeug.security import generate_password_hash
    dosya = tmp_path / "kodkoc.db"
    b = sqlite3.connect(dosya)
    b.executescript("""
        CREATE TABLE kullanicilar (id INTEGER PRIMARY KEY AUTOINCREMENT, kullanici_adi TEXT,
          sifre_hash TEXT, olusturma_zamani TEXT, rol TEXT);
        CREATE TABLE yol_haritalari (id INTEGER PRIMARY KEY AUTOINCREMENT, proje TEXT, bilgi TEXT,
          giris TEXT, dikkat TEXT, ham_cevap TEXT, dosya_yolu TEXT, olusturma_zamani TEXT,
          kullanici_id INTEGER);
        CREATE TABLE adimlar (id INTEGER PRIMARY KEY AUTOINCREMENT, yol_haritasi_id INTEGER,
          sira INTEGER, baslik TEXT, icerik TEXT, tamamlandi INTEGER, tamamlanma_zamani TEXT);
    """)
    b.execute("INSERT INTO kullanicilar VALUES (5, 'ali', ?, '2026-11-01 10:00:00', 'ogrenci')",
              (generate_password_hash("sifre123"),))
    b.execute("INSERT INTO yol_haritalari VALUES (8, 'Not defteri', '', 'g', 'd', 'ham', NULL, "
              "'2026-11-02 10:00:00', 5)")
    b.execute("INSERT INTO adimlar VALUES (12, 8, 1, 'Adım 1: Başla', '- x', 1, '2026-11-03 10:00:00')")
    b.commit()
    b.close()
    return str(dosya)


def test_veriler_ve_idler_aynen_tasinir(eski_db):
    sayilar = tasima.tasi(eski_db)
    assert sayilar == {"kullanicilar": 1, "yol_haritalari": 1, "adimlar": 1}
    ali = veritabani.kullanici_dogrula("ali", "sifre123")        # Eski şifreyle giriş yapılabiliyor
    assert ali["id"] == 5
    harita, adimlar = veritabani.yol_haritasi_getir(8, 5)
    assert harita["proje"] == "Not defteri" and adimlar[0]["tamamlandi"] == 1
    assert adimlar[0]["not_metni"] is None                     # Eski dosyada olmayan sütun boş kalır


def test_tasimadan_sonra_yeni_kayitlar_cakismaz(eski_db):
    tasima.tasi(eski_db)
    assert veritabani.kullanici_ekle("ayse", "sifre123") == 6   # Sayaç en büyük id'den devam ediyor


def test_dolu_veritabanina_tasima_yapilmaz(eski_db):
    veritabani.kullanici_ekle("hoca", "sifre123", "ogretmen")
    with pytest.raises(SystemExit):
        tasima.tasi(eski_db)
