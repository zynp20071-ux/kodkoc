"""Veritabanı testleri: cevabı adımlara bölme ve eski veritabanını yükseltme (göç)."""

import sqlite3

import pytest

import veritabani
from conftest import ORNEK_CEVAP


# ---------------------------------------------------------------------------
# SQLite sorgularını PostgreSQL'e çeviren fonksiyon
# ---------------------------------------------------------------------------

def test_postgres_sql_yer_tutuculari_cevirir():
    assert veritabani.postgres_sql("SELECT * FROM a WHERE id = ? AND b = ?") == \
        "SELECT * FROM a WHERE id = %s AND b = %s"
    assert veritabani.postgres_sql("WHERE kullanici_id = :k OR x = :k") == \
        "WHERE kullanici_id = %(k)s OR x = %(k)s"


def test_postgres_sql_metin_ve_yorumlara_dokunmaz():
    sorgu = "UPDATE y SET z = '2026-01-01 00:00:00' -- ne zaman? :)\nWHERE id = ?"
    assert veritabani.postgres_sql(sorgu) == \
        "UPDATE y SET z = '2026-01-01 00:00:00' -- ne zaman? :)\nWHERE id = %s"


def test_postgres_sql_yuzde_isaretini_kacirir():
    # psycopg'de % özel işaret; metin içindeki % da %% olmalı (psycopg geri tek %'ye çevirir)
    assert veritabani.postgres_sql("WHERE a LIKE '%x%' AND b = ?") == "WHERE a LIKE '%%x%%' AND b = %s"


def test_postgres_sql_tablo_tanimini_cevirir():
    sorgu = "CREATE TABLE k (id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT UNIQUE COLLATE NOCASE)"
    assert veritabani.postgres_sql(sorgu) == "CREATE TABLE k (id SERIAL PRIMARY KEY, ad TEXT UNIQUE)"


def test_satir_hem_isimle_hem_sirayla_okunur():
    satir = veritabani.Satir([("id", 7), ("proje", "Not defteri")])
    assert satir["proje"] == "Not defteri" and satir[0] == 7 and dict(satir)["id"] == 7


def test_kullanici_adi_buyuk_kucuk_harf_farketmez(kayit_ol):
    kayit_ol("Ali")
    assert veritabani.kullanici_ekle("ali", "sifre123") is None       # Aynı ad sayılır
    assert veritabani.kullanici_dogrula("ALI", "sifre123")["kullanici_adi"] == "Ali"


def test_gecmiste_arama_buyuk_kucuk_harf_farketmez(kayit_ol):
    from conftest import yol_haritasi_cikar
    ali = kayit_ol("ali")
    yol_haritasi_cikar(ali, "Hesap Makinesi")
    assert len(veritabani.tum_yol_haritalari(ali.kullanici["id"], ara="hesap")) == 1


def test_cevap_adimlara_bolunuyor():
    parcalar = veritabani.cevabi_parcala(ORNEK_CEVAP)
    assert parcalar["giris"].startswith("Harika bir proje")
    assert [baslik for baslik, _ in parcalar["adimlar"]] == [
        "Adım 1: Menüyü Planlama", "Adım 2: Görev Ekleme",
        "Adım 3: Görevleri Listeleme", "Adım 4: Dosyaya Kaydetme"]
    assert "**Ne yapılacak:**" in parcalar["adimlar"][0][1]
    assert parcalar["dikkat"].startswith("## Dikkat et")
    assert "Hemen ilk adıma başla!" in parcalar["dikkat"]


def test_kalin_yazili_baslik_temizleniyor():
    parcalar = veritabani.cevabi_parcala("### **Adım 1: Başla**\n- madde")
    assert parcalar["adimlar"][0][0] == "Adım 1: Başla"


def test_bicimsiz_cevapta_adim_yok():
    parcalar = veritabani.cevabi_parcala("Sadece düz bir paragraf.")
    assert parcalar["adimlar"] == []
    assert parcalar["giris"] == "Sadece düz bir paragraf."


@pytest.mark.skipif(veritabani.POSTGRES, reason="Eski SQLite dosyasının yükseltilmesi; PostgreSQL'de anlamsız")
def test_eski_veritabani_kayip_olmadan_yukseltiliyor(tmp_path, monkeypatch):
    """8. haftanın ilk sürümüyle oluşmuş bir veritabanı: yeni sütunlar ve tablolar yok."""
    dosya = tmp_path / "eski.db"
    b = sqlite3.connect(dosya)
    b.executescript("""
        CREATE TABLE yol_haritalari (id INTEGER PRIMARY KEY AUTOINCREMENT, proje TEXT NOT NULL,
          bilgi TEXT, giris TEXT, dikkat TEXT, ham_cevap TEXT NOT NULL, dosya_yolu TEXT,
          olusturma_zamani TEXT NOT NULL);
        CREATE TABLE adimlar (id INTEGER PRIMARY KEY AUTOINCREMENT, yol_haritasi_id INTEGER NOT NULL,
          sira INTEGER NOT NULL, baslik TEXT NOT NULL, icerik TEXT,
          tamamlandi INTEGER NOT NULL DEFAULT 0, tamamlanma_zamani TEXT);
        INSERT INTO yol_haritalari VALUES (1, 'Eski proje', NULL, 'g', '', 'x', NULL, '2026-11-09 10:00:00');
        INSERT INTO adimlar VALUES (1, 1, 1, 'Adım 1: A', '- x', 1, NULL);
    """)
    b.commit()
    b.close()

    monkeypatch.setattr(veritabani, "VERITABANI_DOSYASI", str(dosya))
    veritabani.hazirla()
    veritabani.hazirla()          # İkinci kez çalışınca da hata vermemeli

    b = sqlite3.connect(dosya)
    tablolar = {r[0] for r in b.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"ipuclari", "kullanicilar", "siniflar", "sinif_uyeleri",
            "commitler", "ogretmen_yorumlari"} <= tablolar
    adim_sutunlari = [r[1] for r in b.execute("PRAGMA table_info(adimlar)")]
    harita_sutunlari = [r[1] for r in b.execute("PRAGMA table_info(yol_haritalari)")]
    assert "not_metni" in adim_sutunlari
    assert {"kullanici_id", "github_depo", "github_son_kontrol"} <= set(harita_sutunlari)
    # Eski kayıt ve ilerlemesi yerinde
    assert b.execute("SELECT proje FROM yol_haritalari").fetchone()[0] == "Eski proje"
    assert b.execute("SELECT tamamlandi FROM adimlar").fetchone()[0] == 1
