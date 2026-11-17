"""
KodKoç - Sunum için örnek (demo) veri (9. hafta)

Boş bir sitede öğretmen panelini göstermek zor: tablo boş, rapor boş, grafik boş.
Bu betik bir demo öğretmen, bir sınıf ve farklı durumlarda üç öğrenci oluşturur:
  - demo_elif : neredeyse bitirmiş, notlar yazmış, hedefini zamanında tutturmuş
  - demo_can  : bir adımda takılmış (3 ipucu), hedefi geçmiş, öğretmenine soru sormuş
  - demo_deniz: sınıfa katılmış ama henüz başlamamış
Yapay zekâ KULLANILMAZ (kota harcamaz); yol haritası metni bu dosyada hazır yazılı.

Kullanım (PowerShell):
    python demo_veri.py olustur <şifre>     # Bütün demo hesaplar bu şifreyle açılır
    python demo_veri.py sil <şifre>         # Demo hesapları ve her şeylerini siler
Canlı veritabanında çalıştırmak için önce $env:DATABASE_URL = "postgresql://..." yazılır.

Güvenlik: Demo hesaplar zaten varsa "olustur" hiçbir şey yapmaz. Şifre en az 8 karakter
olmalı; canlı sitede herkesin bildiği "1234" gibi bir şifreyle öğretmen hesabı açılmasın.
"""

import sys
from datetime import date, datetime, timedelta

import veritabani

OGRETMEN = "demo_ogretmen"
OGRENCILER = ["demo_elif", "demo_can", "demo_deniz"]
EN_KISA_SIFRE = 8

SINIF_PROJESI = ("Python ile bir yapılacaklar listesi uygulaması: görev ekleme, listeleme, "
                 "tamamlandı işaretleme ve görevleri dosyaya kaydetme.")

YOL_HARITASI = """Güzel bir proje, adım adım ilerleyelim.

### Adım 1: Menüyü Planlama
- **Ne yapılacak:** Kullanıcının göreceği menüyü tasarla ve bir döngüyle tekrar göster.
- **Öğrenilecek konular:** while döngüsü, input, if/elif
- **Nasıl anlarsın:** Menü, çıkış seçilene kadar tekrar tekrar geliyor.

### Adım 2: Görev Ekleme
- **Ne yapılacak:** Kullanıcının yazdığı görevi bir listeye ekle.
- **Öğrenilecek konular:** Listeler, append
- **Nasıl anlarsın:** Eklediğin görev listede duruyor.

### Adım 3: Görevleri Listeleme
- **Ne yapılacak:** Görevleri numaralı olarak alt alta yazdır.
- **Öğrenilecek konular:** for döngüsü, enumerate, f-string
- **Nasıl anlarsın:** Görevler 1, 2, 3 diye numaralı çıkıyor.

### Adım 4: Tamamlandı İşaretleme
- **Ne yapılacak:** Numarası verilen görevi tamamlandı olarak işaretle.
- **Öğrenilecek konular:** Sözlükler, int() dönüşümü, hata kontrolü
- **Nasıl anlarsın:** Tamamlanan görevin yanında ✓ görünüyor.

### Adım 5: Dosyaya Kaydetme
- **Ne yapılacak:** Görevleri dosyaya yaz, program açılınca geri oku.
- **Öğrenilecek konular:** open, with, read/write
- **Nasıl anlarsın:** Programı kapatıp açınca görevler kaybolmuyor.

## Dikkat et
- Sayı yerine harf girilirse program çökmesin.

İlk adımla başla!
"""


