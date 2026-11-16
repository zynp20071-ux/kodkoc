"""
KodKoç - SQLite'tan PostgreSQL'e veri taşıma (9. hafta)

Bilgisayarındaki kodkoc.db dosyasındaki her şeyi (hesaplar, yol haritaları,
adımlar, ipuçları, sınıflar...) canlı sunucunun PostgreSQL veritabanına kopyalar.
Böylece canlıya geçince eski çalışmalar kaybolmaz.

Kullanım (PowerShell):
    $env:DATABASE_URL = "postgresql://..."      # Sunucudaki veritabanının adresi
    python tasima.py kodkoc.db

Güvenlik: Hedef veritabanında zaten kullanıcı varsa hiçbir şey yapmaz
(yanlışlıkla iki kez çalıştırıp verileri karıştırmayalım diye).
"""

import sqlite3
import sys

import veritabani

# Sıra önemli: Bir tablo, yabancı anahtarla bağlı olduğu tablodan SONRA taşınmalı
# (ör. adımlar, ait oldukları yol haritasından önce eklenemez).
TABLOLAR = [
    "kullanicilar", "yol_haritalari", "adimlar", "ipuclari", "siniflar", "sinif_uyeleri",
    "commitler", "ogretmen_yorumlari", "kod_incelemeleri", "koc_sorulari", "duyurular",
    "yz_kullanimi",
]

# Otomatik artan id'si olan tablolar (taşıdıktan sonra sayaçları ayarlanacak)
ID_LI_TABLOLAR = ["kullanicilar", "yol_haritalari", "adimlar", "ipuclari", "siniflar",
                  "commitler", "ogretmen_yorumlari", "kod_incelemeleri", "koc_sorulari", "duyurular"]


def tasi(sqlite_dosyasi):
    """Verileri taşır ve {tablo: satır sayısı} döndürür."""
    if not veritabani.POSTGRES:
        raise SystemExit("DATABASE_URL ayarlı değil (ya da PostgreSQL adresi değil).")

    veritabani.hazirla()                      # Hedefte tablolar yoksa oluştur
    kaynak = sqlite3.connect(sqlite_dosyasi)
    kaynak.row_factory = sqlite3.Row
    hedef = veritabani.baglan()
    try:
        if hedef.execute("SELECT COUNT(*) FROM kullanicilar").fetchone()[0] > 0:
            raise SystemExit("Hedef veritabanında zaten kullanıcı var; taşıma yapılmadı.")

        sqlite_tablolari = {s[0] for s in kaynak.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
        sayilar = {}
        for tablo in TABLOLAR:
            if tablo not in sqlite_tablolari:          # Eski bir kodkoc.db'de olmayabilir
                continue
            # Sadece iki tarafta da olan sütunlar (eski dosyada bazı sütunlar eksik olabilir)
            kaynak_sutunlari = [s["name"] for s in kaynak.execute(f"PRAGMA table_info({tablo})")]
            hedef_sutunlari = {s[0] for s in hedef.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = ?", (tablo,))}
            sutunlar = [s for s in kaynak_sutunlari if s in hedef_sutunlari]

            satirlar = [tuple(s) for s in kaynak.execute(f"SELECT {', '.join(sutunlar)} FROM {tablo}")]
            if satirlar:
                yer_tutucular = ", ".join("?" * len(sutunlar))
                hedef.executemany(
                    f"INSERT INTO {tablo} ({', '.join(sutunlar)}) VALUES ({yer_tutucular})", satirlar)
            sayilar[tablo] = len(satirlar)

        # id'leri kendimiz verdik; PostgreSQL'in sayacı hâlâ 1'de. Sayacı en büyük id'ye
        # getiriyoruz, yoksa bir sonraki kayıt var olan bir id'yi almaya çalışıp hata verir.
        for tablo in ID_LI_TABLOLAR:
            hedef.execute(f"""SELECT setval(pg_get_serial_sequence('{tablo}', 'id'),
                                            COALESCE((SELECT MAX(id) FROM {tablo}), 0) + 1, false)""")

        hedef.commit()                        # Hepsi tek işlemde: yarıda hata olursa hiçbiri yazılmaz
        return sayilar
    finally:
        hedef.close()
        kaynak.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Kullanım: python tasima.py kodkoc.db")
    for tablo, sayi in tasi(sys.argv[1]).items():
        print(f"{tablo:22} {sayi} satır")
    print("Taşıma tamamlandı.")
