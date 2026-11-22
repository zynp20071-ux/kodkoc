"""
KodKoç - Veritabanı yedeği (9. hafta)

Bütün tabloları tek bir JSON dosyasına yazar: yedekler/kodkoc-2026-11-23-1530.json
Neon'un ücretsiz planı sadece kısa bir süre geriye dönebiliyor; haftada bir yedek almak iyi olur.

Kullanım (PowerShell):
    $env:DATABASE_URL = "postgresql://..."     # Canlı veritabanı (yoksa yereldeki kodkoc.db)
    python yedek_al.py                          # Yedek al
    python yedek_al.py geri yedekler/x.json     # BOŞ bir veritabanına geri yükle

UYARI: Yedekte şifre özetleri, mesajlar ve notlar var. Dosyayı kimseyle paylaşma,
GitHub'a yükleme (yedekler/ klasörü .gitignore'da).
"""

import json
import os
import sys
from datetime import datetime

import veritabani

# Geri yüklerken sıra önemli: bir tablo, bağlı olduğu tablodan SONRA eklenmeli.
SIRA = ["kullanicilar", "siniflar", "sinif_uyeleri", "yol_haritalari", "adimlar", "ipuclari", "commitler",
        "ogretmen_yorumlari", "kod_incelemeleri", "koc_sorulari", "duyurular", "yz_kullanimi",
        "giris_denemeleri", "ogretmen_sorulari", "mesajlar", "sohbet_okuma", "engellemeler", "quizler",
        "odevler", "teslimler", "gruplar", "grup_uyeleri", "gorevler", "grup_okuma", "sablonlar",
        "sifre_sifirlama", "sikayetler"]


def yedek_al(klasor="yedekler"):
    """Bütün tabloları okuyup JSON dosyasına yazar; dosyanın yolunu döndürür."""
    veritabani.hazirla()
    veri = {"zaman": datetime.now().isoformat(timespec="seconds"),
            "tablolar": {t: veritabani.tablonun_satirlari(t) for t in veritabani.tablo_adlari()}}
    os.makedirs(klasor, exist_ok=True)
    yol = os.path.join(klasor, f"kodkoc-{datetime.now():%Y-%m-%d-%H%M%S}.json")
    with open(yol, "w", encoding="utf-8") as dosya:
        json.dump(veri, dosya, ensure_ascii=False, indent=1, default=str)
    return yol


def geri_yukle(yol):
    """Yedeği BOŞ bir veritabanına yükler (doluysa hiçbir şey yapmaz). {tablo: satır sayısı} döndürür."""
    with open(yol, encoding="utf-8") as dosya:
        tablolar = json.load(dosya)["tablolar"]
    veritabani.hazirla()
    baglanti = veritabani.baglan()
    try:
        if baglanti.execute("SELECT COUNT(*) FROM kullanicilar").fetchone()[0] > 0:
            raise SystemExit("Hedef veritabanında zaten kullanıcı var; geri yükleme yapılmadı.")
        sayilar = {}
        for tablo in SIRA + sorted(set(tablolar) - set(SIRA)):
            satirlar = tablolar.get(tablo, [])
            if satirlar:
                sutunlar = list(satirlar[0])
                yer = ", ".join("?" * len(sutunlar))
                baglanti.executemany(f"INSERT INTO {tablo} ({', '.join(sutunlar)}) VALUES ({yer})",
                                     [tuple(s[c] for c in sutunlar) for s in satirlar])
            sayilar[tablo] = len(satirlar)
        if veritabani.POSTGRES:
            # id sayaçlarını en büyük id'ye getir (tasima.py'deki gibi)
            for tablo, satirlar in tablolar.items():
                if satirlar and "id" in satirlar[0]:
                    baglanti.execute(f"""SELECT setval(pg_get_serial_sequence('{tablo}', 'id'),
                                         COALESCE((SELECT MAX(id) FROM {tablo}), 0) + 1, false)""")
        baglanti.commit()
        return sayilar
    finally:
        baglanti.close()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "geri":
        for tablo, sayi in geri_yukle(sys.argv[2]).items():
            print(f"{tablo:22} {sayi} satır")
        print("Geri yükleme tamamlandı.")
    elif len(sys.argv) == 1:
        print("Yedek alındı:", yedek_al())
    else:
        raise SystemExit("Kullanım: python yedek_al.py   |   python yedek_al.py geri <dosya.json>")