def zaman(gun_once, saat=15):
    """Bugünden 'gun_once' gün önceki bir saat: '2026-11-15 15:00:00' biçiminde."""
    return (datetime.now() - timedelta(days=gun_once)).replace(
        hour=saat, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def guncelle(sorgu, degerler):
    """Demo kayıtların tarihlerini geçmişe almak için küçük bir yardımcı (tek UPDATE)."""
    baglanti = veritabani.baglan()
    try:
        baglanti.execute(sorgu, degerler)
        baglanti.commit()
    finally:
        baglanti.close()


def adimlari(harita_id):
    baglanti = veritabani.baglan()
    try:
        return [s["id"] for s in baglanti.execute(
            "SELECT id FROM adimlar WHERE yol_haritasi_id = ? ORDER BY sira", (harita_id,)).fetchall()]
    finally:
        baglanti.close()


def adim_bitir(adim_id, gun_once):
    veritabani.adim_durumunu_degistir(adim_id, True)
    guncelle("UPDATE adimlar SET tamamlanma_zamani = ? WHERE id = ?", (zaman(gun_once), adim_id))


def ipucu(adim_id, seviye, gun_once):
    veritabani.ipucu_ekle(adim_id, seviye, "Nereden başlayacağımı bilmiyorum.",
                          "Önce küçük bir parça dene: tek bir görevi listeye ekleyip yazdır.")
    guncelle("UPDATE ipuclari SET olusturma_zamani = ? WHERE adim_id = ? AND seviye = ?",
             (zaman(gun_once, 16), adim_id, seviye))


def olustur(sifre):
    """Demo öğretmeni, sınıfı ve öğrencileri oluşturur; özet sözlük döndürür."""
    if len(sifre) < EN_KISA_SIFRE:
        raise SystemExit(f"Şifre en az {EN_KISA_SIFRE} karakter olmalı.")
    veritabani.hazirla()
    ogretmen_id = veritabani.kullanici_ekle(OGRETMEN, sifre, "ogretmen")
    if ogretmen_id is None:
        raise SystemExit(f"'{OGRETMEN}' zaten var; demo veri daha önce oluşturulmuş. "
                         "Baştan kurmak için önce: python demo_veri.py sil <şifre>")
    ids = {ad: veritabani.kullanici_ekle(ad, sifre) for ad in OGRENCILER}

    sinif_id = veritabani.sinif_olustur(ogretmen_id, "Demo Sınıfı · 10-A")
    veritabani.sinif_proje_ayarla(sinif_id, SINIF_PROJESI)
    kod = veritabani.sinif_getir(sinif_id, ogretmen_id)["katilim_kodu"]
    for ogrenci_id in ids.values():
        veritabani.sinifa_katil(ogrenci_id, kod)
    veritabani.duyuru_ekle(sinif_id, "Cuma gününe kadar 3. adımı bitirmeye çalışın. "
                                     "Takılan öğretmenine sor düğmesini kullansın!")

    # --- Elif: 5 adımın 4'ü bitti, son 4 gündür her gün çalışmış, notlar yazmış ---
    elif_harita = veritabani.yol_haritasi_ekle(SINIF_PROJESI, "Python temel seviye", YOL_HARITASI,
                                               kullanici_id=ids["demo_elif"], sinif_id=sinif_id)
    guncelle("UPDATE yol_haritalari SET olusturma_zamani = ? WHERE id = ?", (zaman(8, 10), elif_harita))
    elif_adimlar = adimlari(elif_harita)
    veritabani.hedef_tarih_ayarla(elif_adimlar[2], (date.today() - timedelta(days=1)).isoformat())
    for adim_id, gun_once in zip(elif_adimlar[:4], (4, 3, 2, 1)):
        adim_bitir(adim_id, gun_once)
    ipucu(elif_adimlar[3], 1, 1)
    veritabani.not_kaydet(elif_adimlar[0], "while True ile sonsuz döngü kurup 'q' gelince break ile çıktım.")
    veritabani.not_kaydet(elif_adimlar[2], "enumerate(liste, 1) numaralamayı 1'den başlatıyor.")
    veritabani.not_kaydet(elif_adimlar[3], "int() harf gelince ValueError veriyor; try/except ile yakaladım.")
    veritabani.yol_haritasi_degerlendir(elif_harita, ogretmen_id, 5,
                                        "Çok düzenli çalışıyorsun, notların da harika. Son adımda başarılar!")

    # --- Can: 1. adımı bitirmiş, 2. adımda 3 ipucu almış, hedefi geçmiş, öğretmenine sormuş ---
    can_harita = veritabani.yol_haritasi_ekle(SINIF_PROJESI, "", YOL_HARITASI,
                                              kullanici_id=ids["demo_can"], sinif_id=sinif_id)
    guncelle("UPDATE yol_haritalari SET olusturma_zamani = ? WHERE id = ?", (zaman(7, 11), can_harita))
    can_adimlar = adimlari(can_harita)
    adim_bitir(can_adimlar[0], 6)
    for seviye, gun_once in ((1, 5), (2, 4), (3, 2)):
        ipucu(can_adimlar[1], seviye, gun_once)
    veritabani.hedef_tarih_ayarla(can_adimlar[1], (date.today() - timedelta(days=2)).isoformat())
    veritabani.ogretmene_soru_ekle(can_adimlar[1], "append yazınca liste neden hep boş görünüyor?")
    veritabani.yorum_ekle(can_adimlar[0], ogretmen_id, "Menün çok güzel olmuş, aferin!")

    # demo_deniz: hiçbir şey yapmadı (raporda "Başlamadı" görünsün diye)
    return {"ogretmen": OGRETMEN, "ogrenciler": OGRENCILER, "sinif_id": sinif_id, "kod": kod}


def sil(sifre):
    """Demo hesapları (ve onlara ait her şeyi) siler; silinen hesap sayısını döndürür."""
    silinen = 0
    for ad in OGRENCILER + [OGRETMEN]:              # Öğretmen en son: önce öğrencilerin kayıtları
        kullanici = veritabani.kullanici_dogrula(ad, sifre)
        if kullanici and veritabani.hesap_sil(kullanici["id"], sifre):
            silinen += 1
    return silinen


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("olustur", "sil"):
        raise SystemExit("Kullanım: python demo_veri.py olustur <şifre>   |   python demo_veri.py sil <şifre>")
    yer = "PostgreSQL" if veritabani.POSTGRES else veritabani.VERITABANI_DOSYASI
    if sys.argv[1] == "olustur":
        ozet = olustur(sys.argv[2])
        print(f"Demo veri oluşturuldu ({yer}).")
        print(f"  Öğretmen : {ozet['ogretmen']}")
        print(f"  Öğrenciler: {', '.join(ozet['ogrenciler'])}")
        print(f"  Sınıf kodu: {ozet['kod']}  (şifreler: komutta yazdığın şifre)")
    else:
        print(f"{sil(sys.argv[2])} demo hesap silindi ({yer}).")
