"""
KodKoç - Veritabanı (8. hafta)

Bu dosya yol haritalarını ve adımlarını bir SQLite veritabanında saklar.

SQLite nedir?
  Ayrı bir sunucu kurmadan, tek bir dosya (kodkoc.db) içinde çalışan bir
  veritabanıdır. Python'un içinde hazır gelir ("import sqlite3"), ayrıca
  kurulum gerekmez.

9. hafta (canlıya geçiş): Aynı kod PostgreSQL ile de çalışır. DATABASE_URL
  ayarı verilirse PostgreSQL'e bağlanılır (aşağıdaki "SQLite mi, PostgreSQL mi?"
  bölümüne bak). Sorgular SQLite yazımıyla yazılır, Baglanti sınıfı gerekirse çevirir.

İki tablomuz var:

  yol_haritalari                      adimlar
  +------------------+                +---------------------+
  | id  (birincil)   | <------------- | yol_haritasi_id     |  (yabancı anahtar)
  | proje            |   1 harita     | id  (birincil)      |
  | bilgi            |   = çok adım   | sira                |
  | giris            |                | baslik              |
  | dikkat           |                | icerik              |
  | ham_cevap        |                | tamamlandi (0 / 1)  |
  | dosya_yolu       |                | tamamlanma_zamani   |
  | olusturma_zamani |                | not_metni           |
  +------------------+                +---------------------+
                                                 ^
                                      ipuclari   |
                                      +---------------------+
                                      | id  (birincil)      |
                                      | adim_id ------------+  (yabancı anahtar)
                                      | seviye (1, 2, 3)    |
                                      | soru                |
                                      | cevap               |
                                      | olusturma_zamani    |
                                      +---------------------+

Bir yol haritasının birden çok adımı olur ("bire-çok ilişki"). Adımlar
tablosundaki yol_haritasi_id sütunu, adımın hangi yol haritasına ait
olduğunu gösterir. Aynı şekilde bir adımın birden çok ipucu olabilir.

Kullanıcı girişi eklenince bir tablo daha geldi:

  kullanicilar                         yol_haritalari
  +------------------+                 +------------------+
  | id  (birincil)   | <-------------- | kullanici_id     |  (yabancı anahtar)
  | kullanici_adi    |  1 kullanıcı    | ...              |
  | sifre_hash       |  = çok harita   +------------------+
  | olusturma_zamani |
  +------------------+

Öğretmen paneli için iki tablo daha:

  siniflar                             sinif_uyeleri  (ARA TABLO)
  +------------------+                 +--------------------+
  | id  (birincil)   | <-------------- | sinif_id           |  (sinif_id + ogrenci_id
  | ad               |                 | ogrenci_id  -------+---> kullanicilar
  | katilim_kodu     |                 | katilma_zamani     |   birlikte birincil anahtar)
  | ogretmen_id  ----+--> kullanicilar +--------------------+
  +------------------+

GitHub takibi için "commitler" tablosu: her commit bir yol haritasına,
mesajında "Adım N" geçiyorsa ayrıca o adıma (adim_id) bağlanır.
"ogretmen_yorumlari" tablosu: öğretmenin bir adıma bıraktığı yorumlar
(adim_id -> adimlar, ogretmen_id -> kullanicilar).
"kod_incelemeleri" tablosu: öğrencinin bir adım için gönderdiği kod ve
yapay zekânın (kod vermeden) yazdığı geri bildirim (adim_id -> adimlar).

Bir sınıfta çok öğrenci, bir öğrencinin de çok sınıfı olabilir ("çoka-çok ilişki").
kullanicilar tablosundaki "rol" sütunu kişinin öğrenci mi öğretmen mi olduğunu söyler.

Şifreler veritabanına AÇIK METİN olarak yazılmaz; sadece "hash"leri saklanır.
Hash tek yönlüdür: hash'ten şifre geri bulunamaz. Giriş yapılırken girilen
şifrenin hash'i, kayıtlı hash ile karşılaştırılır.
"""

import atexit
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta

from dotenv import load_dotenv
# Flask ile birlikte gelen werkzeug kütüphanesinin şifre fonksiyonları
from werkzeug.security import check_password_hash, generate_password_hash

KLASOR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(KLASOR, ".env"))   # Aşağıdaki ayarlar .env'de de olabilir

# Veritabanı dosyası, program nereden başlatılırsa başlatılsın proje klasöründe durur.
# Canlı sunucuda dosyanın yeri VERITABANI_YOLU ayarıyla değiştirilebilir
# (ör. sunucunun kalıcı diskindeki /var/data/kodkoc.db).
VERITABANI_DOSYASI = os.getenv("VERITABANI_YOLU") or os.path.join(KLASOR, "kodkoc.db")

# ---------------------------------------------------------------------------
# SQLite mi, PostgreSQL mi?
# ---------------------------------------------------------------------------
#
# SQLite tek bir dosyadır; kendi bilgisayarımızda harika çalışır. Ama ücretsiz
# sunucuların çoğunda dosyalar her yeniden başlatmada silinir, yani veriler kaybolur.
# PostgreSQL ise ayrı çalışan bir veritabanı SUNUCUSUDUR (Render, Neon, Supabase
# ücretsiz verir). Programımız ona internet üzerinden bağlanır, veriler orada kalıcıdır.
#
# Sunucu ayarlarında DATABASE_URL varsa PostgreSQL, yoksa SQLite kullanılır.
# Örnek: DATABASE_URL=postgresql://kullanici:sifre@sunucu-adresi/veritabani_adi
VERITABANI_URL = os.getenv("DATABASE_URL", "")
POSTGRES = VERITABANI_URL.startswith(("postgres://", "postgresql://"))

if POSTGRES:
    # Sadece PostgreSQL kullanılacaksa yüklenir; yerelde bu kütüphanelere gerek yok.
    import psycopg
    from psycopg_pool import ConnectionPool
    # Aynı kullanıcı adı / sınıf kodu ikinci kez eklenince gelen hata (iki veritabanında da)
    BUTUNLUK_HATASI = (sqlite3.IntegrityError, psycopg.IntegrityError)
else:
    BUTUNLUK_HATASI = (sqlite3.IntegrityError,)

# Bazı SQL fonksiyonlarının adı iki veritabanında farklı. Sorgularda f-string ile kullanılır.
# "İki (ya da daha çok) değerden büyüğü": SQLite'ta MAX(a, b), PostgreSQL'de GREATEST(a, b)
BUYUGU = "GREATEST" if POSTGRES else "MAX"


# ---------------------------------------------------------------------------
# 1) BAĞLANTI VE TABLOLARI OLUŞTURMA
# ---------------------------------------------------------------------------

class Satir(dict):
    """
    PostgreSQL'den gelen bir satır. sqlite3.Row gibi hem satir["proje"]
    hem de satir[0] (sıra numarasıyla) yazılabilsin diye dict'ten türettik.
    """
    def __getitem__(self, anahtar):
        if isinstance(anahtar, int):
            return list(self.values())[anahtar]
        return super().__getitem__(anahtar)


def _satir_fabrikasi(imlec):
    """psycopg her sorgunun satırlarını bu fonksiyonla Satir nesnesine çevirir."""
    sutunlar = [s.name for s in imlec.description] if imlec.description else []
    return lambda degerler: Satir(zip(sutunlar, degerler))


# Tek tırnaklı metinler ('...') ve "--" yorumları: bunların İÇİNDEKİ ? ve : işaretlerine dokunmayız
_METIN_VEYA_YORUM = re.compile(r"('(?:[^']|'')*'|--[^\n]*)")


def postgres_sql(sorgu):
    """
    SQLite için yazılmış bir sorguyu PostgreSQL'in anlayacağı hale getirir:
      ?        -> %s        (sıralı yer tutucu)
      :k       -> %(k)s     (isimli yer tutucu)
      %        -> %%        (psycopg'de % özel bir işarettir)
      INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL PRIMARY KEY  (otomatik artan id)
      COLLATE NOCASE -> (silinir; büyük/küçük harf farkını LOWER() ile çözüyoruz)
    """
    parcalar = _METIN_VEYA_YORUM.split(sorgu)
    for i, parca in enumerate(parcalar):
        if i % 2 == 1:                       # Tek sıradakiler: metin ya da yorum
            parcalar[i] = parca.replace("%", "%%")
            continue
        parca = parca.replace("%", "%%").replace("?", "%s")
        parcalar[i] = re.sub(r"(?<!:):([A-Za-z_]\w*)", r"%(\1)s", parca)
    sorgu = "".join(parcalar)
    sorgu = sorgu.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    return sorgu.replace(" COLLATE NOCASE", "")


_havuz = None
_havuz_sureci = None          # Havuzu hangi süreç (process) açtı? (os.getpid() değeri)


def _postgres_havuzu():
    """
    Bağlantı havuzu (connection pool): Uzaktaki sunucuya her sorguda yeniden
    bağlanmak yavaştır. Havuz birkaç bağlantıyı açık tutar ve tekrar tekrar kullanır.
    İlk ihtiyaç anında oluşturulur.

    DİKKAT, "fork": Sunucuda gunicorn önce programı bir kez yükler (havuz burada açılır),
    sonra kendini işçilere (worker) KOPYALAR. Havuz yeni bağlantıları arka plandaki
    yardımcı iş parçacıklarıyla (thread) açar ve bunlar kopyaya taşınmaz. Kopyadaki havuz
    bağlantı açacak kimse olmadığı için sonsuza kadar bekler. Canlıda tam olarak bu yaşandı.
    Çözüm: Havuzu açan sürecin numarasını tutuyoruz; başka bir süreçteysek yenisini açıyoruz.
    (Eski havuzu kapatmıyoruz: bağlantıları ana süreçle ortak, kapatırsak onunkiler de kopar.)
    """
    global _havuz, _havuz_sureci
    if _havuz is None or _havuz_sureci != os.getpid():
        _havuz_sureci = os.getpid()
        _havuz = ConnectionPool(
            VERITABANI_URL, min_size=1, max_size=5, open=True,
            kwargs={"row_factory": _satir_fabrikasi},
            check=ConnectionPool.check_connection,   # Vermeden önce bağlantı sağlam mı bak, kopuksa yenile
            # Neon boşta kalan veritabanını birkaç dakika sonra uyutur ve açık bağlantıları koparır.
            # Boşta 1 dakikadan uzun bekleyen bağlantıyı kendimiz kapatıyoruz, kopmuşunu beklemeyelim.
            max_idle=60,
            max_lifetime=600,                        # Hiçbir bağlantı 10 dakikadan uzun yaşamasın
            timeout=15,                              # Bağlantı alınamazsa 30 değil 15 sn sonra hata ver
        )
    return _havuz


@atexit.register
def _havuzu_kapat():
    """Program kapanırken bağlantıları düzgünce kapat (sadece havuzu bu süreç açtıysa)."""
    if _havuz is not None and _havuz_sureci == os.getpid():
        _havuz.close()


class Baglanti:
    """
    SQLite ve PostgreSQL bağlantısını AYNI şekilde kullanabilmemiz için küçük bir sarmalayıcı.
    Kodun geri kalanı hangi veritabanının kullanıldığını bilmek zorunda kalmaz:
    execute, executemany, commit, rollback, close her ikisinde de aynı.
    """
    def __init__(self):
        if POSTGRES:
            self._baglanti = _postgres_havuzu().getconn()
        else:
            self._baglanti = sqlite3.connect(VERITABANI_DOSYASI)
            # Satırları sözlük gibi kullanabilmek için: satir["proje"] yazabiliriz.
            self._baglanti.row_factory = sqlite3.Row
            # SQLite yabancı anahtar kontrolünü varsayılan olarak kapalı tutar, açıyoruz.
            self._baglanti.execute("PRAGMA foreign_keys = ON")

    def execute(self, sorgu, degerler=()):
        if POSTGRES:
            return self._baglanti.execute(postgres_sql(sorgu), degerler)
        return self._baglanti.execute(sorgu, degerler)

    def executemany(self, sorgu, degerler_listesi):
        if POSTGRES:
            imlec = self._baglanti.cursor()
            imlec.executemany(postgres_sql(sorgu), degerler_listesi)
            return imlec
        return self._baglanti.executemany(sorgu, degerler_listesi)

    def ekle(self, sorgu, degerler=()):
        """
        INSERT yapar ve eklenen satırın id'sini döndürür.
        SQLite'ta imlec.lastrowid yeterli; PostgreSQL'de sorgunun sonuna
        "RETURNING id" ekleyip id'yi sorgunun cevabından okuruz.
        """
        if POSTGRES:
            return self.execute(sorgu + " RETURNING id", degerler).fetchone()[0]
        return self.execute(sorgu, degerler).lastrowid

    def commit(self):
        self._baglanti.commit()

    def rollback(self):
        """Yarım kalan işlemi geri alır (PostgreSQL'de hatadan sonra devam etmek için şart)."""
        self._baglanti.rollback()

    def close(self):
        if POSTGRES:
            try:
                self._baglanti.rollback()                # Commit edilmemiş bir şey kalmasın
            except psycopg.Error:
                # Bağlantı bu arada kopmuş olabilir (ör. Neon veritabanını uyuttu).
                # Hata yutulur; havuz kopuk bağlantıyı geri alınca kendisi atar.
                pass
            finally:
                # finally: rollback hata verse BİLE bağlantı havuza geri verilir. Eskiden verilmiyordu;
                # birkaç kopuk bağlantıdan sonra havuz boşalıyor ve site "bağlantı alınamadı" diye çöküyordu.
                _postgres_havuzu().putconn(self._baglanti)
        else:
            self._baglanti.close()


def baglan():
    """Veritabanına bağlanır ve bağlantıyı döndürür."""
    return Baglanti()


def baglanti_teshisi():
    """
    Havuz bağlantı veremezse sadece "zaman aşımı" (PoolTimeout) görürüz, asıl sebebi değil.
    Bu fonksiyon havuzu kullanmadan, doğrudan bir kez bağlanmayı dener ve asıl hatayı
    (yanlış şifre, sunucu bulunamadı...) metin olarak döndürür. Sorun yoksa None.
    Hata mesajlarında şifre bulunmaz; yine de adres ihtimaline karşı "://" sonrası gizlenir.
    """
    if not POSTGRES:
        return None
    try:
        psycopg.connect(VERITABANI_URL, connect_timeout=10).close()
        return None
    except Exception as hata:
        mesaj = re.sub(r"://\S+", "://***", str(hata).strip())
        return f"{type(hata).__name__}: {mesaj}"


def hazirla():
    """
    Tablolar yoksa oluşturur. Program her açıldığında çağrılır.
    "IF NOT EXISTS" sayesinde tablolar zaten varsa hiçbir şey olmaz,
    eski veriler silinmez.
    """
    baglanti = baglan()
    try:
        if POSTGRES:
            # Sunucuda programın birden çok kopyası ("worker") aynı anda açılabilir.
            # Kilit: tabloları aynı anda iki kopya oluşturmaya çalışıp çakışmasın.
            # (İşlem commit edilince kilit kendiliğinden açılır.)
            baglanti.execute("SELECT pg_advisory_xact_lock(4242)")

        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS yol_haritalari (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                proje            TEXT NOT NULL,
                bilgi            TEXT,
                giris            TEXT,
                dikkat           TEXT,
                ham_cevap        TEXT NOT NULL,
                dosya_yolu       TEXT,
                olusturma_zamani TEXT NOT NULL
            )
        """)
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS adimlar (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                yol_haritasi_id   INTEGER NOT NULL REFERENCES yol_haritalari(id),
                sira              INTEGER NOT NULL,
                baslik            TEXT NOT NULL,
                icerik            TEXT,
                tamamlandi        INTEGER NOT NULL DEFAULT 0,
                tamamlanma_zamani TEXT
            )
        """)
        # Öğrencinin takıldığı adımlar için aldığı ipuçları
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS ipuclari (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                adim_id          INTEGER NOT NULL REFERENCES adimlar(id),
                seviye           INTEGER NOT NULL,
                soru             TEXT,
                cevap            TEXT NOT NULL,
                olusturma_zamani TEXT NOT NULL
            )
        """)

        # Kullanıcılar. UNIQUE: aynı kullanıcı adı iki kez kaydedilemez.
        # COLLATE NOCASE: "Ali" ile "ali" aynı ad sayılır.
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS kullanicilar (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                kullanici_adi    TEXT NOT NULL UNIQUE COLLATE NOCASE,
                sifre_hash       TEXT NOT NULL,
                olusturma_zamani TEXT NOT NULL
            )
        """)

        # Öğretmenin açtığı sınıflar. Öğrenciler katilim_kodu ile katılır.
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS siniflar (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ad               TEXT NOT NULL,
                katilim_kodu     TEXT NOT NULL UNIQUE,
                ogretmen_id      INTEGER NOT NULL REFERENCES kullanicilar(id),
                olusturma_zamani TEXT NOT NULL
            )
        """)
        # ARA TABLO (çoka-çok ilişki): Bir sınıfta çok öğrenci, bir öğrenci de
        # birden çok sınıfta olabilir. Bu ilişkiyi iki tabloya sütun ekleyerek
        # kuramayız; bu yüzden "kim hangi sınıfta" bilgisini ayrı bir tabloda tutarız.
        # PRIMARY KEY (sinif_id, ogrenci_id): "bileşik birincil anahtar";
        # aynı öğrenci aynı sınıfa iki kez eklenemez.
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS sinif_uyeleri (
                sinif_id       INTEGER NOT NULL REFERENCES siniflar(id),
                ogrenci_id     INTEGER NOT NULL REFERENCES kullanicilar(id),
                katilma_zamani TEXT NOT NULL,
                PRIMARY KEY (sinif_id, ogrenci_id)
            )
        """)

        # GitHub'dan çekilen commit'ler. adim_id: mesajında "Adım N" geçiyorsa
        # bağlandığı adım (geçmiyorsa boş). UNIQUE(...): aynı commit aynı yol
        # haritasına iki kez kaydedilmez.
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS commitler (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                yol_haritasi_id INTEGER NOT NULL REFERENCES yol_haritalari(id),
                adim_id         INTEGER REFERENCES adimlar(id),
                sha             TEXT NOT NULL,
                mesaj           TEXT NOT NULL,
                yazar           TEXT,
                tarih           TEXT NOT NULL,
                url             TEXT NOT NULL,
                UNIQUE (yol_haritasi_id, sha)
            )
        """)

        # Öğretmenin, öğrencinin bir adımına bıraktığı yorumlar
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS ogretmen_yorumlari (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                adim_id          INTEGER NOT NULL REFERENCES adimlar(id),
                ogretmen_id      INTEGER NOT NULL REFERENCES kullanicilar(id),
                metin            TEXT NOT NULL,
                olusturma_zamani TEXT NOT NULL
            )
        """)

        # Öğrencinin "Kodumu incelet" ile gönderdiği kodlar ve aldığı geri bildirimler
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS kod_incelemeleri (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                adim_id          INTEGER NOT NULL REFERENCES adimlar(id),
                kod              TEXT NOT NULL,
                aciklama         TEXT,
                geri_bildirim    TEXT NOT NULL,
                olusturma_zamani TEXT NOT NULL
            )
        """)

        # "Koça soru sor": öğrencinin bir adımla ilgili serbest soruları ve koçun cevapları
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS koc_sorulari (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                adim_id          INTEGER NOT NULL REFERENCES adimlar(id),
                soru             TEXT NOT NULL,
                cevap            TEXT NOT NULL,
                olusturma_zamani TEXT NOT NULL
            )
        """)

        # Öğretmenin sınıfa yazdığı duyurular (ör. "Cuma'ya kadar 3. adımı bitirin")
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS duyurular (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                sinif_id         INTEGER NOT NULL REFERENCES siniflar(id),
                metin            TEXT NOT NULL,
                olusturma_zamani TEXT NOT NULL
            )
        """)

        # Canlıya geçiş: herkes aynı Gemini anahtarını paylaştığı için her öğrencinin
        # bir günde yapay zekâya kaç istek gönderdiğini sayıyoruz (gun: "2026-11-16").
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS yz_kullanimi (
                kullanici_id INTEGER NOT NULL REFERENCES kullanicilar(id),
                gun          TEXT NOT NULL,
                sayi         INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (kullanici_id, gun)
            )
        """)
        # Canlıya geçiş: yanlış şifre denemeleri (şifreyi deneye deneye bulmayı engellemek için)
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS giris_denemeleri (
                kullanici_adi TEXT NOT NULL COLLATE NOCASE,
                zaman         TEXT NOT NULL
            )
        """)

        # "Öğretmenime sor": öğrencinin bir adım için öğretmenine sorduğu soru ve cevabı.
        # cevap_goruldu: 0 = cevap geldi ama öğrenci henüz görmedi (menü rozeti için)
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS ogretmen_sorulari (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                adim_id       INTEGER NOT NULL REFERENCES adimlar(id),
                soru          TEXT NOT NULL,
                soru_zamani   TEXT NOT NULL,
                cevap         TEXT,
                cevaplayan_id INTEGER,
                cevap_zamani  TEXT,
                cevap_goruldu INTEGER NOT NULL DEFAULT 1
            )
        """)

        # GÖÇ (migration): Tablolar daha önce bu sütunlar olmadan oluşturulduysa
        # sütunları sonradan ekle. Böylece eski veritabanındaki kayıtlar kaybolmaz.
        sutun_yoksa_ekle(baglanti, "adimlar", "not_metni", "TEXT")
        sutun_yoksa_ekle(baglanti, "yol_haritalari", "kullanici_id",
                         "INTEGER REFERENCES kullanicilar(id)")
        # Rol: "ogrenci" ya da "ogretmen". Eski hesaplar öğrenci sayılır.
        sutun_yoksa_ekle(baglanti, "kullanicilar", "rol", "TEXT NOT NULL DEFAULT 'ogrenci'")
        # GitHub deposu ("kullanici/proje") ve en son ne zaman kontrol edildiği
        sutun_yoksa_ekle(baglanti, "yol_haritalari", "github_depo", "TEXT")
        sutun_yoksa_ekle(baglanti, "yol_haritalari", "github_son_kontrol", "TEXT")
        # Öğrenci yorumu gördü mü? (0 = yeni, 1 = okundu)
        sutun_yoksa_ekle(baglanti, "ogretmen_yorumlari", "okundu", "INTEGER NOT NULL DEFAULT 0")
        # Adımı yapay zekâ mı çıkardı (0), öğrenci mi ekledi (1)?
        sutun_yoksa_ekle(baglanti, "adimlar", "kendi_eklendi", "INTEGER NOT NULL DEFAULT 0")
        # Öğrencinin gördüğü en son duyurunun id'si. Bundan büyük id'li duyurular "yeni" sayılır.
        sutun_yoksa_ekle(baglanti, "kullanicilar", "son_okunan_duyuru", "INTEGER NOT NULL DEFAULT 0")
        # Öğretmen şifreyi sıfırladıysa 1: öğrenci girince önce yeni şifre belirlemek zorunda
        sutun_yoksa_ekle(baglanti, "kullanicilar", "gecici_sifre", "INTEGER NOT NULL DEFAULT 0")
        # Öğretmenin bir adım için koyduğu hedef tarih ("2026-11-21"); yoksa boş (NULL)
        sutun_yoksa_ekle(baglanti, "adimlar", "hedef_tarih", "TEXT")
        # Öğretmenin sınıfa verdiği ortak proje (boşsa yok)
        sutun_yoksa_ekle(baglanti, "siniflar", "proje", "TEXT")
        # Yol haritası bir sınıf projesi için çıkarıldıysa o sınıfın id'si.
        # Bilerek yabancı anahtar (REFERENCES) değil: sınıf silinince yol haritası
        # öğrencinin olarak kalmalı; o zaman bu sütunu boşaltıyoruz (sinif_sil'e bak).
        sutun_yoksa_ekle(baglanti, "yol_haritalari", "sinif_id", "INTEGER")
        # Hedef tarihi kim koydu? "ogretmen" ya da "ogrenci" (eski kayıtlarda boş = öğretmen)
        sutun_yoksa_ekle(baglanti, "adimlar", "hedef_koyan", "TEXT")
        # Öğretmenin yol haritası değerlendirmesi: 1-5 puan, kısa geri bildirim, ne zaman, kim
        sutun_yoksa_ekle(baglanti, "yol_haritalari", "degerlendirme_puan", "INTEGER")
        sutun_yoksa_ekle(baglanti, "yol_haritalari", "degerlendirme_metin", "TEXT")
        sutun_yoksa_ekle(baglanti, "yol_haritalari", "degerlendirme_zamani", "TEXT")
        sutun_yoksa_ekle(baglanti, "yol_haritalari", "degerlendiren_id", "INTEGER")
        # Öğrenci değerlendirmeyi gördü mü? (1 = gördü ya da değerlendirme yok, 0 = yeni)
        sutun_yoksa_ekle(baglanti, "yol_haritalari", "degerlendirme_goruldu", "INTEGER NOT NULL DEFAULT 1")
        # Öğretmen bu soru-cevabı sınıfla paylaştı mı? (1 = sınıftaki herkes görür, soranın adı gizli)
        sutun_yoksa_ekle(baglanti, "ogretmen_sorulari", "paylasildi", "INTEGER NOT NULL DEFAULT 0")

        # Mesajlaşma: sınıf sohbeti (sinif_id dolu) ya da iki kişi arasında özel mesaj (alici_id dolu).
        # Bir mesajda ikisinden biri dolu olur. Silinen mesaj satır olarak kalır, metni boşaltılır
        # ("Bu mesaj silindi" yazsın, sohbetin akışı bozulmasın diye).
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS mesajlar (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                sinif_id    INTEGER REFERENCES siniflar(id),
                gonderen_id INTEGER NOT NULL REFERENCES kullanicilar(id),
                alici_id    INTEGER REFERENCES kullanicilar(id),
                metin       TEXT NOT NULL,
                zaman       TEXT NOT NULL,
                silindi     INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Kim hangi sohbeti nereye kadar okudu? (okunmamış mesaj sayısı için)
        # Sınıf sohbeti için diger_id = 0, özel sohbet için sinif_id = 0.
        # (NULL yerine 0: birincil anahtarın parçası olan sütun boş olamaz.)
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS sohbet_okuma (
                kullanici_id  INTEGER NOT NULL REFERENCES kullanicilar(id),
                sinif_id      INTEGER NOT NULL DEFAULT 0,
                diger_id      INTEGER NOT NULL DEFAULT 0,
                son_okunan_id INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (kullanici_id, sinif_id, diger_id)
            )
        """)
        # İndeks: kitabın sonundaki dizin gibi; sohbet açılırken bütün tabloyu taramadan bulur
        baglanti.execute("CREATE INDEX IF NOT EXISTS mesaj_sinif ON mesajlar (sinif_id, id)")
        baglanti.execute("CREATE INDEX IF NOT EXISTS mesaj_alici ON mesajlar (alici_id, gonderen_id)")
        # Profil: kullanıcının kendini kısaca tanıttığı yazı
        sutun_yoksa_ekle(baglanti, "kullanicilar", "hakkimda", "TEXT")
        # Sınıf sohbet ayarları (öğretmen değiştirir):
        #   sohbet_kilitli = 1: sınıf sohbetine sadece öğretmen yazabilir (duyuru kanalı gibi)
        #   ozel_mesaj     = 1: bu sınıftaki öğrenciler birbirine özel mesaj atabilir
        sutun_yoksa_ekle(baglanti, "siniflar", "sohbet_kilitli", "INTEGER NOT NULL DEFAULT 0")
        sutun_yoksa_ekle(baglanti, "siniflar", "ozel_mesaj", "INTEGER NOT NULL DEFAULT 1")

        # Engellemeler: engelleyen, engellediği kişinin mesajlarını görmez; ikisi özel mesajlaşamaz
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS engellemeler (
                engelleyen_id  INTEGER NOT NULL REFERENCES kullanicilar(id),
                engellenen_id  INTEGER NOT NULL REFERENCES kullanicilar(id),
                zaman          TEXT NOT NULL,
                PRIMARY KEY (engelleyen_id, engellenen_id)
            )
        """)
        # Mini quiz: bir adım için yapay zekânın hazırladığı sorular (JSON metni olarak) ve cevaplar.
        # Adım başına tek satır; "yeni sorular" istenince üstüne yazılır, uretim_sayisi artar.
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS quizler (
                adim_id        INTEGER PRIMARY KEY REFERENCES adimlar(id),
                sorular        TEXT NOT NULL,
                cevaplar       TEXT,
                dogru_sayisi   INTEGER,
                uretim_sayisi  INTEGER NOT NULL DEFAULT 1,
                olusturma_zamani TEXT NOT NULL,
                cevap_zamani   TEXT
            )
        """)
        # Ödevler: öğretmen sınıfa son tarihli ödev verir
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS odevler (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                sinif_id         INTEGER NOT NULL REFERENCES siniflar(id),
                baslik           TEXT NOT NULL,
                aciklama         TEXT,
                son_tarih        TEXT NOT NULL,
                olusturma_zamani TEXT NOT NULL
            )
        """)
        # Teslimler: bir öğrenci bir ödevi bir kez teslim eder (puanlanana kadar güncelleyebilir).
        # goruldu = 0: öğretmen puan verdi, öğrenci henüz bakmadı ("Yeni" etiketi)
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS teslimler (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                odev_id              INTEGER NOT NULL REFERENCES odevler(id),
                ogrenci_id           INTEGER NOT NULL REFERENCES kullanicilar(id),
                metin                TEXT,
                baglanti             TEXT,
                zaman                TEXT NOT NULL,
                puan                 INTEGER,
                yorum                TEXT,
                degerlendirme_zamani TEXT,
                goruldu              INTEGER NOT NULL DEFAULT 1,
                UNIQUE (odev_id, ogrenci_id)
            )
        """)
        # Grup projeleri: öğretmen sınıfta gruplar kurar; her grubun projesi, görev panosu ve sohbeti var
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS gruplar (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                sinif_id         INTEGER NOT NULL REFERENCES siniflar(id),
                ad               TEXT NOT NULL,
                proje            TEXT,
                olusturma_zamani TEXT NOT NULL
            )
        """)
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS grup_uyeleri (
                grup_id    INTEGER NOT NULL REFERENCES gruplar(id),
                ogrenci_id INTEGER NOT NULL REFERENCES kullanicilar(id),
                PRIMARY KEY (grup_id, ogrenci_id)
            )
        """)
        # Görev panosu: durum 'yapilacak' -> 'yapiliyor' -> 'bitti'; atanan_id boşsa kimse üstlenmedi
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS gorevler (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                grup_id      INTEGER NOT NULL REFERENCES gruplar(id),
                metin        TEXT NOT NULL,
                atanan_id    INTEGER REFERENCES kullanicilar(id),
                durum        TEXT NOT NULL DEFAULT 'yapilacak',
                olusturan_id INTEGER REFERENCES kullanicilar(id),
                zaman        TEXT NOT NULL
            )
        """)
        # Grup sohbetinin okunma durumu (sohbet_okuma'nın grup için olanı)
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS grup_okuma (
                kullanici_id  INTEGER NOT NULL REFERENCES kullanicilar(id),
                grup_id       INTEGER NOT NULL REFERENCES gruplar(id),
                son_okunan_id INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (kullanici_id, grup_id)
            )
        """)
        # Grup sohbetindeki mesajlarda grup_id dolu olur (sinif_id ve alici_id boş)
        sutun_yoksa_ekle(baglanti, "mesajlar", "grup_id", "INTEGER")
        # Sohbet grupları: kullanıcının kendi kurduğu grup. olusturan_id = grubu kuran (yöneticisi).
        # Boşsa (NULL) öğretmenin sınıfta kurduğu proje grubudur.
        sutun_yoksa_ekle(baglanti, "gruplar", "olusturan_id", "INTEGER")
        baglanti.execute("CREATE INDEX IF NOT EXISTS mesaj_grup ON mesajlar (grup_id, id)")
        # Proje şablonları: öğretmenin kendi yazdığı adımlar (yapay zekâ yerine). adimlar: düz metin;
        # her adım boş bir satırla ayrılır, ilk satır başlık, kalanı açıklama.
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS sablonlar (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                ogretmen_id      INTEGER NOT NULL REFERENCES kullanicilar(id),
                ad               TEXT NOT NULL,
                adimlar          TEXT NOT NULL,
                olusturma_zamani TEXT NOT NULL
            )
        """)
        # Sınıf projesi bir şablondan mı? (boşsa adımları yapay zekâ çıkarır)
        sutun_yoksa_ekle(baglanti, "siniflar", "sablon_id", "INTEGER")
        # Katılım: kullanıcının siteye en son girdiği gün (günde bir kez güncellenir)
        sutun_yoksa_ekle(baglanti, "kullanicilar", "son_giris", "TEXT")
        # E-postayla şifre sıfırlama: isteğe bağlı e-posta adresi ve tek kullanımlık jetonlar.
        # Jetonun kendisi değil SHA-256 özeti saklanır (veritabanı sızsa bile bağlantı kullanılamasın).
        sutun_yoksa_ekle(baglanti, "kullanicilar", "eposta", "TEXT")
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS sifre_sifirlama (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                kullanici_id  INTEGER NOT NULL REFERENCES kullanicilar(id),
                jeton_ozeti   TEXT NOT NULL UNIQUE,
                olusturma     TEXT NOT NULL,
                son_gecerlilik TEXT NOT NULL,
                kullanildi    INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Öğrencilerin öğretmene bildirdiği mesajlar (küfür, zorbalık...). Aynı kişi aynı mesajı
        # bir kez bildirebilir (UNIQUE). durum: 'acik' ya da 'kapandi'
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS sikayetler (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                mesaj_id     INTEGER NOT NULL REFERENCES mesajlar(id),
                bildiren_id  INTEGER NOT NULL REFERENCES kullanicilar(id),
                sebep        TEXT NOT NULL,
                zaman        TEXT NOT NULL,
                durum        TEXT NOT NULL DEFAULT 'acik',
                UNIQUE (mesaj_id, bildiren_id)
            )
        """)

        # --- 10. hafta: grup davetleri, anketler, resimler ---
        # Grup daveti: sohbet grubuna eklenen kişi önce davet alır, kabul edince üye olur
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS grup_davetleri (
                grup_id         INTEGER NOT NULL REFERENCES gruplar(id),
                davet_edilen_id INTEGER NOT NULL REFERENCES kullanicilar(id),
                davet_eden_id   INTEGER NOT NULL REFERENCES kullanicilar(id),
                zaman           TEXT NOT NULL,
                PRIMARY KEY (grup_id, davet_edilen_id)
            )
        """)
        # Anket: sohbette bir mesaj olarak görünür (mesajlar.anket_id). coklu = 1: birden çok seçenek seçilebilir.
        # bitis: bu günden sonra oy verilemez (boşsa süresiz); kapali = 1: kuran kişi anketi bitirdi.
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS anketler (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                olusturan_id INTEGER NOT NULL REFERENCES kullanicilar(id),
                soru         TEXT NOT NULL,
                coklu        INTEGER NOT NULL DEFAULT 0,
                bitis        TEXT,
                kapali       INTEGER NOT NULL DEFAULT 0,
                zaman        TEXT NOT NULL
            )
        """)
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS anket_secenekleri (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                anket_id INTEGER NOT NULL REFERENCES anketler(id),
                sira     INTEGER NOT NULL,
                metin    TEXT NOT NULL
            )
        """)
        # Bir kişi bir seçeneğe bir kez oy verir (çoklu ankette birden çok seçeneğe)
        baglanti.execute("""
            CREATE TABLE IF NOT EXISTS anket_oylari (
                anket_id     INTEGER NOT NULL REFERENCES anketler(id),
                secenek_id   INTEGER NOT NULL REFERENCES anket_secenekleri(id),
                kullanici_id INTEGER NOT NULL REFERENCES kullanicilar(id),
                PRIMARY KEY (secenek_id, kullanici_id)
            )
        """)
        # Resimler: sohbette paylaşılan resimler, küçültülmüş JPEG olarak veritabanında saklanır.
        # (Ücretsiz Render'da diske yazılan dosyalar yeniden başlatınca silindiği için.)
        # SQLite'ta ikili veri türü BLOB, PostgreSQL'de BYTEA.
        baglanti.execute(f"""
            CREATE TABLE IF NOT EXISTS resimler (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                sahip_id INTEGER NOT NULL REFERENCES kullanicilar(id),
                veri    {'BYTEA' if POSTGRES else 'BLOB'} NOT NULL,
                tur     TEXT NOT NULL,
                boyut   INTEGER NOT NULL,
                zaman   TEXT NOT NULL
            )
        """)
        sutun_yoksa_ekle(baglanti, "mesajlar", "anket_id", "INTEGER")
        sutun_yoksa_ekle(baglanti, "mesajlar", "resim_id", "INTEGER")

        if POSTGRES:
            # SQLite'taki COLLATE NOCASE'in yerine: "Ali" ile "ali" aynı ad sayılsın.
            # LOWER(...) üzerine UNIQUE indeks: küçük harfe çevrilmiş halleri aynı olamaz.
            baglanti.execute("""CREATE UNIQUE INDEX IF NOT EXISTS kullanici_adi_buyuk_kucuk
                                ON kullanicilar (LOWER(kullanici_adi))""")

        baglanti.commit()      # Değişiklikleri kalıcı hale getir
    finally:
        baglanti.close()       # Hata olsa bile bağlantıyı kapat


def sutun_yoksa_ekle(baglanti, tablo, sutun, tanim):
    """
    Tabloda o sütun yoksa ALTER TABLE ile ekler.
    PRAGMA table_info: tablonun sütunlarını listeler.
    (Tablo ve sütun adları bizim kodumuzdan geliyor, kullanıcıdan değil;
    bu yüzden burada "?" yerine metne yazmak güvenli.)
    PostgreSQL bunu tek komutla yapabiliyor: ADD COLUMN IF NOT EXISTS.
    """
    if POSTGRES:
        baglanti.execute(f"ALTER TABLE {tablo} ADD COLUMN IF NOT EXISTS {sutun} {tanim}")
        return
    sutunlar = [satir["name"] for satir in baglanti.execute(f"PRAGMA table_info({tablo})")]
    if sutun not in sutunlar:
        baglanti.execute(f"ALTER TABLE {tablo} ADD COLUMN {sutun} {tanim}")


# ---------------------------------------------------------------------------
# 2) YAPAY ZEKÂ CEVABINI PARÇALARA AYIRMA
# ---------------------------------------------------------------------------

def cevabi_parcala(metin):
    """
    Yapay zekânın cevabını üç parçaya ayırır:
      - giris : ilk "### Adım" başlığından önceki kısa paragraf
      - adimlar: her "### Adım N: ..." başlığı ve altındaki maddeler
      - dikkat: "## Dikkat et" başlığı ve sonrası (motivasyon cümlesi dahil)

    TALIMAT'ta yapay zekâdan tam olarak bu biçimde cevap vermesini istemiştik,
    bu yüzden satır satır bakıp başlıklara göre ayırabiliyoruz.
    """
    giris_satirlari = []
    dikkat_satirlari = []
    adimlar = []
    bolum = "giris"            # Şu an hangi bölümün içindeyiz?

    for satir in metin.splitlines():
        if satir.startswith("### "):                     # Yeni bir adım başladı
            baslik = satir[4:].strip().strip("*").strip()  # "**" işaretlerini temizle
            adimlar.append({"baslik": baslik, "satirlar": []})
            bolum = "adim"
        elif satir.startswith("## "):                    # "Dikkat et" bölümü başladı
            bolum = "dikkat"
            dikkat_satirlari.append(satir)
        elif bolum == "giris":
            giris_satirlari.append(satir)
        elif bolum == "adim":
            adimlar[-1]["satirlar"].append(satir)
        else:
            dikkat_satirlari.append(satir)

    return {
        "giris": "\n".join(giris_satirlari).strip(),
        "adimlar": [(a["baslik"], "\n".join(a["satirlar"]).strip()) for a in adimlar],
        "dikkat": "\n".join(dikkat_satirlari).strip(),
    }


# ---------------------------------------------------------------------------
# 3) KAYDETME, OKUMA, GÜNCELLEME (SQL sorguları burada)
# ---------------------------------------------------------------------------

def yol_haritasi_ekle(proje, bilgi, cevap, dosya_yolu=None, kullanici_id=None, sinif_id=None):
    """
    Yeni bir yol haritasını ve adımlarını, sahibi olan kullanıcıyla birlikte kaydeder.
    sinif_id: Öğretmenin verdiği sınıf projesi için çıkarıldıysa o sınıf.
    Yeni yol haritasının id numarasını döndürür.
    """
    parcalar = cevabi_parcala(cevap)
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    baglanti = baglan()
    try:
        # INSERT: tabloya yeni satır ekler.
        # "?" işaretleri yer tutucudur; değerleri sqlite3 güvenli şekilde yerleştirir.
        # Değerleri metnin içine kendimiz yapıştırmayız, yoksa "SQL enjeksiyonu"
        # denen güvenlik açığı oluşur.
        # ekle(): INSERT yapar ve az önce eklenen satırın id'sini döndürür
        harita_id = baglanti.ekle(
            """INSERT INTO yol_haritalari
                   (proje, bilgi, giris, dikkat, ham_cevap, dosya_yolu, olusturma_zamani, kullanici_id,
                    sinif_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (proje, bilgi, parcalar["giris"], parcalar["dikkat"], cevap, dosya_yolu, zaman,
             kullanici_id, sinif_id),
        )

        # Her adımı, yol haritasının id'si ile birlikte adimlar tablosuna ekle
        for sira, (baslik, icerik) in enumerate(parcalar["adimlar"], start=1):
            baglanti.execute(
                """INSERT INTO adimlar (yol_haritasi_id, sira, baslik, icerik)
                   VALUES (?, ?, ?, ?)""",
                (harita_id, sira, baslik, icerik),
            )

        baglanti.commit()
        return harita_id
    finally:
        baglanti.close()


def yol_haritasi_getir(harita_id, kullanici_id):
    """
    Tek bir yol haritasını ve adımlarını getirir.
    Yol haritası yoksa ya da BAŞKA bir kullanıcınınsa (None, []) döndürür.
    """
    baglanti = baglan()
    try:
        # SELECT ... WHERE: koşula uyan satırı okur.
        # "AND kullanici_id = ?" sayesinde kimse adres çubuğuna başka bir sayı
        # yazarak başkasının yol haritasını açamaz.
        harita = baglanti.execute(
            "SELECT * FROM yol_haritalari WHERE id = ? AND kullanici_id = ?",
            (harita_id, kullanici_id),
        ).fetchone()
        if harita is None:
            return None, []

        # ORDER BY: adımları sıra numarasına göre dizer
        adimlar = baglanti.execute(
            "SELECT * FROM adimlar WHERE yol_haritasi_id = ? ORDER BY sira", (harita_id,)
        ).fetchall()
        return harita, adimlar
    finally:
        baglanti.close()


def tum_yol_haritalari(kullanici_id, ara="", durum="hepsi"):
    """
    Geçmiş sayfası için kullanıcının yol haritalarını, en yeniden eskiye doğru getirir.
    Her satırda ayrıca toplam adım sayısı ve tamamlanan adım sayısı bulunur.

    ara  : proje anlatımında geçmesi gereken kelime (boşsa hepsi)
    durum: "hepsi", "devam" (bitmemiş) ya da "bitti" (bütün adımlar tamam)
    """
    # Sorguyu parça parça kuruyoruz; değerleri yine "?" ile güvenli şekilde veriyoruz.
    sorgu = """
        SELECT y.id, y.proje, y.olusturma_zamani, y.degerlendirme_puan, y.degerlendirme_goruldu,
               COUNT(a.id)                    AS toplam_adim,
               COALESCE(SUM(a.tamamlandi), 0) AS tamamlanan_adim,
               (SELECT COUNT(*) FROM ogretmen_yorumlari o
                 JOIN adimlar a2 ON a2.id = o.adim_id
                 WHERE a2.yol_haritasi_id = y.id) AS yorum_sayisi,
               (SELECT COUNT(*) FROM ogretmen_yorumlari o
                 JOIN adimlar a2 ON a2.id = o.adim_id
                 WHERE a2.yol_haritasi_id = y.id AND o.okundu = 0) AS yeni_yorum_sayisi
        FROM yol_haritalari AS y
        LEFT JOIN adimlar AS a ON a.yol_haritasi_id = y.id
        WHERE y.kullanici_id = ?
    """
    degerler = [kullanici_id]

    # WHERE: satırları gruplamadan ÖNCE süzer.
    # LIKE '%kelime%': içinde o kelime geçen metinleri bulur.
    # LOWER: İki tarafı da küçük harfe çeviriyoruz; PostgreSQL'in LIKE'ı büyük/küçük harfe duyarlı.
    if ara:
        sorgu += " AND LOWER(y.proje) LIKE LOWER(?)"
        degerler.append(f"%{ara}%")

    sorgu += " GROUP BY y.id"

    # HAVING: gruplamadan SONRA süzer; COUNT/SUM sonuçlarına göre süzmek için gerekir.
    if durum == "bitti":
        sorgu += " HAVING COUNT(a.id) > 0 AND SUM(a.tamamlandi) = COUNT(a.id)"
    elif durum == "devam":
        sorgu += " HAVING COUNT(a.id) = 0 OR SUM(a.tamamlandi) < COUNT(a.id)"

    sorgu += " ORDER BY y.id DESC"

    baglanti = baglan()
    try:
        # LEFT JOIN : iki tabloyu yol_haritasi_id üzerinden birleştirir
        #             (adımı olmayan yol haritaları da listede kalsın diye LEFT).
        # COUNT/SUM : her yol haritası için adımları sayar ve toplar.
        # GROUP BY  : bu sayımı her yol haritası için ayrı ayrı yapar.
        return baglanti.execute(sorgu, degerler).fetchall()
    finally:
        baglanti.close()


def istatistikler(kullanici_id):
    """Geçmiş sayfasının üstündeki özet sayılar: kaç yol haritası, adım ve ipucu var."""
    baglanti = baglan()
    try:
        # Alt sorgular: her parantez içindeki SELECT ayrı bir sayı döndürür.
        # Hepsi sadece bu kullanıcının yol haritalarını sayar.
        return baglanti.execute("""
            SELECT (SELECT COUNT(*) FROM yol_haritalari WHERE kullanici_id = :k) AS harita_sayisi,
                   (SELECT COUNT(*) FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = :k AND a.tamamlandi = 1)              AS biten_adim,
                   (SELECT COUNT(*) FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = :k)                                   AS toplam_adim,
                   (SELECT COUNT(*) FROM ipuclari i
                     JOIN adimlar a ON a.id = i.adim_id
                     JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = :k)                                   AS ipucu_sayisi
        """, {"k": kullanici_id}).fetchone()   # ":k" isimli yer tutucu; 4 yerde aynı değer
    finally:
        baglanti.close()


def yol_haritasi_sil(harita_id, kullanici_id):
    """
    Bir yol haritasını, adımlarını ve ipuçlarını siler (sadece sahibi silebilir).
    Sıra önemli: önce "çocuk" kayıtlar (ipuçları, adımlar), en son "ebeveyn"
    (yol haritası) silinir. Yoksa yabancı anahtar kuralı silmeye izin vermez.
    Üç silme işlemi tek bir "işlem" (transaction) içindedir: commit'ten önce
    bir hata olursa hiçbiri uygulanmaz, veritabanı yarım kalmaz.
    """
    baglanti = baglan()
    try:
        # Önce bu yol haritası gerçekten bu kullanıcının mı, kontrol et
        sahibi_mi = baglanti.execute(
            "SELECT 1 FROM yol_haritalari WHERE id = ? AND kullanici_id = ?",
            (harita_id, kullanici_id),
        ).fetchone()
        if sahibi_mi is None:
            return False

        baglanti.execute("""
            DELETE FROM ipuclari
            WHERE adim_id IN (SELECT id FROM adimlar WHERE yol_haritasi_id = ?)
        """, (harita_id,))
        # Commit'ler ve öğretmen yorumları adımlara bağlı olduğu için adımlardan ÖNCE silinmeli
        baglanti.execute("DELETE FROM commitler WHERE yol_haritasi_id = ?", (harita_id,))
        baglanti.execute("""
            DELETE FROM ogretmen_yorumlari
            WHERE adim_id IN (SELECT id FROM adimlar WHERE yol_haritasi_id = ?)
        """, (harita_id,))
        baglanti.execute("""
            DELETE FROM kod_incelemeleri
            WHERE adim_id IN (SELECT id FROM adimlar WHERE yol_haritasi_id = ?)
        """, (harita_id,))
        baglanti.execute("""
            DELETE FROM koc_sorulari
            WHERE adim_id IN (SELECT id FROM adimlar WHERE yol_haritasi_id = ?)
        """, (harita_id,))
        baglanti.execute("""
            DELETE FROM ogretmen_sorulari
            WHERE adim_id IN (SELECT id FROM adimlar WHERE yol_haritasi_id = ?)
        """, (harita_id,))
        baglanti.execute("DELETE FROM quizler WHERE adim_id IN (SELECT id FROM adimlar WHERE yol_haritasi_id = ?)",
                         (harita_id,))
        baglanti.execute("DELETE FROM adimlar WHERE yol_haritasi_id = ?", (harita_id,))
        imlec = baglanti.execute("DELETE FROM yol_haritalari WHERE id = ?", (harita_id,))
        baglanti.commit()
        return imlec.rowcount > 0          # Gerçekten bir şey silindi mi?
    finally:
        baglanti.close()


def adim_getir(adim_id, kullanici_id):
    """
    Tek bir adımı, ait olduğu yol haritasının proje anlatımıyla birlikte getirir.
    JOIN ile iki tablodan aynı anda bilgi alıyoruz.
    Adım yoksa ya da başka bir kullanıcınınsa None döner.
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT a.*, y.proje, y.bilgi
            FROM adimlar AS a
            JOIN yol_haritalari AS y ON y.id = a.yol_haritasi_id
            WHERE a.id = ? AND y.kullanici_id = ?
        """, (adim_id, kullanici_id)).fetchone()
    finally:
        baglanti.close()


def not_kaydet(adim_id, not_metni):
    """Öğrencinin bir adıma yazdığı notu kaydeder (boş metin notu siler)."""
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE adimlar SET not_metni = ? WHERE id = ?",
                         (not_metni or None, adim_id))
        baglanti.commit()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 4) İPUÇLARI
# ---------------------------------------------------------------------------

def ipuclarini_getir(adim_id):
    """Bir adım için verilmiş ipuçlarını, verildikleri sırayla getirir."""
    baglanti = baglan()
    try:
        return baglanti.execute(
            "SELECT * FROM ipuclari WHERE adim_id = ? ORDER BY seviye", (adim_id,)
        ).fetchall()
    finally:
        baglanti.close()


def yol_haritasinin_ipuclari(harita_id):
    """
    Bir yol haritasındaki bütün ipuçlarını tek sorguda getirir ve
    {adim_id: [ipucu, ipucu, ...]} şeklinde bir sözlüğe çevirir.
    (Her adım için ayrı ayrı sorgu atmaktan daha hızlıdır.)
    """
    baglanti = baglan()
    try:
        satirlar = baglanti.execute("""
            SELECT i.*
            FROM ipuclari AS i
            JOIN adimlar AS a ON a.id = i.adim_id
            WHERE a.yol_haritasi_id = ?
            ORDER BY i.adim_id, i.seviye
        """, (harita_id,)).fetchall()
    finally:
        baglanti.close()

    sozluk = {}
    for satir in satirlar:
        sozluk.setdefault(satir["adim_id"], []).append(satir)
    return sozluk


def ipucu_ekle(adim_id, seviye, soru, cevap):
    """Yeni bir ipucunu kaydeder."""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        baglanti.execute(
            """INSERT INTO ipuclari (adim_id, seviye, soru, cevap, olusturma_zamani)
               VALUES (?, ?, ?, ?, ?)""",
            (adim_id, seviye, soru or None, cevap, zaman),
        )
        baglanti.commit()
    finally:
        baglanti.close()


def adim_durumunu_degistir(adim_id, tamamlandi):
    """
    Bir adımı "tamamlandı" ya da "tamamlanmadı" olarak işaretler.
    Adımın ait olduğu yol haritasının id'sini döndürür (adım yoksa None).
    """
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if tamamlandi else None

    baglanti = baglan()
    try:
        # UPDATE: var olan bir satırın sütunlarını değiştirir
        baglanti.execute(
            "UPDATE adimlar SET tamamlandi = ?, tamamlanma_zamani = ? WHERE id = ?",
            (1 if tamamlandi else 0, zaman, adim_id),
        )
        baglanti.commit()

        satir = baglanti.execute(
            "SELECT yol_haritasi_id FROM adimlar WHERE id = ?", (adim_id,)
        ).fetchone()
        return satir["yol_haritasi_id"] if satir else None
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 5) KULLANICILAR (kayıt ve giriş)
# ---------------------------------------------------------------------------

def kullanici_ekle(kullanici_adi, sifre, rol="ogrenci"):
    """
    Yeni kullanıcı kaydeder ve id'sini döndürür.
    rol: "ogrenci" ya da "ogretmen".
    Bu kullanıcı adı zaten alınmışsa None döndürür.
    """
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sifre_hash = generate_password_hash(sifre)    # Şifrenin kendisi değil, hash'i saklanır

    baglanti = baglan()
    try:
        kullanici_id = baglanti.ekle(
            """INSERT INTO kullanicilar (kullanici_adi, sifre_hash, olusturma_zamani, rol)
               VALUES (?, ?, ?, ?)""",
            (kullanici_adi, sifre_hash, zaman, rol),
        )
        baglanti.commit()
        return kullanici_id
    except BUTUNLUK_HATASI:
        # UNIQUE kuralı çiğnendi: bu ad zaten var
        return None
    finally:
        baglanti.close()


def kullanici_dogrula(kullanici_adi, sifre):
    """
    Kullanıcı adı ve şifre doğruysa kullanıcının satırını, değilse None döndürür.
    check_password_hash: girilen şifrenin hash'ini kayıtlı hash ile karşılaştırır.
    """
    baglanti = baglan()
    try:
        kullanici = baglanti.execute(
            # LOWER: "Ali" ile girmeye çalışan "ali" hesabına da girebilsin (iki veritabanında da çalışır)
            "SELECT * FROM kullanicilar WHERE LOWER(kullanici_adi) = LOWER(?)", (kullanici_adi,)
        ).fetchone()
    finally:
        baglanti.close()

    if kullanici and check_password_hash(kullanici["sifre_hash"], sifre):
        return kullanici
    return None


def kullanici_getir(kullanici_id):
    """id'si verilen kullanıcıyı getirir (yoksa None)."""
    baglanti = baglan()
    try:
        return baglanti.execute(
            "SELECT id, kullanici_adi, rol, gecici_sifre, son_giris FROM kullanicilar WHERE id = ?", (kullanici_id,)
        ).fetchone()
    finally:
        baglanti.close()


def sahipsiz_kayitlari_aktar(kullanici_id):
    """
    Kullanıcı girişi eklenmeden ÖNCE kaydedilmiş yol haritalarının sahibi yoktur
    (kullanici_id boştur, yani NULL). Bunları verilen kullanıcıya aktarır ve
    kaç kayıt aktarıldığını döndürür. Uygulama bunu sadece İLK kayıt olan kişi
    için çağırır; böylece eski çalışmalar kaybolmaz.
    """
    baglanti = baglan()
    try:
        # NULL ile karşılaştırma "= NULL" ile değil "IS NULL" ile yapılır
        imlec = baglanti.execute(
            "UPDATE yol_haritalari SET kullanici_id = ? WHERE kullanici_id IS NULL",
            (kullanici_id,),
        )
        baglanti.commit()
        return imlec.rowcount
    finally:
        baglanti.close()


def kullanici_sayisi():
    """Kaç kullanıcı kayıtlı olduğunu döndürür."""
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT COUNT(*) FROM kullanicilar").fetchone()[0]
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 6) SINIFLAR VE ÖĞRETMEN PANELİ
# ---------------------------------------------------------------------------

# Katılım kodlarında karıştırılabilecek karakterler yok (0/O, 1/I gibi)
KOD_KARAKTERLERI = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def sinif_olustur(ogretmen_id, ad):
    """
    Yeni sınıf açar, rastgele 6 karakterlik bir katılım kodu üretir.
    Kod tesadüfen başka bir sınıfınkiyle aynı çıkarsa (UNIQUE hatası) yenisini dener.
    Sınıfın id'sini döndürür.
    """
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        while True:
            # secrets: tahmin edilmesi zor rastgele değerler üretir
            kod = "".join(secrets.choice(KOD_KARAKTERLERI) for _ in range(6))
            try:
                sinif_id = baglanti.ekle(
                    """INSERT INTO siniflar (ad, katilim_kodu, ogretmen_id, olusturma_zamani)
                       VALUES (?, ?, ?, ?)""",
                    (ad, kod, ogretmen_id, zaman),
                )
                baglanti.commit()
                return sinif_id
            except BUTUNLUK_HATASI:
                # Kod çakıştı. Başarısız işlemi geri al (PostgreSQL hatadan sonra
                # rollback yapılmadan yeni komut kabul etmez), döngü yeni kod dener.
                baglanti.rollback()
                continue
    finally:
        baglanti.close()


def ogretmenin_siniflari(ogretmen_id):
    """Öğretmenin sınıflarını, her sınıftaki öğrenci sayısıyla birlikte getirir."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT s.*, COUNT(u.ogrenci_id) AS ogrenci_sayisi
            FROM siniflar AS s
            LEFT JOIN sinif_uyeleri AS u ON u.sinif_id = s.id
            WHERE s.ogretmen_id = ?
            GROUP BY s.id
            ORDER BY s.id DESC
        """, (ogretmen_id,)).fetchall()
    finally:
        baglanti.close()


def sinif_getir(sinif_id, ogretmen_id):
    """Sınıfı getirir; sınıf yoksa ya da bu öğretmenin değilse None."""
    baglanti = baglan()
    try:
        return baglanti.execute(
            "SELECT * FROM siniflar WHERE id = ? AND ogretmen_id = ?", (sinif_id, ogretmen_id)
        ).fetchone()
    finally:
        baglanti.close()


def sinif_sil(sinif_id, ogretmen_id):
    """
    Sınıfı ve üyelik kayıtlarını siler. Öğrencilerin yol haritalarına DOKUNMAZ;
    sadece "kim hangi sınıfta" bilgisi silinir.
    """
    baglanti = baglan()
    try:
        if baglanti.execute("SELECT 1 FROM siniflar WHERE id = ? AND ogretmen_id = ?",
                            (sinif_id, ogretmen_id)).fetchone() is None:
            return False
        baglanti.execute("DELETE FROM sinif_uyeleri WHERE sinif_id = ?", (sinif_id,))
        baglanti.execute("DELETE FROM duyurular WHERE sinif_id = ?", (sinif_id,))
        baglanti.execute("DELETE FROM sikayetler WHERE mesaj_id IN (SELECT id FROM mesajlar WHERE sinif_id = ?)",
                         (sinif_id,))
        gruplari = "SELECT id FROM gruplar WHERE sinif_id = ?"
        baglanti.execute(f"DELETE FROM sikayetler WHERE mesaj_id IN (SELECT id FROM mesajlar WHERE grup_id IN ({gruplari}))",
                         (sinif_id,))
        for tablo in ("mesajlar", "gorevler", "grup_uyeleri", "grup_okuma", "grup_davetleri"):
            baglanti.execute(f"DELETE FROM {tablo} WHERE grup_id IN ({gruplari})", (sinif_id,))
        baglanti.execute("DELETE FROM gruplar WHERE sinif_id = ?", (sinif_id,))
        baglanti.execute("DELETE FROM teslimler WHERE odev_id IN (SELECT id FROM odevler WHERE sinif_id = ?)",
                         (sinif_id,))
        baglanti.execute("DELETE FROM odevler WHERE sinif_id = ?", (sinif_id,))
        baglanti.execute("DELETE FROM mesajlar WHERE sinif_id = ?", (sinif_id,))        # Sınıf sohbeti
        _sahipsizleri_temizle(baglanti)                    # Silinen mesajların anketleri ve resimleri
        baglanti.execute("DELETE FROM sohbet_okuma WHERE sinif_id = ?", (sinif_id,))
        # Sınıf projesi için çıkarılmış yol haritaları öğrencide kalır, sadece sınıf bağı kopar
        baglanti.execute("UPDATE yol_haritalari SET sinif_id = NULL WHERE sinif_id = ?", (sinif_id,))
        baglanti.execute("DELETE FROM siniflar WHERE id = ?", (sinif_id,))
        baglanti.commit()
        return True
    finally:
        baglanti.close()


def sinifa_katil(ogrenci_id, kod):
    """
    Öğrenciyi, kodu verilen sınıfa ekler.
    Döndürdüğü değer: ("tamam", sinif) / ("zaten", sinif) / ("yok", None)
    """
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        sinif = baglanti.execute(
            "SELECT * FROM siniflar WHERE katilim_kodu = ?", (kod,)
        ).fetchone()
        if sinif is None:
            return "yok", None
        try:
            baglanti.execute(
                "INSERT INTO sinif_uyeleri (sinif_id, ogrenci_id, katilma_zamani) VALUES (?, ?, ?)",
                (sinif["id"], ogrenci_id, zaman),
            )
            baglanti.commit()
            return "tamam", sinif
        except BUTUNLUK_HATASI:
            # Bileşik birincil anahtar: bu öğrenci bu sınıfta zaten var
            return "zaten", sinif
    finally:
        baglanti.close()


def siniftan_ayril(ogrenci_id, sinif_id):
    """Öğrenciyi sınıftan (ve o sınıfın gruplarından) çıkarır."""
    baglanti = baglan()
    try:
        baglanti.execute("""DELETE FROM grup_uyeleri WHERE ogrenci_id = ?
                            AND grup_id IN (SELECT id FROM gruplar WHERE sinif_id = ?)""", (ogrenci_id, sinif_id))
        baglanti.execute("""DELETE FROM grup_davetleri WHERE davet_edilen_id = ?
                            AND grup_id IN (SELECT id FROM gruplar WHERE sinif_id = ?)""", (ogrenci_id, sinif_id))
        _yoneticiligi_devret(baglanti, ogrenci_id, sinif_id)    # Kurduğu sohbet grupları başkasına geçer
        baglanti.commit()
    finally:
        baglanti.close()
    return _siniftan_ayril(ogrenci_id, sinif_id)


def _siniftan_ayril(ogrenci_id, sinif_id):
    """Öğrenciyi sınıftan çıkarır."""
    baglanti = baglan()
    try:
        baglanti.execute("DELETE FROM sinif_uyeleri WHERE sinif_id = ? AND ogrenci_id = ?",
                         (sinif_id, ogrenci_id))
        baglanti.commit()
    finally:
        baglanti.close()


def ogrencinin_siniflari(ogrenci_id):
    """Öğrencinin katıldığı sınıfları, öğretmenin adıyla birlikte getirir."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT s.id, s.ad, s.proje, s.sablon_id, k.kullanici_adi AS ogretmen_adi, u.katilma_zamani,
                   -- Bu sınıfın projesi için çıkardığı en son yol haritası (yoksa boş)
                   (SELECT MAX(y.id) FROM yol_haritalari y
                     WHERE y.kullanici_id = u.ogrenci_id AND y.sinif_id = s.id) AS proje_harita_id
            FROM sinif_uyeleri AS u
            JOIN siniflar     AS s ON s.id = u.sinif_id
            JOIN kullanicilar AS k ON k.id = s.ogretmen_id
            WHERE u.ogrenci_id = ?
            ORDER BY u.katilma_zamani DESC
        """, (ogrenci_id,)).fetchall()
    finally:
        baglanti.close()


def sinif_ozeti(sinif_id):
    """
    Öğretmen paneli için: sınıftaki her öğrencinin ilerleme özeti.
    İLİŞKİLİ ALT SORGU (correlated subquery): Parantez içindeki her SELECT,
    dıştaki sorgunun o anki satırındaki öğrenci (k.id) için ayrı ayrı çalışır.
    """
    baglanti = baglan()
    try:
        # f-string: {BUYUGU} yerine SQLite'ta MAX, PostgreSQL'de GREATEST yazılır
        # Son 7 günün başı (bugün dahil 7 gün): yapay zekâ kullanımını saymak için
        hafta_basi = (datetime.now() - timedelta(days=6)).strftime("%Y-%m-%d")
        bugun = datetime.now().strftime("%Y-%m-%d")
        return baglanti.execute(f"""
            SELECT k.id, k.kullanici_adi, u.katilma_zamani, k.son_giris,
                   -- Son 7 günde yapay zekâya gönderdiği istek sayısı (yz_kullanimi tablosundan)
                   (SELECT COALESCE(SUM(z.sayi), 0) FROM yz_kullanimi z
                     WHERE z.kullanici_id = k.id AND z.gun >= ?)        AS yz_hafta,
                   -- Sınıf projesi: bu sınıfın projesi için çıkardığı en son yol haritası ve ilerlemesi
                   (SELECT MAX(y.id) FROM yol_haritalari y
                     WHERE y.kullanici_id = k.id AND y.sinif_id = u.sinif_id)  AS proje_harita_id,
                   (SELECT COUNT(*) FROM adimlar a WHERE a.yol_haritasi_id =
                      (SELECT MAX(y.id) FROM yol_haritalari y
                        WHERE y.kullanici_id = k.id AND y.sinif_id = u.sinif_id)) AS proje_toplam,
                   (SELECT COUNT(*) FROM adimlar a WHERE a.tamamlandi = 1 AND a.yol_haritasi_id =
                      (SELECT MAX(y.id) FROM yol_haritalari y
                        WHERE y.kullanici_id = k.id AND y.sinif_id = u.sinif_id)) AS proje_biten,
                   (SELECT y.degerlendirme_puan FROM yol_haritalari y WHERE y.id =
                      (SELECT MAX(y2.id) FROM yol_haritalari y2
                        WHERE y2.kullanici_id = k.id AND y2.sinif_id = u.sinif_id)) AS proje_puan,
                   -- Hedef tarihi geçmiş ama bitmemiş adım sayısı
                   (SELECT COUNT(*) FROM adimlar a
                     JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = k.id AND a.tamamlandi = 0
                       AND a.hedef_tarih < ?)                           AS geciken_adim,
                   (SELECT COUNT(*) FROM yol_haritalari y
                     WHERE y.kullanici_id = k.id)                       AS harita_sayisi,
                   (SELECT COUNT(*) FROM adimlar a
                     JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = k.id)                       AS toplam_adim,
                   (SELECT COUNT(*) FROM adimlar a
                     JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = k.id AND a.tamamlandi = 1)  AS biten_adim,
                   (SELECT COUNT(*) FROM ipuclari i
                     JOIN adimlar a ON a.id = i.adim_id
                     JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = k.id)                       AS ipucu_sayisi,
                   (SELECT COUNT(*) FROM commitler c
                     JOIN yol_haritalari y ON y.id = c.yol_haritasi_id
                     WHERE y.kullanici_id = k.id)                       AS commit_sayisi,
                   -- Son etkinlik: en son yol haritası, tamamlanan adım ya da ipucu zamanı.
                   -- MAX(a, b, c) üçünden en büyüğünü verir; boş (NULL) olanlar '' sayılır.
                   {BUYUGU}(
                     COALESCE((SELECT MAX(y.olusturma_zamani) FROM yol_haritalari y
                               WHERE y.kullanici_id = k.id), ''),
                     COALESCE((SELECT MAX(a.tamamlanma_zamani) FROM adimlar a
                               JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                               WHERE y.kullanici_id = k.id), ''),
                     COALESCE((SELECT MAX(i.olusturma_zamani) FROM ipuclari i
                               JOIN adimlar a ON a.id = i.adim_id
                               JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                               WHERE y.kullanici_id = k.id), ''),
                     COALESCE((SELECT MAX(c.tarih) FROM commitler c
                               JOIN yol_haritalari y ON y.id = c.yol_haritasi_id
                               WHERE y.kullanici_id = k.id), '')
                   )                                                    AS son_etkinlik
            FROM sinif_uyeleri AS u
            JOIN kullanicilar  AS k ON k.id = u.ogrenci_id
            WHERE u.sinif_id = ?
            ORDER BY k.kullanici_adi
        """, (hafta_basi, bugun, sinif_id)).fetchall()   # Sıra önemli: ? işaretleri soldan sağa doldurulur
    finally:
        baglanti.close()


def takilan_adimlar(sinif_id, en_az_ipucu=2):
    """
    Öğretmenin dikkat etmesi gereken yerler: sınıftaki öğrencilerin henüz
    BİTİRMEDİĞİ ve en az 2 ipucu aldığı adımlar. En çok ipucu alınan en üstte.
    HAVING: ipucu sayısına (COUNT sonucuna) göre süzmek için.
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT k.id AS ogrenci_id, k.kullanici_adi, y.id AS harita_id,
                   a.id AS adim_id, a.baslik, a.sira, y.proje,
                   COUNT(i.id)             AS ipucu_sayisi,
                   MAX(i.olusturma_zamani) AS son_ipucu
            FROM sinif_uyeleri AS u
            JOIN kullanicilar   AS k ON k.id = u.ogrenci_id
            JOIN yol_haritalari AS y ON y.kullanici_id = k.id
            JOIN adimlar        AS a ON a.yol_haritasi_id = y.id
            JOIN ipuclari       AS i ON i.adim_id = a.id
            WHERE u.sinif_id = ? AND a.tamamlandi = 0
            -- Seçilen sütunların tabloları (k, y, a) GROUP BY'da olmalı; PostgreSQL bunu şart koşar
            GROUP BY a.id, k.id, y.id
            HAVING COUNT(i.id) >= ?
            ORDER BY ipucu_sayisi DESC, son_ipucu DESC
        """, (sinif_id, en_az_ipucu)).fetchall()
    finally:
        baglanti.close()


def sinif_etkinlikleri(sinif_id, baslangic):
    """
    Sınıf istatistikleri için: hangi öğrenci hangi gün çalışmış?
    baslangic: '2026-10-28' gibi bir gün; bu günden önceki kayıtlar alınmaz.
    {(ogrenci_id, '2026-11-10'), ...} şeklinde bir KÜME döndürür.

    calisma_gunleri() ile aynı fikir (UNION ALL ile beş etkinlik türünü birleştir),
    farkı: tek öğrenci yerine sınıftaki BÜTÜN öğrenciler, ve öğrenci id'si de geliyor.
    DISTINCT: aynı öğrenci aynı gün 5 iş yaptıysa bile tek satır gelsin
    (grafikte "o gün kaç FARKLI öğrenci çalıştı?" sorusunu soruyoruz).
    IN (alt sorgu): sadece bu sınıfın üyesi olan öğrenciler.
    """
    baglanti = baglan()
    try:
        satirlar = baglanti.execute("""
            SELECT DISTINCT ogrenci_id, gun FROM (
                SELECT y.kullanici_id AS ogrenci_id, SUBSTR(y.olusturma_zamani, 1, 10) AS gun
                  FROM yol_haritalari y
                UNION ALL
                SELECT y.kullanici_id, SUBSTR(a.tamamlanma_zamani, 1, 10) FROM adimlar a
                  JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                 WHERE a.tamamlanma_zamani IS NOT NULL
                UNION ALL
                SELECT y.kullanici_id, SUBSTR(i.olusturma_zamani, 1, 10) FROM ipuclari i
                  JOIN adimlar a ON a.id = i.adim_id JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                UNION ALL
                SELECT y.kullanici_id, SUBSTR(s.olusturma_zamani, 1, 10) FROM koc_sorulari s
                  JOIN adimlar a ON a.id = s.adim_id JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                UNION ALL
                SELECT y.kullanici_id, SUBSTR(ki.olusturma_zamani, 1, 10) FROM kod_incelemeleri ki
                  JOIN adimlar a ON a.id = ki.adim_id JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
            ) AS etkinlikler
            WHERE ogrenci_id IN (SELECT ogrenci_id FROM sinif_uyeleri WHERE sinif_id = ?)
              AND gun >= ?
        """, (sinif_id, baslangic)).fetchall()
    finally:
        baglanti.close()
    return {(satir["ogrenci_id"], satir["gun"]) for satir in satirlar}


# ---------------------------------------------------------------------------
# 7) GITHUB COMMIT'LERİ
# ---------------------------------------------------------------------------

def github_depo_ayarla(harita_id, kullanici_id, depo):
    """
    Yol haritasına bir GitHub deposu bağlar (depo=None ise bağlantıyı kaldırır).
    Depo değişirse eski deponun commit'leri silinir, çünkü artık geçerli değiller.
    Sadece yol haritasının sahibi yapabilir; başarılıysa True döner.
    """
    baglanti = baglan()
    try:
        harita = baglanti.execute(
            "SELECT github_depo FROM yol_haritalari WHERE id = ? AND kullanici_id = ?",
            (harita_id, kullanici_id),
        ).fetchone()
        if harita is None:
            return False
        if harita["github_depo"] != depo:
            baglanti.execute("DELETE FROM commitler WHERE yol_haritasi_id = ?", (harita_id,))
            baglanti.execute(
                "UPDATE yol_haritalari SET github_depo = ?, github_son_kontrol = NULL WHERE id = ?",
                (depo, harita_id),
            )
        baglanti.commit()
        return True
    finally:
        baglanti.close()


def commitleri_kaydet(harita_id, commitler, adim_numarasi_bul):
    """
    GitHub'dan gelen commit'leri kaydeder; yeni eklenen commit sayısını döndürür.
    adim_numarasi_bul: commit mesajından adım numarasını çıkaran fonksiyon
    (github_takip.py'den gelir; fonksiyonu parametre olarak alıyoruz).

    ON CONFLICT DO NOTHING: UNIQUE kuralına takılan (zaten kayıtlı) commit'i hata
    vermeden atlar. Böylece "Yenile"ye her basışta sadece yeniler eklenir.
    (SQLite'ın "INSERT OR IGNORE" yazımı PostgreSQL'de yok; bu yazım ikisinde de çalışır.)
    """
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        # Adım sıra numarası -> adım id'si eşlemesi: {1: 15, 2: 16, ...}
        sira_id = {satir["sira"]: satir["id"] for satir in baglanti.execute(
            "SELECT id, sira FROM adimlar WHERE yol_haritasi_id = ?", (harita_id,))}

        yeni = 0
        for c in commitler:
            adim_id = sira_id.get(adim_numarasi_bul(c["mesaj"]))   # Yoksa None
            imlec = baglanti.execute(
                """INSERT INTO commitler
                       (yol_haritasi_id, adim_id, sha, mesaj, yazar, tarih, url)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT DO NOTHING""",
                (harita_id, adim_id, c["sha"], c["mesaj"], c["yazar"], c["tarih"], c["url"]),
            )
            yeni += imlec.rowcount          # Eklendiyse 1, atlandıysa 0

        baglanti.execute("UPDATE yol_haritalari SET github_son_kontrol = ? WHERE id = ?",
                         (zaman, harita_id))
        baglanti.commit()
        return yeni
    finally:
        baglanti.close()


def yol_haritasinin_commitleri(harita_id):
    """Yol haritasının bütün commit'leri, en yeniden eskiye."""
    baglanti = baglan()
    try:
        return baglanti.execute(
            "SELECT * FROM commitler WHERE yol_haritasi_id = ? ORDER BY tarih DESC", (harita_id,)
        ).fetchall()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 8) ÖĞRETMEN YORUMLARI
# ---------------------------------------------------------------------------

def yorum_ekle(adim_id, ogretmen_id, metin):
    """Öğretmenin bir adıma yorumunu kaydeder. (Yetki kontrolü app.py'de yapılır.)"""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        baglanti.execute(
            """INSERT INTO ogretmen_yorumlari (adim_id, ogretmen_id, metin, olusturma_zamani)
               VALUES (?, ?, ?, ?)""",
            (adim_id, ogretmen_id, metin, zaman),
        )
        baglanti.commit()
    finally:
        baglanti.close()


def yorum_sil(yorum_id, ogretmen_id):
    """
    Öğretmen sadece KENDİ yorumunu silebilir.
    Geri dönebilmek için (öğrenci id, yol haritası id, adım id) döndürür;
    yorum yoksa ya da başkasınınsa None.
    """
    baglanti = baglan()
    try:
        satir = baglanti.execute("""
            SELECT y.kullanici_id AS ogrenci_id, a.yol_haritasi_id AS harita_id, a.id AS adim_id
            FROM ogretmen_yorumlari AS o
            JOIN adimlar        AS a ON a.id = o.adim_id
            JOIN yol_haritalari AS y ON y.id = a.yol_haritasi_id
            WHERE o.id = ? AND o.ogretmen_id = ?
        """, (yorum_id, ogretmen_id)).fetchone()
        if satir is None:
            return None
        baglanti.execute("DELETE FROM ogretmen_yorumlari WHERE id = ?", (yorum_id,))
        baglanti.commit()
        return satir["ogrenci_id"], satir["harita_id"], satir["adim_id"]
    finally:
        baglanti.close()


def yol_haritasinin_yorumlari(harita_id):
    """Yol haritasındaki bütün öğretmen yorumları: {adim_id: [yorum, ...]} (eskiden yeniye)."""
    baglanti = baglan()
    try:
        satirlar = baglanti.execute("""
            SELECT o.*, k.kullanici_adi AS ogretmen_adi
            FROM ogretmen_yorumlari AS o
            JOIN adimlar      AS a ON a.id = o.adim_id
            JOIN kullanicilar AS k ON k.id = o.ogretmen_id
            WHERE a.yol_haritasi_id = ?
            ORDER BY o.id
        """, (harita_id,)).fetchall()
    finally:
        baglanti.close()

    sozluk = {}
    for satir in satirlar:
        sozluk.setdefault(satir["adim_id"], []).append(satir)
    return sozluk


def okunmamis_yorum_sayisi(ogrenci_id):
    """Öğrencinin bütün yol haritalarında henüz görmediği öğretmen yorumu sayısı."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT COUNT(*)
            FROM ogretmen_yorumlari AS o
            JOIN adimlar        AS a ON a.id = o.adim_id
            JOIN yol_haritalari AS y ON y.id = a.yol_haritasi_id
            WHERE y.kullanici_id = ? AND o.okundu = 0
        """, (ogrenci_id,)).fetchone()[0]
    finally:
        baglanti.close()


def yorumlari_okundu_yap(harita_id):
    """
    Yol haritasındaki yeni yorumları "okundu" yapar.
    Hangi yorumların yeni olduğunu (id listesi) döndürür; sayfa bunları
    bir kereliğine "Yeni" etiketiyle gösterir.
    """
    baglanti = baglan()
    try:
        yeniler = [satir["id"] for satir in baglanti.execute("""
            SELECT o.id FROM ogretmen_yorumlari AS o
            JOIN adimlar AS a ON a.id = o.adim_id
            WHERE a.yol_haritasi_id = ? AND o.okundu = 0
        """, (harita_id,))]
        if yeniler:
            # "IN (?, ?, ?)": listedeki kadar yer tutucu üretiyoruz
            yer_tutucular = ", ".join("?" * len(yeniler))
            baglanti.execute(f"UPDATE ogretmen_yorumlari SET okundu = 1 WHERE id IN ({yer_tutucular})",
                             yeniler)
            baglanti.commit()
        return yeniler
    finally:
        baglanti.close()


def ogretmen_gorebilir_mi(ogretmen_id, ogrenci_id):
    """
    Bu öğretmen bu öğrencinin verilerini görebilir mi?
    Sadece öğrenci, öğretmenin sınıflarından birine KENDİSİ katıldıysa evet.
    EXISTS: alt sorgu en az bir satır bulursa 1 (doğru), bulmazsa 0 döndürür.
    """
    baglanti = baglan()
    try:
        return bool(baglanti.execute("""
            SELECT EXISTS (
                SELECT 1 FROM sinif_uyeleri AS u
                JOIN siniflar AS s ON s.id = u.sinif_id
                WHERE s.ogretmen_id = ? AND u.ogrenci_id = ?
            )
        """, (ogretmen_id, ogrenci_id)).fetchone()[0])
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 9) ANA SAYFA: "Kaldığın yerden devam et"
# ---------------------------------------------------------------------------

def devam_edilecek_adim(kullanici_id):
    """
    Kullanıcının bitirmediği EN SON yol haritasını ve oradaki ilk bitmemiş adımı getirir.
    Bütün yol haritaları bitmişse (ya da hiç yoksa) None döner.

    ORDER BY y.id DESC, a.sira ASC + LIMIT 1:
      önce en yeni yol haritası, onun içinde de en küçük sıra numaralı bitmemiş adım;
      LIMIT 1 ile sadece ilk satırı alıyoruz.
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT y.id AS harita_id, y.proje, a.id AS adim_id, a.baslik, a.sira,
                   (SELECT COUNT(*) FROM adimlar WHERE yol_haritasi_id = y.id)                    AS toplam,
                   (SELECT COUNT(*) FROM adimlar WHERE yol_haritasi_id = y.id AND tamamlandi = 1) AS biten
            FROM yol_haritalari AS y
            JOIN adimlar AS a ON a.yol_haritasi_id = y.id
            WHERE y.kullanici_id = ? AND a.tamamlandi = 0
            ORDER BY y.id DESC, a.sira ASC
            LIMIT 1
        """, (kullanici_id,)).fetchone()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 10) KOD İNCELEMELERİ ("Kodumu incelet")
# ---------------------------------------------------------------------------

def kod_incelemesi_ekle(adim_id, kod, aciklama, geri_bildirim):
    """Öğrencinin gönderdiği kodu ve yapay zekânın geri bildirimini kaydeder."""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        baglanti.execute(
            """INSERT INTO kod_incelemeleri (adim_id, kod, aciklama, geri_bildirim, olusturma_zamani)
               VALUES (?, ?, ?, ?, ?)""",
            (adim_id, kod, aciklama or None, geri_bildirim, zaman),
        )
        baglanti.commit()
    finally:
        baglanti.close()


def adimin_inceleme_sayisi(adim_id):
    """Bir adım için kaç kez kod incelemesi istendiğini döndürür (hak sınırı için)."""
    baglanti = baglan()
    try:
        return baglanti.execute(
            "SELECT COUNT(*) FROM kod_incelemeleri WHERE adim_id = ?", (adim_id,)
        ).fetchone()[0]
    finally:
        baglanti.close()


def yol_haritasinin_incelemeleri(harita_id):
    """Yol haritasındaki bütün kod incelemeleri: {adim_id: [inceleme, ...]} (en yeni en üstte)."""
    baglanti = baglan()
    try:
        satirlar = baglanti.execute("""
            SELECT k.*
            FROM kod_incelemeleri AS k
            JOIN adimlar AS a ON a.id = k.adim_id
            WHERE a.yol_haritasi_id = ?
            ORDER BY k.id DESC
        """, (harita_id,)).fetchall()
    finally:
        baglanti.close()

    sozluk = {}
    for satir in satirlar:
        sozluk.setdefault(satir["adim_id"], []).append(satir)
    return sozluk


# ---------------------------------------------------------------------------
# 11) ADIMLARI DÜZENLEME (öğrenci yol haritasını kendine göre uyarlar)
# ---------------------------------------------------------------------------

def adim_ekle(harita_id, baslik, icerik):
    """
    Yol haritasının SONUNA öğrencinin kendi adımını ekler; yeni adımın id'sini döndürür.
    COALESCE(MAX(sira), 0) + 1: en büyük sıra numarasının bir fazlası
    (hiç adım yoksa MAX boş/NULL döner, COALESCE onu 0 yapar).
    """
    baglanti = baglan()
    try:
        sira = baglanti.execute(
            "SELECT COALESCE(MAX(sira), 0) + 1 FROM adimlar WHERE yol_haritasi_id = ?", (harita_id,)
        ).fetchone()[0]
        adim_id = baglanti.ekle(
            """INSERT INTO adimlar (yol_haritasi_id, sira, baslik, icerik, kendi_eklendi)
               VALUES (?, ?, ?, ?, 1)""",
            (harita_id, sira, baslik, icerik),
        )
        baglanti.commit()
        return adim_id
    finally:
        baglanti.close()


def adim_duzenle(adim_id, baslik, icerik):
    """Adımın başlığını ve içeriğini değiştirir. (Yetki kontrolü app.py'de yapılır.)"""
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE adimlar SET baslik = ?, icerik = ? WHERE id = ?",
                         (baslik, icerik, adim_id))
        baglanti.commit()
    finally:
        baglanti.close()


def adim_sil(adim_id):
    """
    Bir adımı siler ve sonraki adımların sıra numaralarını birer azaltır
    (Adım 2 silinirse eski Adım 3, yeni Adım 2 olur). Böylece numaralarda boşluk
    kalmaz ve GitHub'daki "Adım N" eşlemesi doğru çalışmaya devam eder.

    Yol haritasının son adımı silinemez; o durumda False döner.
    Hepsi tek bir işlemde (transaction) yapılır.
    """
    baglanti = baglan()
    try:
        adim = baglanti.execute("SELECT yol_haritasi_id, sira FROM adimlar WHERE id = ?",
                                (adim_id,)).fetchone()
        kalan = baglanti.execute("SELECT COUNT(*) FROM adimlar WHERE yol_haritasi_id = ?",
                                 (adim["yol_haritasi_id"],)).fetchone()[0]
        if kalan <= 1:
            return False

        # Önce adıma bağlı "çocuk" kayıtlar
        for tablo in ("ipuclari", "ogretmen_yorumlari", "kod_incelemeleri", "koc_sorulari",
                      "ogretmen_sorulari", "quizler"):
            baglanti.execute(f"DELETE FROM {tablo} WHERE adim_id = ?", (adim_id,))
        # Commit'ler GitHub'da hâlâ var; silmiyoruz, sadece adımla bağlarını koparıyoruz
        baglanti.execute("UPDATE commitler SET adim_id = NULL WHERE adim_id = ?", (adim_id,))
        baglanti.execute("DELETE FROM adimlar WHERE id = ?", (adim_id,))
        # Arkadaki adımları bir öne kaydır
        baglanti.execute("UPDATE adimlar SET sira = sira - 1 WHERE yol_haritasi_id = ? AND sira > ?",
                         (adim["yol_haritasi_id"], adim["sira"]))
        baglanti.commit()
        return True
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 12) ROZETLER
# ---------------------------------------------------------------------------

def rozet_verileri(kullanici_id):
    """
    Rozetlerin kazanılıp kazanılmadığını hesaplamak için gereken sayıları tek sorguda getirir.
    Her satır bir alt sorgu; ":k" yer tutucusu hepsinde aynı kullanıcı id'si.
    """
    baglanti = baglan()
    try:
        return dict(baglanti.execute("""
            SELECT
              -- Tamamlanan adım sayısı
              (SELECT COUNT(*) FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                WHERE y.kullanici_id = :k AND a.tamamlandi = 1)                       AS biten_adim,
              -- Hiç ipucu almadan tamamlanan adım sayısı (NOT EXISTS: o adıma ait ipucu yok)
              (SELECT COUNT(*) FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                WHERE y.kullanici_id = :k AND a.tamamlandi = 1
                  AND NOT EXISTS (SELECT 1 FROM ipuclari i WHERE i.adim_id = a.id))  AS ipucusuz_biten,
              -- 3 ipucunun hepsini kullanıp yine de tamamlanan adım sayısı
              (SELECT COUNT(*) FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                WHERE y.kullanici_id = :k AND a.tamamlandi = 1
                  AND (SELECT COUNT(*) FROM ipuclari i WHERE i.adim_id = a.id) >= 3) AS israrci_biten,
              -- Baştan sona biten yol haritası sayısı (alt sorgu içinde GROUP BY + HAVING)
              (SELECT COUNT(*) FROM (
                  SELECT y.id FROM yol_haritalari y JOIN adimlar a ON a.yol_haritasi_id = y.id
                  WHERE y.kullanici_id = :k
                  GROUP BY y.id HAVING SUM(a.tamamlandi) = COUNT(a.id)) AS biten)           AS biten_harita,
              (SELECT COUNT(*) FROM commitler c JOIN yol_haritalari y ON y.id = c.yol_haritasi_id
                WHERE y.kullanici_id = :k)                                          AS commit_sayisi,
              (SELECT COUNT(*) FROM kod_incelemeleri ki JOIN adimlar a ON a.id = ki.adim_id
                JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                WHERE y.kullanici_id = :k)                                          AS inceleme_sayisi,
              (SELECT COUNT(*) FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                WHERE y.kullanici_id = :k AND a.not_metni IS NOT NULL)              AS not_sayisi,
              (SELECT COUNT(*) FROM koc_sorulari s JOIN adimlar a ON a.id = s.adim_id
                JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                WHERE y.kullanici_id = :k)                                          AS soru_sayisi,
              -- Hedef tarihinde ya da daha önce bitirilen adımlar (tarih metinleri 'YYYY-AA-GG'
              -- biçiminde olduğu için harf harf karşılaştırmak tarih karşılaştırmakla aynı)
              (SELECT COUNT(*) FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                WHERE y.kullanici_id = :k AND a.tamamlandi = 1 AND a.hedef_tarih IS NOT NULL
                  AND SUBSTR(a.tamamlanma_zamani, 1, 10) <= a.hedef_tarih)          AS zamaninda_biten,
              (SELECT COUNT(*) FROM ogretmen_sorulari s JOIN adimlar a ON a.id = s.adim_id
                JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                WHERE y.kullanici_id = :k)                                          AS ogretmen_sorusu
        """, {"k": kullanici_id}).fetchone())
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 13) KOÇA SORU SOR
# ---------------------------------------------------------------------------

def koc_sorusu_ekle(adim_id, soru, cevap):
    """Öğrencinin sorusunu ve koçun cevabını kaydeder."""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        baglanti.execute(
            "INSERT INTO koc_sorulari (adim_id, soru, cevap, olusturma_zamani) VALUES (?, ?, ?, ?)",
            (adim_id, soru, cevap, zaman),
        )
        baglanti.commit()
    finally:
        baglanti.close()


def adimin_sorulari(adim_id):
    """Bir adımda sorulan soruları eskiden yeniye getirir (yapay zekâya geçmiş olarak verilir)."""
    baglanti = baglan()
    try:
        return baglanti.execute(
            "SELECT * FROM koc_sorulari WHERE adim_id = ? ORDER BY id", (adim_id,)
        ).fetchall()
    finally:
        baglanti.close()


def yol_haritasinin_sorulari(harita_id):
    """Yol haritasındaki bütün soru-cevaplar: {adim_id: [soru, ...]} (eskiden yeniye, sohbet gibi)."""
    baglanti = baglan()
    try:
        satirlar = baglanti.execute("""
            SELECT s.*
            FROM koc_sorulari AS s
            JOIN adimlar AS a ON a.id = s.adim_id
            WHERE a.yol_haritasi_id = ?
            ORDER BY s.id
        """, (harita_id,)).fetchall()
    finally:
        baglanti.close()

    sozluk = {}
    for satir in satirlar:
        sozluk.setdefault(satir["adim_id"], []).append(satir)
    return sozluk


# ---------------------------------------------------------------------------
# 14) PROFİL: şifre değiştirme ve hesap bilgileri
# ---------------------------------------------------------------------------

def sifre_degistir(kullanici_id, eski_sifre, yeni_sifre):
    """
    Eski şifre doğruysa yeni şifrenin hash'ini kaydeder ve True döndürür.
    Eski şifre yanlışsa hiçbir şey değiştirmez ve False döndürür.
    Neden eski şifreyi soruyoruz? Bilgisayarını açık bırakan birinin hesabını
    başkası ele geçiremesin diye.
    """
    baglanti = baglan()
    try:
        satir = baglanti.execute("SELECT sifre_hash FROM kullanicilar WHERE id = ?",
                                 (kullanici_id,)).fetchone()
        if satir is None or not check_password_hash(satir["sifre_hash"], eski_sifre):
            return False
        # gecici_sifre = 0: Öğretmenin verdiği geçici şifre varsa artık geçerli değil
        baglanti.execute("UPDATE kullanicilar SET sifre_hash = ?, gecici_sifre = 0 WHERE id = ?",
                         (generate_password_hash(yeni_sifre), kullanici_id))
        baglanti.commit()
        return True
    finally:
        baglanti.close()


def hesap_bilgileri(kullanici_id):
    """Profil sayfası için: kayıt tarihi, yol haritası / adım / soru sayıları ve ilk-son çalışma günü."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT u.kullanici_adi, u.rol, u.olusturma_zamani, u.hakkimda,
                   (SELECT COUNT(*) FROM yol_haritalari WHERE kullanici_id = :k)        AS harita_sayisi,
                   (SELECT COUNT(*) FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = :k AND a.tamamlandi = 1)                    AS biten_adim,
                   -- En son ne zaman bir adım bitirdi? (MAX: en büyük = en yeni tarih)
                   (SELECT MAX(a.tamamlanma_zamani) FROM adimlar a
                     JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = :k)                                         AS son_tamamlama
            FROM kullanicilar u
            WHERE u.id = :k
        """, {"k": kullanici_id}).fetchone()
    finally:
        baglanti.close()


def calisma_gunleri(kullanici_id):
    """
    Öğrencinin "çalıştığı" günleri {"2026-11-10": 3, ...} (gün: o günkü etkinlik sayısı) döndürür.
    Etkinlik = adım bitirmek, ipucu almak, koça soru sormak, kod incelettirmek, yol haritası çıkarmak.

    UNION ALL: Beş ayrı SELECT'in sonuçlarını alt alta tek listede birleştirir.
    SUBSTR(..., 1, 10): '2026-11-10 16:49:00' -> '2026-11-10' (saati atar, sadece gün kalır).
    Dıştaki GROUP BY gun: aynı güne düşen etkinlikleri sayar.
    """
    baglanti = baglan()
    try:
        satirlar = baglanti.execute("""
            SELECT gun, COUNT(*) AS sayi FROM (
                SELECT SUBSTR(y.olusturma_zamani, 1, 10) AS gun FROM yol_haritalari y
                 WHERE y.kullanici_id = :k
                UNION ALL
                SELECT SUBSTR(a.tamamlanma_zamani, 1, 10) FROM adimlar a
                  JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                 WHERE y.kullanici_id = :k AND a.tamamlanma_zamani IS NOT NULL
                UNION ALL
                SELECT SUBSTR(i.olusturma_zamani, 1, 10) FROM ipuclari i
                  JOIN adimlar a ON a.id = i.adim_id JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                 WHERE y.kullanici_id = :k
                UNION ALL
                SELECT SUBSTR(s.olusturma_zamani, 1, 10) FROM koc_sorulari s
                  JOIN adimlar a ON a.id = s.adim_id JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                 WHERE y.kullanici_id = :k
                UNION ALL
                SELECT SUBSTR(ki.olusturma_zamani, 1, 10) FROM kod_incelemeleri ki
                  JOIN adimlar a ON a.id = ki.adim_id JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                 WHERE y.kullanici_id = :k
            ) AS etkinlikler
            GROUP BY gun
        """, {"k": kullanici_id}).fetchall()
    finally:
        baglanti.close()
    return {satir["gun"]: satir["sayi"] for satir in satirlar}


# ---------------------------------------------------------------------------
# 15) SINIF DUYURULARI
# ---------------------------------------------------------------------------

def duyuru_ekle(sinif_id, metin):
    """Sınıfa yeni bir duyuru ekler. (Sınıfın bu öğretmenin olduğu app.py'de kontrol edilir.)"""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        baglanti.execute("INSERT INTO duyurular (sinif_id, metin, olusturma_zamani) VALUES (?, ?, ?)",
                         (sinif_id, metin, zaman))
        baglanti.commit()
    finally:
        baglanti.close()


def sinifin_duyurulari(sinif_id):
    """Bir sınıfın duyuruları, en yenisi en üstte."""
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT * FROM duyurular WHERE sinif_id = ? ORDER BY id DESC",
                                (sinif_id,)).fetchall()
    finally:
        baglanti.close()


def duyuru_sil(duyuru_id, ogretmen_id):
    """
    Duyuruyu siler; sadece duyurunun yazıldığı sınıfın öğretmeni silebilir.
    Silinen duyurunun sınıf id'sini döndürür (geri dönmek için), silinemezse None.
    """
    baglanti = baglan()
    try:
        # JOIN ile "bu duyuru, bu öğretmenin sınıfında mı?" kontrolü
        satir = baglanti.execute("""
            SELECT d.sinif_id FROM duyurular AS d
            JOIN siniflar AS s ON s.id = d.sinif_id
            WHERE d.id = ? AND s.ogretmen_id = ?
        """, (duyuru_id, ogretmen_id)).fetchone()
        if satir is None:
            return None
        baglanti.execute("DELETE FROM duyurular WHERE id = ?", (duyuru_id,))
        baglanti.commit()
        return satir["sinif_id"]
    finally:
        baglanti.close()


def ogrencinin_duyurulari(ogrenci_id, sadece_yeniler=False, sinir=None):
    """
    Öğrencinin üye olduğu sınıfların duyuruları (en yenisi üstte), sınıf ve öğretmen adıyla.
    Her satırda "yeni" sütunu var: 1 = öğrenci henüz görmedi.
    Öğrenci sınıftan ayrılırsa JOIN sinif_uyeleri satırı kalmadığı için duyurular da görünmez.
    """
    sorgu = """
        SELECT d.*, s.ad AS sinif_adi, k.kullanici_adi AS ogretmen_adi,
               d.id > o.son_okunan_duyuru AS yeni          -- Karşılaştırma 1 ya da 0 döndürür
        FROM duyurular     AS d
        JOIN sinif_uyeleri AS u ON u.sinif_id = d.sinif_id AND u.ogrenci_id = :o
        JOIN siniflar      AS s ON s.id = d.sinif_id
        JOIN kullanicilar  AS k ON k.id = s.ogretmen_id
        JOIN kullanicilar  AS o ON o.id = :o                -- Öğrencinin kendi satırı
    """
    if sadece_yeniler:
        sorgu += " WHERE d.id > o.son_okunan_duyuru"
    sorgu += " ORDER BY d.id DESC"
    if sinir:
        sorgu += f" LIMIT {int(sinir)}"                     # int(): metne sadece sayı girebilir
    baglanti = baglan()
    try:
        return baglanti.execute(sorgu, {"o": ogrenci_id}).fetchall()
    finally:
        baglanti.close()


def okunmamis_duyuru_sayisi(ogrenci_id):
    """Menüdeki "Sınıfım" yanındaki sayı için."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT COUNT(*) FROM duyurular AS d
            JOIN sinif_uyeleri AS u ON u.sinif_id = d.sinif_id
            WHERE u.ogrenci_id = :o
              AND d.id > (SELECT son_okunan_duyuru FROM kullanicilar WHERE id = :o)
        """, {"o": ogrenci_id}).fetchone()[0]
    finally:
        baglanti.close()


def duyurulari_okundu_yap(ogrenci_id):
    """
    Öğrencinin "son okunan duyuru" değerini, görebildiği en büyük duyuru id'sine çeker.
    Neden her duyuru için ayrı "okundu" satırı tutmuyoruz? Duyurular sırayla (artan id ile)
    eklendiği için tek bir sayı yetiyor: "şu id'ye kadar hepsini gördü".
    MAX(...) yanında 0 da var: MAX(a, b) iki sayıdan büyüğünü verir; hiç duyuru yoksa değer düşmez.
    """
    baglanti = baglan()
    try:
        baglanti.execute(f"""
            UPDATE kullanicilar
            SET son_okunan_duyuru = {BUYUGU}(son_okunan_duyuru, COALESCE((
                SELECT MAX(d.id) FROM duyurular AS d
                JOIN sinif_uyeleri AS u ON u.sinif_id = d.sinif_id
                WHERE u.ogrenci_id = :o), 0))
            WHERE id = :o
        """, {"o": ogrenci_id})
        baglanti.commit()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 16) CANLIYA GEÇİŞ: yapay zekâ kotası ve yanlış giriş denemeleri
# ---------------------------------------------------------------------------

def bugunku_yz_kullanimi(kullanici_id):
    """Kullanıcının bugün yapay zekâya kaç istek gönderdiğini döndürür."""
    gun = datetime.now().strftime("%Y-%m-%d")
    baglanti = baglan()
    try:
        satir = baglanti.execute("SELECT sayi FROM yz_kullanimi WHERE kullanici_id = ? AND gun = ?",
                                 (kullanici_id, gun)).fetchone()
        return satir["sayi"] if satir else 0
    finally:
        baglanti.close()


def bugunku_toplam_yz_kullanimi():
    """Bütün sitede bugün yapay zekâya gönderilen istek sayısı (ortak anahtarın kotası için)."""
    gun = datetime.now().strftime("%Y-%m-%d")
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT COALESCE(SUM(sayi), 0) FROM yz_kullanimi WHERE gun = ?",
                                (gun,)).fetchone()[0]
    finally:
        baglanti.close()


def yz_kullanimi_ekle(kullanici_id):
    """
    Bugünkü sayacı bir artırır. "UPSERT": satır yoksa ekler (sayi = 1),
    varsa (ON CONFLICT) var olan satırın sayısını bir artırır.
    """
    gun = datetime.now().strftime("%Y-%m-%d")
    baglanti = baglan()
    try:
        baglanti.execute("""
            INSERT INTO yz_kullanimi (kullanici_id, gun, sayi) VALUES (?, ?, 1)
            ON CONFLICT (kullanici_id, gun) DO UPDATE SET sayi = yz_kullanimi.sayi + 1
        """, (kullanici_id, gun))
        baglanti.commit()
    finally:
        baglanti.close()


def yanlis_giris_ekle(kullanici_adi):
    """Bir yanlış şifre denemesini kaydeder."""
    baglanti = baglan()
    try:
        baglanti.execute("INSERT INTO giris_denemeleri (kullanici_adi, zaman) VALUES (?, ?)",
                         (kullanici_adi, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        baglanti.commit()
    finally:
        baglanti.close()


def son_yanlis_giris_sayisi(kullanici_adi, dakika):
    """Son 'dakika' dakika içindeki yanlış deneme sayısı. Eski kayıtları da temizler."""
    sinir = (datetime.now() - timedelta(minutes=dakika)).strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        # Süresi dolmuş denemeleri sil ki tablo sonsuza kadar büyümesin
        baglanti.execute("DELETE FROM giris_denemeleri WHERE zaman < ?", (sinir,))
        baglanti.commit()
        return baglanti.execute("SELECT COUNT(*) FROM giris_denemeleri WHERE LOWER(kullanici_adi) = LOWER(?)",
                                (kullanici_adi,)).fetchone()[0]
    finally:
        baglanti.close()


def yanlis_girisleri_temizle(kullanici_adi):
    """Doğru şifre girilince o kullanıcı adının yanlış denemelerini siler."""
    baglanti = baglan()
    try:
        baglanti.execute("DELETE FROM giris_denemeleri WHERE LOWER(kullanici_adi) = LOWER(?)",
                         (kullanici_adi,))
        baglanti.commit()
    finally:
        baglanti.close()

# ---------------------------------------------------------------------------
# 17) ÖĞRETMENİN ŞİFRE SIFIRLAMASI VE HESAP SİLME
# ---------------------------------------------------------------------------

# Geçici şifrede karıştırılabilecek karakterler yok (0/o, 1/l/i gibi); öğretmen tahtaya yazabilsin
GECICI_SIFRE_KARAKTERLERI = "abcdefghjkmnpqrstuvwxyz23456789"


def gecici_sifre_ver(ogrenci_id):
    """
    Öğrenciye rastgele 8 karakterlik geçici şifre verir ve şifreyi döndürür.
    gecici_sifre = 1: Öğrenci bu şifreyle girince önce kendi şifresini belirlemek zorunda.
    Öğrencinin yanlış şifre denemeleri de silinir (kilitlendiyse açılsın).
    (Öğretmenin bu öğrenciyi görme yetkisi app.py'de kontrol edilir.)
    """
    sifre = "".join(secrets.choice(GECICI_SIFRE_KARAKTERLERI) for _ in range(8))
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE kullanicilar SET sifre_hash = ?, gecici_sifre = 1 WHERE id = ?",
                         (generate_password_hash(sifre), ogrenci_id))
        baglanti.execute("""DELETE FROM giris_denemeleri WHERE LOWER(kullanici_adi) =
                            (SELECT LOWER(kullanici_adi) FROM kullanicilar WHERE id = ?)""", (ogrenci_id,))
        baglanti.commit()
        return sifre
    finally:
        baglanti.close()


def hesap_sil(kullanici_id, sifre):
    """
    Kullanıcıyı ve ona ait HER ŞEYİ siler; şifre yanlışsa hiçbir şey yapmaz ve False döner.
    Hepsi tek bir işlemde (transaction): yarıda bir hata olursa hiçbiri silinmez.
    Sıra önemli: önce "çocuk" kayıtlar (ipuçları, adımlar...), en son kullanıcının kendisi.
    """
    baglanti = baglan()
    try:
        satir = baglanti.execute("SELECT kullanici_adi, sifre_hash FROM kullanicilar WHERE id = ?",
                                 (kullanici_id,)).fetchone()
        if satir is None or not check_password_hash(satir["sifre_hash"], sifre):
            return False

        # 1) Kullanıcının yol haritalarına bağlı her şey
        haritalari = "SELECT id FROM yol_haritalari WHERE kullanici_id = :k"
        adimlari = f"SELECT id FROM adimlar WHERE yol_haritasi_id IN ({haritalari})"
        for tablo in ("ipuclari", "ogretmen_yorumlari", "kod_incelemeleri", "koc_sorulari",
                      "ogretmen_sorulari", "quizler"):
            baglanti.execute(f"DELETE FROM {tablo} WHERE adim_id IN ({adimlari})", {"k": kullanici_id})
        baglanti.execute(f"DELETE FROM commitler WHERE yol_haritasi_id IN ({haritalari})", {"k": kullanici_id})
        baglanti.execute(f"DELETE FROM adimlar WHERE yol_haritasi_id IN ({haritalari})", {"k": kullanici_id})
        baglanti.execute("DELETE FROM yol_haritalari WHERE kullanici_id = :k", {"k": kullanici_id})

        # 2) Öğretmense: başkalarına yazdığı yorumlar ve açtığı sınıflar (duyuruları, üyelikleriyle)
        baglanti.execute("DELETE FROM ogretmen_yorumlari WHERE ogretmen_id = :k", {"k": kullanici_id})
        # Öğretmenin verdiği cevaplar öğrencide kalır, sadece "kim cevapladı" bilgisi silinir
        baglanti.execute("UPDATE ogretmen_sorulari SET cevaplayan_id = NULL WHERE cevaplayan_id = :k",
                         {"k": kullanici_id})
        siniflari = "SELECT id FROM siniflar WHERE ogretmen_id = :k"
        baglanti.execute(f"DELETE FROM duyurular WHERE sinif_id IN ({siniflari})", {"k": kullanici_id})
        # Mesajlar: öğretmenin sınıflarının sohbetleri ve kullanıcının gönderdiği/aldığı bütün mesajlar
        gruplari = f"SELECT id FROM gruplar WHERE sinif_id IN ({siniflari})"
        silinecek = f"""SELECT id FROM mesajlar WHERE sinif_id IN ({siniflari}) OR grup_id IN ({gruplari})
                         OR gonderen_id = :k OR alici_id = :k"""
        baglanti.execute(f"DELETE FROM sikayetler WHERE mesaj_id IN ({silinecek}) OR bildiren_id = :k",
                         {"k": kullanici_id})
        baglanti.execute("DELETE FROM engellemeler WHERE engelleyen_id = :k OR engellenen_id = :k",
                         {"k": kullanici_id})
        baglanti.execute(f"DELETE FROM mesajlar WHERE sinif_id IN ({siniflari})", {"k": kullanici_id})
        # Gruplar: öğretmenin sınıflarındaki gruplar tamamen; öğrencinin üyelikleri ve görev atamaları
        for tablo in ("mesajlar", "gorevler", "grup_uyeleri", "grup_okuma", "grup_davetleri"):
            baglanti.execute(f"DELETE FROM {tablo} WHERE grup_id IN ({gruplari})", {"k": kullanici_id})
        baglanti.execute(f"DELETE FROM gruplar WHERE sinif_id IN ({siniflari})", {"k": kullanici_id})
        baglanti.execute("DELETE FROM grup_uyeleri WHERE ogrenci_id = :k", {"k": kullanici_id})
        _yoneticiligi_devret(baglanti, kullanici_id)        # Kurduğu sohbet grupları başkasına geçer
        baglanti.execute("DELETE FROM grup_okuma WHERE kullanici_id = :k", {"k": kullanici_id})
        baglanti.execute("UPDATE gorevler SET atanan_id = NULL WHERE atanan_id = :k", {"k": kullanici_id})
        baglanti.execute("UPDATE gorevler SET olusturan_id = NULL WHERE olusturan_id = :k", {"k": kullanici_id})
        odevleri = f"SELECT id FROM odevler WHERE sinif_id IN ({siniflari})"
        baglanti.execute(f"DELETE FROM teslimler WHERE odev_id IN ({odevleri}) OR ogrenci_id = :k",
                         {"k": kullanici_id})
        baglanti.execute(f"DELETE FROM odevler WHERE sinif_id IN ({siniflari})", {"k": kullanici_id})
        baglanti.execute(f"DELETE FROM sohbet_okuma WHERE sinif_id IN ({siniflari})", {"k": kullanici_id})
        baglanti.execute("DELETE FROM mesajlar WHERE gonderen_id = :k OR alici_id = :k", {"k": kullanici_id})
        baglanti.execute("DELETE FROM sohbet_okuma WHERE kullanici_id = :k OR diger_id = :k", {"k": kullanici_id})
        baglanti.execute(f"DELETE FROM sinif_uyeleri WHERE sinif_id IN ({siniflari})", {"k": kullanici_id})
        baglanti.execute(f"UPDATE yol_haritalari SET sinif_id = NULL WHERE sinif_id IN ({siniflari})",
                         {"k": kullanici_id})
        baglanti.execute("DELETE FROM siniflar WHERE ogretmen_id = :k", {"k": kullanici_id})
        baglanti.execute("DELETE FROM sablonlar WHERE ogretmen_id = :k", {"k": kullanici_id})
        baglanti.execute("DELETE FROM sifre_sifirlama WHERE kullanici_id = :k", {"k": kullanici_id})
        # Davetler (gelen ve gönderdiği), anket oyları; mesajları silindiği için anketleri ve resimleri
        baglanti.execute("DELETE FROM grup_davetleri WHERE davet_edilen_id = :k OR davet_eden_id = :k",
                         {"k": kullanici_id})
        baglanti.execute("DELETE FROM anket_oylari WHERE kullanici_id = :k", {"k": kullanici_id})
        _sahipsizleri_temizle(baglanti)
        baglanti.execute("DELETE FROM resimler WHERE sahip_id = :k", {"k": kullanici_id})

        # 3) Üyelikler, yapay zekâ sayacı, giriş denemeleri ve en son kullanıcı
        baglanti.execute("DELETE FROM sinif_uyeleri WHERE ogrenci_id = :k", {"k": kullanici_id})
        baglanti.execute("DELETE FROM yz_kullanimi WHERE kullanici_id = :k", {"k": kullanici_id})
        baglanti.execute("DELETE FROM giris_denemeleri WHERE LOWER(kullanici_adi) = LOWER(:ad)",
                         {"ad": satir["kullanici_adi"]})
        baglanti.execute("DELETE FROM kullanicilar WHERE id = :k", {"k": kullanici_id})
        baglanti.commit()
        return True
    finally:
        baglanti.close()

# ---------------------------------------------------------------------------
# 18) HEDEF TARİHLER VE HAFTALIK ÖZET
# ---------------------------------------------------------------------------

def hedef_tarih_ayarla(adim_id, tarih, koyan="ogretmen"):
    """
    Adımın hedef tarihini ayarlar ("2026-11-21"); tarih None ise hedefi kaldırır.
    koyan: "ogretmen" ya da "ogrenci" (öğrenci, öğretmenin koyduğu tarihi değiştiremez).
    """
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE adimlar SET hedef_tarih = ?, hedef_koyan = ? WHERE id = ?",
                         (tarih, koyan if tarih else None, adim_id))
        baglanti.commit()
    finally:
        baglanti.close()


def yaklasan_hedefler(kullanici_id, son_gun):
    """
    Öğrencinin bitmemiş ve hedef tarihi 'son_gun'e kadar olan adımları (gecikmişler dahil),
    en yakın tarih en üstte. Ana sayfadaki "Yaklaşan hedefler" kartı için.
    "2026-11-20" < "2026-11-21": Tarihleri YYYY-AA-GG biçiminde metin olarak sakladığımız
    için metin karşılaştırması tarih karşılaştırmasıyla aynı sonucu verir.
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT a.id AS adim_id, a.baslik, a.sira, a.hedef_tarih, y.id AS harita_id, y.proje
            FROM adimlar AS a
            JOIN yol_haritalari AS y ON y.id = a.yol_haritasi_id
            WHERE y.kullanici_id = ? AND a.tamamlandi = 0
              AND a.hedef_tarih IS NOT NULL AND a.hedef_tarih <= ?
            ORDER BY a.hedef_tarih, a.sira
        """, (kullanici_id, son_gun)).fetchall()
    finally:
        baglanti.close()


def haftalik_ozet(kullanici_id, bu_hafta_basi, gecen_hafta_basi):
    """
    Bu hafta ve geçen hafta kaç adım bitirdi? (Hafta pazartesi başlar.)
    Haftanın başı "2026-11-16" ise "2026-11-16 00:00:00" ve sonrası bu haftadır.
    """
    baglanti = baglan()
    try:
        satir = baglanti.execute("""
            SELECT
              (SELECT COUNT(*) FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                WHERE y.kullanici_id = :k AND a.tamamlandi = 1
                  AND a.tamamlanma_zamani >= :bu)                               AS bu_hafta,
              (SELECT COUNT(*) FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                WHERE y.kullanici_id = :k AND a.tamamlandi = 1
                  AND a.tamamlanma_zamani >= :gecen AND a.tamamlanma_zamani < :bu) AS gecen_hafta
        """, {"k": kullanici_id, "bu": bu_hafta_basi, "gecen": gecen_hafta_basi}).fetchone()
        return {"bu_hafta": satir["bu_hafta"], "gecen_hafta": satir["gecen_hafta"]}
    finally:
        baglanti.close()

# ---------------------------------------------------------------------------
# 19) SINIF PROJESİ VE SINIFIN SON ETKİNLİKLERİ
# ---------------------------------------------------------------------------

def sinif_proje_ayarla(sinif_id, proje):
    """Sınıfın ortak projesini ayarlar; proje None ise kaldırır. (Yetki app.py'de kontrol edilir.)"""
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE siniflar SET proje = ? WHERE id = ?", (proje, sinif_id))
        baglanti.commit()
    finally:
        baglanti.close()


def sinif_etkinlik_akisi(sinif_id, sinir=20):
    """
    Sınıftaki öğrencilerin son etkinlikleri, en yenisi en üstte:
    yol haritası çıkarma, adım bitirme, ipucu, koça soru, kod inceleme, commit.

    UNION ALL ile altı farklı tablodan aynı biçimde satırlar üretiyoruz; her satırın
    "tur" sütunu olayın ne olduğunu söylüyor. Bütün SELECT'lerde sütun sayısı ve sırası
    aynı olmalı. İlk SELECT'teki CAST(NULL AS INTEGER): PostgreSQL boş değerin tipini
    bilemez, sayı olduğunu biz söylüyoruz.
    """
    adim_ortak = """
        JOIN adimlar a ON a.id = x.adim_id
        JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
        JOIN kullanicilar k ON k.id = y.kullanici_id
        WHERE y.kullanici_id IN (SELECT ogrenci_id FROM sinif_uyeleri WHERE sinif_id = :s)"""
    sorgu = f"""
        SELECT * FROM (
            SELECT 'harita' AS tur, y.olusturma_zamani AS zaman, k.id AS ogrenci_id, k.kullanici_adi,
                   y.id AS harita_id, CAST(NULL AS INTEGER) AS adim_id, CAST(NULL AS INTEGER) AS sira,
                   y.proje AS baslik
              FROM yol_haritalari y JOIN kullanicilar k ON k.id = y.kullanici_id
             WHERE y.kullanici_id IN (SELECT ogrenci_id FROM sinif_uyeleri WHERE sinif_id = :s)
            UNION ALL
            SELECT 'adim', a.tamamlanma_zamani, k.id, k.kullanici_adi, y.id, a.id, a.sira, a.baslik
              FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
              JOIN kullanicilar k ON k.id = y.kullanici_id
             WHERE a.tamamlandi = 1 AND a.tamamlanma_zamani IS NOT NULL
               AND y.kullanici_id IN (SELECT ogrenci_id FROM sinif_uyeleri WHERE sinif_id = :s)
            UNION ALL
            SELECT 'ipucu', x.olusturma_zamani, k.id, k.kullanici_adi, y.id, a.id, a.sira, a.baslik
              FROM ipuclari x {adim_ortak}
            UNION ALL
            SELECT 'soru', x.olusturma_zamani, k.id, k.kullanici_adi, y.id, a.id, a.sira, a.baslik
              FROM koc_sorulari x {adim_ortak}
            UNION ALL
            SELECT 'inceleme', x.olusturma_zamani, k.id, k.kullanici_adi, y.id, a.id, a.sira, a.baslik
              FROM kod_incelemeleri x {adim_ortak}
            UNION ALL
            SELECT 'commit', c.tarih, k.id, k.kullanici_adi, y.id, c.adim_id, CAST(NULL AS INTEGER), c.mesaj
              FROM commitler c JOIN yol_haritalari y ON y.id = c.yol_haritasi_id
              JOIN kullanicilar k ON k.id = y.kullanici_id
             WHERE y.kullanici_id IN (SELECT ogrenci_id FROM sinif_uyeleri WHERE sinif_id = :s)
        ) AS olaylar
        ORDER BY zaman DESC
        LIMIT {int(sinir)}
    """
    baglanti = baglan()
    try:
        return baglanti.execute(sorgu, {"s": sinif_id}).fetchall()
    finally:
        baglanti.close()

# ---------------------------------------------------------------------------
# 20) ÖĞRETMEN DEĞERLENDİRMESİ
# ---------------------------------------------------------------------------

def yol_haritasi_degerlendir(harita_id, ogretmen_id, puan, metin):
    """
    Öğretmenin yol haritası değerlendirmesini kaydeder (puan 1-5, kısa metin).
    puan None ise değerlendirme kaldırılır. (Yetki kontrolü app.py'de yapılır.)
    """
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if puan else None
    baglanti = baglan()
    try:
        baglanti.execute("""
            UPDATE yol_haritalari
            SET degerlendirme_puan = ?, degerlendirme_metin = ?, degerlendirme_zamani = ?,
                degerlendiren_id = ?, degerlendirme_goruldu = ?
            WHERE id = ?
        """, (puan, metin if puan else None, zaman, ogretmen_id if puan else None,
              0 if puan else 1, harita_id))
        baglanti.commit()
    finally:
        baglanti.close()


def degerlendiren_adi(kullanici_id):
    """Değerlendirmeyi yapan öğretmenin adı (hesap silindiyse None)."""
    satir = kullanici_getir(kullanici_id) if kullanici_id else None
    return satir["kullanici_adi"] if satir else None


# ---------------------------------------------------------------------------
# 21) BİLDİRİMLER VE TOPLU HEDEF
# ---------------------------------------------------------------------------

def okunmamis_bildirim_sayisi(ogrenci_id):
    """
    Menüdeki "Geçmiş" rozeti: görülmemiş öğretmen yorumları + değerlendirmeler + soru cevapları.
    Üç alt sorgunun sonucu toplanıyor.
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT (SELECT COUNT(*) FROM ogretmen_yorumlari o
                      JOIN adimlar a ON a.id = o.adim_id
                      JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = :k AND o.okundu = 0)
                 + (SELECT COUNT(*) FROM yol_haritalari
                     WHERE kullanici_id = :k AND degerlendirme_goruldu = 0)
                 + (SELECT COUNT(*) FROM ogretmen_sorulari s
                      JOIN adimlar a ON a.id = s.adim_id
                      JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
                     WHERE y.kullanici_id = :k AND s.cevap_goruldu = 0)
        """, {"k": ogrenci_id}).fetchone()[0]
    finally:
        baglanti.close()


def degerlendirmeyi_goruldu_yap(harita_id):
    """
    Öğrenci yol haritasını açınca değerlendirmeyi "görüldü" yapar.
    Yeni miydi? (True/False) döndürür; sayfa bir kereliğine "Yeni" etiketi göstersin diye.
    """
    baglanti = baglan()
    try:
        imlec = baglanti.execute("""UPDATE yol_haritalari SET degerlendirme_goruldu = 1
                                    WHERE id = ? AND degerlendirme_goruldu = 0""", (harita_id,))
        baglanti.commit()
        return imlec.rowcount > 0
    finally:
        baglanti.close()


def toplu_hedef_koy(sinif_id, sira, tarih):
    """
    Sınıf projesinde, sınıftaki BÜTÜN öğrencilerin "sira" numaralı adımına aynı hedef tarihi koyar.
    Sadece bu sınıfın projesi için çıkarılmış ve öğrencisi hâlâ sınıfta olan yol haritaları
    (öğrencinin başka projelerine dokunulmaz). Kaç adıma tarih konduğunu döndürür.
    """
    baglanti = baglan()
    try:
        imlec = baglanti.execute("""
            UPDATE adimlar SET hedef_tarih = ?, hedef_koyan = 'ogretmen'
            WHERE sira = ? AND yol_haritasi_id IN (
                SELECT y.id FROM yol_haritalari y
                JOIN sinif_uyeleri u ON u.ogrenci_id = y.kullanici_id AND u.sinif_id = y.sinif_id
                WHERE y.sinif_id = ?)
        """, (tarih, sira, sinif_id))
        baglanti.commit()
        return imlec.rowcount
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 22) ÖĞRETMENİME SOR VE SINIF PROJESİNİN ADIM DAĞILIMI
# ---------------------------------------------------------------------------

def ogretmene_soru_ekle(adim_id, soru):
    """Öğrencinin öğretmenine sorduğu soruyu kaydeder. (Yetki app.py'de kontrol edilir.)"""
    baglanti = baglan()
    try:
        baglanti.execute("INSERT INTO ogretmen_sorulari (adim_id, soru, soru_zamani) VALUES (?, ?, ?)",
                         (adim_id, soru, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        baglanti.commit()
    finally:
        baglanti.close()


def acik_soru_sayisi(ogrenci_id):
    """Öğrencinin henüz cevaplanmamış soru sayısı (aynı anda en fazla birkaç soru sorabilsin)."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT COUNT(*) FROM ogretmen_sorulari s
            JOIN adimlar a ON a.id = s.adim_id
            JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
            WHERE y.kullanici_id = ? AND s.cevap IS NULL
        """, (ogrenci_id,)).fetchone()[0]
    finally:
        baglanti.close()


def yol_haritasinin_ogretmen_sorulari(harita_id):
    """Yol haritasındaki öğretmene sorulan sorular: {adim_id: [soru, ...]} (eskiden yeniye)."""
    baglanti = baglan()
    try:
        satirlar = baglanti.execute("""
            SELECT s.*, k.kullanici_adi AS cevaplayan_adi
            FROM ogretmen_sorulari AS s
            JOIN adimlar AS a ON a.id = s.adim_id
            LEFT JOIN kullanicilar AS k ON k.id = s.cevaplayan_id
            WHERE a.yol_haritasi_id = ?
            ORDER BY s.id
        """, (harita_id,)).fetchall()
    finally:
        baglanti.close()
    sozluk = {}
    for satir in satirlar:
        sozluk.setdefault(satir["adim_id"], []).append(satir)
    return sozluk


def ogretmen_sorusu_getir(soru_id):
    """Soruyu, sahibi olan öğrencinin ve yol haritasının id'siyle birlikte getirir (yoksa None)."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT s.*, y.kullanici_id AS ogrenci_id, y.id AS harita_id
            FROM ogretmen_sorulari AS s
            JOIN adimlar AS a ON a.id = s.adim_id
            JOIN yol_haritalari AS y ON y.id = a.yol_haritasi_id
            WHERE s.id = ?
        """, (soru_id,)).fetchone()
    finally:
        baglanti.close()


def ogretmen_sorusunu_cevapla(soru_id, ogretmen_id, cevap, paylas=False):
    """
    Öğretmenin cevabını kaydeder; öğrenci için "yeni" olur (cevap_goruldu = 0).
    paylas: True ise soru-cevap öğretmenin sınıflarındaki herkese (soranın adı olmadan) görünür.
    """
    baglanti = baglan()
    try:
        baglanti.execute("""
            UPDATE ogretmen_sorulari
            SET cevap = ?, cevaplayan_id = ?, cevap_zamani = ?, cevap_goruldu = 0, paylasildi = ?
            WHERE id = ?
        """, (cevap, ogretmen_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              1 if paylas else 0, soru_id))
        baglanti.commit()
    finally:
        baglanti.close()


def cevaplari_goruldu_yap(harita_id):
    """Öğrenci yol haritasını açınca yeni cevapları "görüldü" yapar; yeni olanların id'lerini döndürür."""
    baglanti = baglan()
    try:
        yeniler = [s["id"] for s in baglanti.execute("""
            SELECT s.id FROM ogretmen_sorulari s JOIN adimlar a ON a.id = s.adim_id
            WHERE a.yol_haritasi_id = ? AND s.cevap_goruldu = 0
        """, (harita_id,)).fetchall()]
        if yeniler:
            yer_tutucular = ", ".join("?" * len(yeniler))
            baglanti.execute(f"UPDATE ogretmen_sorulari SET cevap_goruldu = 1 WHERE id IN ({yer_tutucular})",
                             yeniler)
            baglanti.commit()
        return yeniler
    finally:
        baglanti.close()


def ogretmenin_bekleyen_sorulari(ogretmen_id):
    """
    Öğretmenin sınıflarındaki öğrencilerin cevap bekleyen soruları, en eskisi en üstte
    (önce bekleyen önce cevaplansın). EXISTS: öğrenci bu öğretmenin sınıflarından
    en az birinde mi? Öğrenci iki sınıftaysa bile soru bir kez gelir.
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT s.id, s.soru, s.soru_zamani, a.id AS adim_id, a.baslik, a.sira,
                   y.id AS harita_id, k.id AS ogrenci_id, k.kullanici_adi
            FROM ogretmen_sorulari AS s
            JOIN adimlar        AS a ON a.id = s.adim_id
            JOIN yol_haritalari AS y ON y.id = a.yol_haritasi_id
            JOIN kullanicilar   AS k ON k.id = y.kullanici_id
            WHERE s.cevap IS NULL AND EXISTS (
                SELECT 1 FROM sinif_uyeleri u JOIN siniflar c ON c.id = u.sinif_id
                WHERE u.ogrenci_id = k.id AND c.ogretmen_id = ?)
            ORDER BY s.soru_zamani
        """, (ogretmen_id,)).fetchall()
    finally:
        baglanti.close()


def sinif_projesi_adimlari(sinif_id):
    """
    Sınıf projesinin adım dağılımı için ham veri: sınıftaki her öğrencinin sınıf projesi
    için çıkardığı EN SON yol haritasının adımları (sıra, bitti mi, kaç ipucu alındı).
    Hesaplama (kim hangi adımda?) app.py'de yapılır.
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT a.yol_haritasi_id AS harita_id, a.sira, a.tamamlandi,
                   (SELECT COUNT(*) FROM ipuclari i WHERE i.adim_id = a.id) AS ipucu_sayisi
            FROM adimlar AS a
            WHERE a.yol_haritasi_id IN (
                SELECT MAX(y.id) FROM yol_haritalari y
                JOIN sinif_uyeleri u ON u.ogrenci_id = y.kullanici_id AND u.sinif_id = y.sinif_id
                WHERE y.sinif_id = ?
                GROUP BY y.kullanici_id)
            ORDER BY a.yol_haritasi_id, a.sira
        """, (sinif_id,)).fetchall()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 23) SINIFLA PAYLAŞILAN SORULAR
# ---------------------------------------------------------------------------

def paylasilan_sorular(ogrenci_id):
    """
    Öğrencinin üye olduğu sınıfların öğretmenlerinin "sınıfla paylaş" dediği soru-cevaplar.
    Soran öğrencinin adı GETİRİLMEZ (gizlilik): sadece soru, cevap, adım başlığı ve proje.
    EXISTS: cevaplayan öğretmen, bu öğrencinin sınıflarından birinin öğretmeni mi?
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT s.id, s.soru, s.cevap, s.cevap_zamani, a.baslik, a.sira,
                   k.kullanici_adi AS ogretmen_adi
            FROM ogretmen_sorulari AS s
            JOIN adimlar      AS a ON a.id = s.adim_id
            JOIN kullanicilar AS k ON k.id = s.cevaplayan_id
            WHERE s.paylasildi = 1 AND s.cevap IS NOT NULL AND EXISTS (
                SELECT 1 FROM sinif_uyeleri u JOIN siniflar c ON c.id = u.sinif_id
                WHERE u.ogrenci_id = ? AND c.ogretmen_id = s.cevaplayan_id)
            ORDER BY s.cevap_zamani DESC
            LIMIT 30
        """, (ogrenci_id,)).fetchall()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 24) NOTLARIM: öğrencinin bütün adım notları tek yerde
# ---------------------------------------------------------------------------

def tum_notlar(kullanici_id, ara=""):
    """
    Öğrencinin not yazdığı bütün adımları, yol haritasıyla birlikte getirir (en yeni harita önce).
    ara: notta, adım başlığında ya da projede geçmesi gereken kelime (boşsa hepsi).
    """
    sorgu = """
        SELECT a.id AS adim_id, a.sira, a.baslik, a.not_metni, a.tamamlandi,
               y.id AS harita_id, y.proje
        FROM adimlar AS a
        JOIN yol_haritalari AS y ON y.id = a.yol_haritasi_id
        WHERE y.kullanici_id = ? AND a.not_metni IS NOT NULL
    """
    degerler = [kullanici_id]
    if ara:
        sorgu += """ AND (LOWER(a.not_metni) LIKE LOWER(?) OR LOWER(a.baslik) LIKE LOWER(?)
                          OR LOWER(y.proje) LIKE LOWER(?))"""
        degerler += [f"%{ara}%"] * 3
    sorgu += " ORDER BY y.id DESC, a.sira"
    baglanti = baglan()
    try:
        return baglanti.execute(sorgu, degerler).fetchall()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 25) PROFİL VE MESAJLAŞMA (sınıf sohbeti + özel mesaj)
# ---------------------------------------------------------------------------
#
# Kim kimi görebilir, kime yazabilir? Hep SINIF üzerinden:
#   - Aynı sınıftaki herkes (öğretmen + öğrenciler) birbirinin profilini görür.
#   - Öğretmen ile kendi sınıfındaki öğrenci her zaman özel mesajlaşabilir.
#   - İki öğrenci, ancak ortak bir sınıfları varsa VE o sınıfta öğretmen özel mesajı
#     kapatmadıysa (ozel_mesaj = 1) özel mesajlaşabilir.

# Kullanıcının içinde bulunduğu sınıflar: öğretmeni olduğu ya da üye olduğu (UNION tekrarları atar)
_SINIFLARI = """(SELECT id FROM siniflar WHERE ogretmen_id = :k
                  UNION SELECT sinif_id FROM sinif_uyeleri WHERE ogrenci_id = :k)"""


def hakkimda_kaydet(kullanici_id, metin):
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE kullanicilar SET hakkimda = ? WHERE id = ?", (metin or None, kullanici_id))
        baglanti.commit()
    finally:
        baglanti.close()


def kullanicinin_siniflari(kullanici_id):
    """Kullanıcının içinde olduğu bütün sınıflar (öğretmense açtıkları, öğrenciyse katıldıkları)."""
    baglanti = baglan()
    try:
        return baglanti.execute(f"""
            SELECT s.id, s.ad, s.ogretmen_id, s.sohbet_kilitli, s.ozel_mesaj
            FROM siniflar AS s WHERE s.id IN {_SINIFLARI}
            ORDER BY s.ad
        """, {"k": kullanici_id}).fetchall()
    finally:
        baglanti.close()


def sinifta_mi(kullanici_id, sinif_id):
    """Bu kullanıcı bu sınıfın öğretmeni ya da üyesi mi? Değilse None, ise sınıf satırı."""
    baglanti = baglan()
    try:
        return baglanti.execute(f"""
            SELECT s.id, s.ad, s.ogretmen_id, s.sohbet_kilitli, s.ozel_mesaj
            FROM siniflar AS s WHERE s.id = :s AND s.id IN {_SINIFLARI}
        """, {"k": kullanici_id, "s": sinif_id}).fetchone()
    finally:
        baglanti.close()


def ortak_siniflar(a, b):
    """İki kullanıcının ortak sınıfları (biri öğretmen, öteki üye de olabilir; ikisi de üye de)."""
    baglanti = baglan()
    try:
        return baglanti.execute(f"""
            SELECT s.id, s.ad, s.ogretmen_id, s.ozel_mesaj FROM siniflar AS s
            WHERE s.id IN {_SINIFLARI.replace(':k', ':a')} AND s.id IN {_SINIFLARI.replace(':k', ':b')}
            ORDER BY s.ad
        """, {"a": a, "b": b}).fetchall()
    finally:
        baglanti.close()


def mesaj_atabilecegi_kisiler(kullanici_id):
    """
    Özel mesaj atabileceği kişiler (ada göre sıralı). Üç grubun birleşimi:
    öğrencilerim (öğretmensem), öğretmenlerim, özel mesajı açık sınıflardaki sınıf arkadaşlarım.
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT k.id, k.kullanici_adi, k.rol FROM kullanicilar AS k
            WHERE k.id <> :k AND (
                k.id IN (SELECT u.ogrenci_id FROM sinif_uyeleri u
                          JOIN siniflar s ON s.id = u.sinif_id WHERE s.ogretmen_id = :k)
             OR k.id IN (SELECT s.ogretmen_id FROM siniflar s
                          JOIN sinif_uyeleri u ON u.sinif_id = s.id WHERE u.ogrenci_id = :k)
             OR k.id IN (SELECT u2.ogrenci_id FROM sinif_uyeleri u1
                          JOIN sinif_uyeleri u2 ON u2.sinif_id = u1.sinif_id
                          JOIN siniflar s ON s.id = u1.sinif_id
                          WHERE u1.ogrenci_id = :k AND s.ozel_mesaj = 1))
              -- Engelleme hangi yönde olursa olsun ikisi birbirine yazamaz
              AND NOT EXISTS (SELECT 1 FROM engellemeler e
                              WHERE (e.engelleyen_id = :k AND e.engellenen_id = k.id)
                                 OR (e.engelleyen_id = k.id AND e.engellenen_id = :k))
            ORDER BY LOWER(k.kullanici_adi)
        """, {"k": kullanici_id}).fetchall()
    finally:
        baglanti.close()


def sinif_uyeleri_listesi(sinif_id):
    """Sohbet sayfasındaki üye listesi: önce öğretmen, sonra öğrenciler (ada göre)."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT k.id, k.kullanici_adi, k.rol FROM kullanicilar k
             JOIN siniflar s ON s.ogretmen_id = k.id WHERE s.id = :s
            UNION ALL
            SELECT k.id, k.kullanici_adi, k.rol FROM kullanicilar k
             JOIN sinif_uyeleri u ON u.ogrenci_id = k.id WHERE u.sinif_id = :s
            ORDER BY rol DESC, kullanici_adi
        """, {"s": sinif_id}).fetchall()
    finally:
        baglanti.close()


def mesaj_ekle(gonderen_id, metin, sinif_id=None, alici_id=None, grup_id=None, anket_id=None, resim_id=None):
    """
    Sınıf sohbetine (sinif_id), gruba (grup_id) ya da bir kişiye (alici_id) mesaj ekler, id'sini döndürür.
    Mesaj bir anket (anket_id) ya da resim (resim_id) taşıyabilir.
    """
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        mesaj_id = baglanti.ekle(
            """INSERT INTO mesajlar (sinif_id, grup_id, gonderen_id, alici_id, metin, zaman, anket_id, resim_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sinif_id, grup_id, gonderen_id, alici_id, metin, zaman, anket_id, resim_id))
        baglanti.commit()
        return mesaj_id
    finally:
        baglanti.close()


def son_dakika_mesaj_sayisi(kullanici_id):
    """Son 60 saniyede gönderilen mesaj sayısı (art arda yüzlerce mesajla sohbeti boğmayı önler)."""
    sinir = (datetime.now() - timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT COUNT(*) FROM mesajlar WHERE gonderen_id = ? AND zaman >= ?",
                                (kullanici_id, sinir)).fetchone()[0]
    finally:
        baglanti.close()


# Sohbet listesinde son mesajın özeti: anketse "📊 Anket: soru", yazısız resimse "📷 Resim"
_SON_METIN = """CASE WHEN m.anket_id IS NOT NULL THEN '📊 Anket: ' || m.metin
                      WHEN m.resim_id IS NOT NULL AND m.metin = '' THEN '📷 Resim'
                      WHEN m.resim_id IS NOT NULL THEN '📷 ' || m.metin
                      ELSE m.metin END"""

_MESAJ_SUTUNLARI = """m.id, m.sinif_id, m.gonderen_id, m.alici_id, m.metin, m.zaman, m.silindi,
                      m.anket_id, m.resim_id,
                      k.kullanici_adi AS gonderen_adi, k.rol AS gonderen_rol"""


def sinif_mesajlari(sinif_id, sonra=0, sinir=100, izleyen_id=0):
    """
    Sınıf sohbetinin mesajları (eskiden yeniye). sonra: bu id'den SONRAKİLER (yeni mesaj kontrolü).
    izleyen_id: sohbete bakan kişi; onun engellediği kişilerin mesajları gösterilmez.
    """
    baglanti = baglan()
    try:
        # İç sorgu en yeni 'sinir' mesajı alır, dış sorgu onları eskiden yeniye çevirir
        return baglanti.execute(f"""
            SELECT * FROM (
                SELECT {_MESAJ_SUTUNLARI} FROM mesajlar m JOIN kullanicilar k ON k.id = m.gonderen_id
                WHERE m.sinif_id = :s AND m.id > :sonra
                  AND m.gonderen_id NOT IN (SELECT e.engellenen_id FROM engellemeler e
                                            WHERE e.engelleyen_id = :izleyen)
                ORDER BY m.id DESC LIMIT :sinir
            ) AS son ORDER BY id
        """, {"s": sinif_id, "sonra": sonra, "sinir": sinir, "izleyen": izleyen_id}).fetchall()
    finally:
        baglanti.close()


def ozel_mesajlar(a, b, sonra=0, sinir=100):
    """İki kişi arasındaki özel mesajlar (eskiden yeniye)."""
    baglanti = baglan()
    try:
        return baglanti.execute(f"""
            SELECT * FROM (
                SELECT {_MESAJ_SUTUNLARI} FROM mesajlar m JOIN kullanicilar k ON k.id = m.gonderen_id
                WHERE ((m.gonderen_id = :a AND m.alici_id = :b) OR (m.gonderen_id = :b AND m.alici_id = :a))
                  AND m.id > :sonra
                ORDER BY m.id DESC LIMIT :sinir
            ) AS son ORDER BY id
        """, {"a": a, "b": b, "sonra": sonra, "sinir": sinir}).fetchall()
    finally:
        baglanti.close()


def mesaj_getir(mesaj_id):
    baglanti = baglan()
    try:
        # Grup mesajında sınıf, grubun sınıfıdır (COALESCE: ilk boş olmayan değer)
        return baglanti.execute("""SELECT m.*, s.ogretmen_id FROM mesajlar m
                                   LEFT JOIN gruplar gr ON gr.id = m.grup_id
                                   LEFT JOIN siniflar s ON s.id = COALESCE(m.sinif_id, gr.sinif_id)
                                   WHERE m.id = ?""",
                                (mesaj_id,)).fetchone()
    finally:
        baglanti.close()


def mesaj_sil(mesaj_id):
    """
    Mesajı "silindi" yapar ve metnini boşaltır (satır kalır, sohbetin sırası bozulmaz).
    Mesajın anketi ya da resmi varsa onlar tamamen silinir.
    """
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE mesajlar SET silindi = 1, metin = '', anket_id = NULL, resim_id = NULL WHERE id = ?",
                         (mesaj_id,))
        _sahipsizleri_temizle(baglanti)
        baglanti.commit()
    finally:
        baglanti.close()


def _sahipsizleri_temizle(baglanti):
    """
    Hiçbir mesajın göstermediği anketleri (seçenek ve oylarıyla) ve resimleri siler.
    Mesaj, grup, sınıf ya da hesap silinince çağrılır; böylece silme kodunun her yerinde
    ayrı ayrı "bu mesajın resmi var mıydı?" diye bakmaya gerek kalmaz. (commit'i çağıran yapar)
    """
    anketsiz = "SELECT id FROM anketler WHERE id NOT IN (SELECT anket_id FROM mesajlar WHERE anket_id IS NOT NULL)"
    baglanti.execute(f"DELETE FROM anket_oylari WHERE anket_id IN ({anketsiz})")
    baglanti.execute(f"DELETE FROM anket_secenekleri WHERE anket_id IN ({anketsiz})")
    baglanti.execute(f"DELETE FROM anketler WHERE id IN ({anketsiz})")
    baglanti.execute("""DELETE FROM resimler
                        WHERE id NOT IN (SELECT resim_id FROM mesajlar WHERE resim_id IS NOT NULL)""")


def okundu_yap(kullanici_id, son_id, sinif_id=0, diger_id=0):
    """
    Sohbeti 'son_id'ye kadar okundu sayar. "UPSERT": satır yoksa ekler, varsa günceller.
    ON CONFLICT ... DO UPDATE hem SQLite'ta hem PostgreSQL'de aynı yazılıyor.
    excluded: eklenmeye çalışılan (çakışan) yeni satırın değerleri.
    """
    baglanti = baglan()
    try:
        baglanti.execute(f"""
            INSERT INTO sohbet_okuma (kullanici_id, sinif_id, diger_id, son_okunan_id) VALUES (?, ?, ?, ?)
            ON CONFLICT (kullanici_id, sinif_id, diger_id)
            DO UPDATE SET son_okunan_id = {BUYUGU}(sohbet_okuma.son_okunan_id, excluded.son_okunan_id)
        """, (kullanici_id, sinif_id, diger_id, son_id))
        baglanti.commit()
    finally:
        baglanti.close()


# Okunmamış mesaj: başkasının yazdığı, silinmemiş ve "son okunan"dan sonra gelen mesaj
_OKUNMAMIS_SINIF = """(SELECT COUNT(*) FROM mesajlar x
                        WHERE x.sinif_id = {sinif} AND x.gonderen_id <> :k AND x.silindi = 0
                          AND x.gonderen_id NOT IN (SELECT e.engellenen_id FROM engellemeler e
                                                    WHERE e.engelleyen_id = :k)
                          AND x.id > COALESCE((SELECT o.son_okunan_id FROM sohbet_okuma o
                                WHERE o.kullanici_id = :k AND o.sinif_id = {sinif} AND o.diger_id = 0), 0))"""
_OKUNMAMIS_KISI = """(SELECT COUNT(*) FROM mesajlar x
                       WHERE x.alici_id = :k AND x.gonderen_id = {kisi} AND x.silindi = 0
                         AND x.gonderen_id NOT IN (SELECT e.engellenen_id FROM engellemeler e
                                                   WHERE e.engelleyen_id = :k)
                         AND x.id > COALESCE((SELECT o.son_okunan_id FROM sohbet_okuma o
                               WHERE o.kullanici_id = :k AND o.sinif_id = 0 AND o.diger_id = {kisi}), 0))"""


# Kullanıcının görebildiği gruplar: üyesi olduğu ya da öğretmeni olduğu sınıftaki gruplar
# (Öğretmen: kendi sınıflarının proje grupları ve kendi kurduğu sohbet grupları. Öğrencilerin kurduğu
#  sohbet grupları öğretmenin mesaj listesine girmez; öğretmen onları sınıf sayfasından açıp bakabilir.)
_GRUPLARI = """(SELECT grup_id FROM grup_uyeleri WHERE ogrenci_id = :k
                UNION SELECT gr2.id FROM gruplar gr2 JOIN siniflar s2 ON s2.id = gr2.sinif_id
                      WHERE s2.ogretmen_id = :k AND (gr2.olusturan_id IS NULL OR gr2.olusturan_id = :k))"""
_OKUNMAMIS_GRUP = """(SELECT COUNT(*) FROM mesajlar x
                       WHERE x.grup_id = {grup} AND x.gonderen_id <> :k AND x.silindi = 0
                         AND x.gonderen_id NOT IN (SELECT e.engellenen_id FROM engellemeler e
                                                   WHERE e.engelleyen_id = :k)
                         AND x.id > COALESCE((SELECT o.son_okunan_id FROM grup_okuma o
                               WHERE o.kullanici_id = :k AND o.grup_id = {grup}), 0))"""


def okunmamis_mesaj_sayisi(kullanici_id):
    """Menüdeki "Mesajlar" rozeti: bütün sınıf sohbetlerindeki ve özel sohbetlerdeki okunmamışlar."""
    baglanti = baglan()
    try:
        # int(...): PostgreSQL'de SUM(COUNT) "numeric" türünde (Python'da Decimal) gelir;
        # JSON'a "0" gibi metin olarak yazılmasın diye tam sayıya çeviriyoruz.
        return int(baglanti.execute(f"""
            SELECT
              (SELECT COALESCE(SUM({_OKUNMAMIS_SINIF.format(sinif='s.id')}), 0)
                 FROM siniflar s WHERE s.id IN {_SINIFLARI})
            + (SELECT COALESCE(SUM({_OKUNMAMIS_GRUP.format(grup='gr.id')}), 0)
                 FROM gruplar gr WHERE gr.id IN {_GRUPLARI})
            + (SELECT COUNT(*) FROM grup_davetleri d WHERE d.davet_edilen_id = :k)
            + (SELECT COUNT(*) FROM mesajlar x
                WHERE x.alici_id = :k AND x.silindi = 0
                  AND x.gonderen_id NOT IN (SELECT e.engellenen_id FROM engellemeler e
                                            WHERE e.engelleyen_id = :k)
                  AND x.id > COALESCE((SELECT o.son_okunan_id FROM sohbet_okuma o
                        WHERE o.kullanici_id = :k AND o.sinif_id = 0 AND o.diger_id = x.gonderen_id), 0))
        """, {"k": kullanici_id}).fetchone()[0])
    finally:
        baglanti.close()


def sohbet_listesi(kullanici_id):
    """
    "Mesajlar" sayfası için: (sınıf sohbetleri, özel sohbetler).
    Her birinde son mesaj ve okunmamış sayısı var. Özel sohbetler en yeni mesaja göre sıralı.
    """
    baglanti = baglan()
    try:
        siniflar = baglanti.execute(f"""
            SELECT s.id, s.ad, s.sohbet_kilitli, m.id AS son_id,
                   {_SON_METIN} AS son_metin, m.zaman AS son_zaman, m.silindi AS son_silindi,
                   k.kullanici_adi AS son_gonderen,
                   {_OKUNMAMIS_SINIF.format(sinif='s.id')} AS okunmamis
            FROM siniflar s
            LEFT JOIN mesajlar m ON m.id = (SELECT MAX(id) FROM mesajlar WHERE sinif_id = s.id)
            LEFT JOIN kullanicilar k ON k.id = m.gonderen_id
            WHERE s.id IN {_SINIFLARI}
            ORDER BY COALESCE(m.id, 0) DESC, s.ad
        """, {"k": kullanici_id}).fetchall()
        # Her özel sohbetin "öteki kişisi" ve son mesajının id'si (CASE: ben gönderdiysem alıcı, değilse gönderen)
        kisiler = baglanti.execute(f"""
            SELECT t.diger_id, t.son_id, k.kullanici_adi, k.rol, {_SON_METIN} AS son_metin, m.zaman AS son_zaman,
                   m.silindi AS son_silindi, m.gonderen_id AS son_gonderen_id,
                   {_OKUNMAMIS_KISI.format(kisi='t.diger_id')} AS okunmamis
            FROM (SELECT diger_id, MAX(id) AS son_id FROM (
                      SELECT CASE WHEN gonderen_id = :k THEN alici_id ELSE gonderen_id END AS diger_id, id
                      FROM mesajlar WHERE alici_id IS NOT NULL AND (gonderen_id = :k OR alici_id = :k)
                  ) AS d GROUP BY diger_id) AS t
            JOIN mesajlar m ON m.id = t.son_id
            JOIN kullanicilar k ON k.id = t.diger_id
            ORDER BY t.son_id DESC
        """, {"k": kullanici_id}).fetchall()
        gruplar = baglanti.execute(f"""
            SELECT gr.id, gr.ad, s.ad AS sinif_adi, gr.olusturan_id, m.id AS son_id,
                   {_SON_METIN} AS son_metin, m.zaman AS son_zaman, m.silindi AS son_silindi,
                   k.kullanici_adi AS son_gonderen,
                   {_OKUNMAMIS_GRUP.format(grup='gr.id')} AS okunmamis
            FROM gruplar gr
            JOIN siniflar s ON s.id = gr.sinif_id
            LEFT JOIN mesajlar m ON m.id = (SELECT MAX(id) FROM mesajlar WHERE grup_id = gr.id)
            LEFT JOIN kullanicilar k ON k.id = m.gonderen_id
            WHERE gr.id IN {_GRUPLARI}
            ORDER BY COALESCE(m.id, 0) DESC, gr.ad
        """, {"k": kullanici_id}).fetchall()
        return siniflar, kisiler, gruplar
    finally:
        baglanti.close()


def sohbet_ayarla(sinif_id, kilitli, ozel_mesaj):
    """Öğretmenin sınıf sohbeti ayarları. (Yetki app.py'de kontrol edilir.)"""
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE siniflar SET sohbet_kilitli = ?, ozel_mesaj = ? WHERE id = ?",
                         (1 if kilitli else 0, 1 if ozel_mesaj else 0, sinif_id))
        baglanti.commit()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 26) GÜVENLİK: engelleme ve mesaj bildirme
# ---------------------------------------------------------------------------

def engelle(engelleyen_id, engellenen_id):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        baglanti.execute("""INSERT INTO engellemeler (engelleyen_id, engellenen_id, zaman) VALUES (?, ?, ?)
                            ON CONFLICT DO NOTHING""", (engelleyen_id, engellenen_id, zaman))
        # Aralarındaki bekleyen grup davetleri geçersiz olur
        baglanti.execute("""DELETE FROM grup_davetleri WHERE (davet_eden_id = ? AND davet_edilen_id = ?)
                                                          OR (davet_eden_id = ? AND davet_edilen_id = ?)""",
                         (engelleyen_id, engellenen_id, engellenen_id, engelleyen_id))
        baglanti.commit()
    finally:
        baglanti.close()


def engeli_kaldir(engelleyen_id, engellenen_id):
    baglanti = baglan()
    try:
        baglanti.execute("DELETE FROM engellemeler WHERE engelleyen_id = ? AND engellenen_id = ?",
                         (engelleyen_id, engellenen_id))
        baglanti.commit()
    finally:
        baglanti.close()


def engelledi_mi(engelleyen_id, engellenen_id):
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT 1 FROM engellemeler WHERE engelleyen_id = ? AND engellenen_id = ?",
                                (engelleyen_id, engellenen_id)).fetchone() is not None
    finally:
        baglanti.close()


def engelledikleri(kullanici_id):
    """Kullanıcının engellediği kişiler (Profilim sayfasındaki liste)."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT k.id, k.kullanici_adi FROM engellemeler e JOIN kullanicilar k ON k.id = e.engellenen_id
            WHERE e.engelleyen_id = ? ORDER BY LOWER(k.kullanici_adi)
        """, (kullanici_id,)).fetchall()
    finally:
        baglanti.close()


def sikayet_ekle(mesaj_id, bildiren_id, sebep):
    """Mesajı bildirir. Aynı kişi aynı mesajı ikinci kez bildirirse bir şey olmaz (ON CONFLICT DO NOTHING)."""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        baglanti.execute("""INSERT INTO sikayetler (mesaj_id, bildiren_id, sebep, zaman) VALUES (?, ?, ?, ?)
                            ON CONFLICT DO NOTHING""", (mesaj_id, bildiren_id, sebep, zaman))
        baglanti.commit()
    finally:
        baglanti.close()


def ogretmenin_sikayetleri(ogretmen_id):
    """
    Öğretmenin bakması gereken açık bildirimler:
      - kendi sınıfının sohbetindeki mesajlar
      - iki öğrencisi arasındaki özel mesajlar (gönderen de bildiren de onun öğrencisiyse)
    Öğretmen öğrencilerin özel sohbetlerini GÖREMEZ; sadece bildirilen o tek mesajı görür.
    """
    ogrencileri = """(SELECT u.ogrenci_id FROM sinif_uyeleri u JOIN siniflar s2 ON s2.id = u.sinif_id
                      WHERE s2.ogretmen_id = :k)"""
    baglanti = baglan()
    try:
        return baglanti.execute(f"""
            SELECT r.id, r.sebep, r.zaman, m.id AS mesaj_id, m.metin, m.resim_id, m.silindi, m.sinif_id, m.zaman AS mesaj_zamani,
                   s.ad AS sinif_adi, gr.ad AS grup_adi, g.kullanici_adi AS gonderen_adi, m.gonderen_id,
                   b.kullanici_adi AS bildiren_adi
            FROM sikayetler r
            JOIN mesajlar m     ON m.id = r.mesaj_id
            JOIN kullanicilar g ON g.id = m.gonderen_id
            JOIN kullanicilar b ON b.id = r.bildiren_id
            LEFT JOIN gruplar gr ON gr.id = m.grup_id
            LEFT JOIN siniflar s ON s.id = COALESCE(m.sinif_id, gr.sinif_id)
            WHERE r.durum = 'acik'
              AND (s.ogretmen_id = :k
                   OR (m.alici_id IS NOT NULL AND m.gonderen_id IN {ogrencileri} AND r.bildiren_id IN {ogrencileri}))
            ORDER BY r.id
        """, {"k": ogretmen_id}).fetchall()
    finally:
        baglanti.close()


def sikayetleri_kapat(mesaj_id):
    """Bir mesajla ilgili bütün açık bildirimleri kapatır (öğretmen baktı)."""
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE sikayetler SET durum = 'kapandi' WHERE mesaj_id = ?", (mesaj_id,))
        baglanti.commit()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 27) MİNİ QUIZ
# ---------------------------------------------------------------------------

def quiz_kaydet(adim_id, sorular_json):
    """Adımın quizini kaydeder; varsa yenisiyle değiştirir (cevaplar silinir, üretim sayısı artar)."""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        baglanti.execute("""
            INSERT INTO quizler (adim_id, sorular, olusturma_zamani) VALUES (?, ?, ?)
            ON CONFLICT (adim_id) DO UPDATE SET sorular = excluded.sorular, cevaplar = NULL,
                dogru_sayisi = NULL, cevap_zamani = NULL, olusturma_zamani = excluded.olusturma_zamani,
                uretim_sayisi = quizler.uretim_sayisi + 1
        """, (adim_id, sorular_json, zaman))
        baglanti.commit()
    finally:
        baglanti.close()


def quiz_getir(adim_id):
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT * FROM quizler WHERE adim_id = ?", (adim_id,)).fetchone()
    finally:
        baglanti.close()


def quiz_cevapla(adim_id, cevaplar_json, dogru_sayisi):
    """Cevapları kaydeder. Zaten cevaplanmışsa değiştirmez (aynı soruları tekrar tekrar deneyip puanı düzeltemesin)."""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        imlec = baglanti.execute("""UPDATE quizler SET cevaplar = ?, dogru_sayisi = ?, cevap_zamani = ?
                                    WHERE adim_id = ? AND cevaplar IS NULL""",
                                 (cevaplar_json, dogru_sayisi, zaman, adim_id))
        baglanti.commit()
        return imlec.rowcount > 0
    finally:
        baglanti.close()


def yol_haritasinin_quizleri(harita_id):
    """{adim_id: quiz satırı} sözlüğü."""
    baglanti = baglan()
    try:
        satirlar = baglanti.execute("""
            SELECT q.* FROM quizler q JOIN adimlar a ON a.id = q.adim_id WHERE a.yol_haritasi_id = ?
        """, (harita_id,)).fetchall()
    finally:
        baglanti.close()
    return {s["adim_id"]: s for s in satirlar}


# ---------------------------------------------------------------------------
# 28) ÖDEVLER VE TESLİMLER
# ---------------------------------------------------------------------------

def odev_ekle(sinif_id, baslik, aciklama, son_tarih):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        odev_id = baglanti.ekle("""INSERT INTO odevler (sinif_id, baslik, aciklama, son_tarih, olusturma_zamani)
                                   VALUES (?, ?, ?, ?, ?)""", (sinif_id, baslik, aciklama or None, son_tarih, zaman))
        baglanti.commit()
        return odev_id
    finally:
        baglanti.close()


def odev_getir(odev_id):
    """Ödev + sınıfın adı ve öğretmeni (yetki kontrolü için)."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT o.*, s.ad AS sinif_adi, s.ogretmen_id FROM odevler o JOIN siniflar s ON s.id = o.sinif_id
            WHERE o.id = ?
        """, (odev_id,)).fetchone()
    finally:
        baglanti.close()


def odev_sil(odev_id):
    baglanti = baglan()
    try:
        baglanti.execute("DELETE FROM teslimler WHERE odev_id = ?", (odev_id,))
        baglanti.execute("DELETE FROM odevler WHERE id = ?", (odev_id,))
        baglanti.commit()
    finally:
        baglanti.close()


def sinifin_odevleri(sinif_id):
    """Öğretmenin sınıf sayfası: ödevler, teslim ve puanlanan sayısıyla (son tarihe göre)."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT o.*,
                   (SELECT COUNT(*) FROM teslimler t JOIN sinif_uyeleri u
                      ON u.ogrenci_id = t.ogrenci_id AND u.sinif_id = o.sinif_id
                     WHERE t.odev_id = o.id)                       AS teslim_sayisi,
                   (SELECT COUNT(*) FROM teslimler t JOIN sinif_uyeleri u
                      ON u.ogrenci_id = t.ogrenci_id AND u.sinif_id = o.sinif_id
                     WHERE t.odev_id = o.id AND t.puan IS NULL)    AS bekleyen_sayisi
            FROM odevler o WHERE o.sinif_id = ? ORDER BY o.son_tarih DESC, o.id DESC
        """, (sinif_id,)).fetchall()
    finally:
        baglanti.close()


def odevin_teslimleri(odev_id):
    """
    Öğretmen için: sınıftaki HER öğrenci ve (varsa) teslimi. LEFT JOIN: teslim etmeyenler de
    listede kalsın (teslim sütunları boş gelir).
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT k.id AS ogrenci_id, k.kullanici_adi, t.id AS teslim_id, t.metin, t.baglanti, t.zaman,
                   t.puan, t.yorum
            FROM odevler o
            JOIN sinif_uyeleri u ON u.sinif_id = o.sinif_id
            JOIN kullanicilar k  ON k.id = u.ogrenci_id
            LEFT JOIN teslimler t ON t.odev_id = o.id AND t.ogrenci_id = k.id
            WHERE o.id = ?
            ORDER BY (t.id IS NULL), LOWER(k.kullanici_adi)
        """, (odev_id,)).fetchall()
    finally:
        baglanti.close()


def ogrencinin_odevleri(ogrenci_id):
    """Öğrencinin bütün sınıflarındaki ödevler ve kendi teslimi (son tarihi yakın olan önce)."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT o.id, o.baslik, o.son_tarih, s.ad AS sinif_adi,
                   t.id AS teslim_id, t.zaman AS teslim_zamani, t.puan, t.goruldu
            FROM odevler o
            JOIN sinif_uyeleri u ON u.sinif_id = o.sinif_id AND u.ogrenci_id = :k
            JOIN siniflar s      ON s.id = o.sinif_id
            LEFT JOIN teslimler t ON t.odev_id = o.id AND t.ogrenci_id = :k
            ORDER BY o.son_tarih DESC, o.id DESC
        """, {"k": ogrenci_id}).fetchall()
    finally:
        baglanti.close()


def teslim_getir(odev_id, ogrenci_id):
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT * FROM teslimler WHERE odev_id = ? AND ogrenci_id = ?",
                                (odev_id, ogrenci_id)).fetchone()
    finally:
        baglanti.close()


def teslim_kaydet(odev_id, ogrenci_id, metin, baglanti_adresi):
    """Teslim eder ya da (puanlanmadıysa) teslimi günceller. Puanlanmışsa False döner."""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        eski = baglanti.execute("SELECT puan FROM teslimler WHERE odev_id = ? AND ogrenci_id = ?",
                                (odev_id, ogrenci_id)).fetchone()
        if eski is not None and eski["puan"] is not None:
            return False
        baglanti.execute("""
            INSERT INTO teslimler (odev_id, ogrenci_id, metin, baglanti, zaman) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (odev_id, ogrenci_id) DO UPDATE
              SET metin = excluded.metin, baglanti = excluded.baglanti, zaman = excluded.zaman
        """, (odev_id, ogrenci_id, metin or None, baglanti_adresi or None, zaman))
        baglanti.commit()
        return True
    finally:
        baglanti.close()


def teslim_puanla(teslim_id, puan, yorum):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        baglanti.execute("""UPDATE teslimler SET puan = ?, yorum = ?, degerlendirme_zamani = ?, goruldu = 0
                            WHERE id = ?""", (puan, yorum or None, zaman, teslim_id))
        baglanti.commit()
    finally:
        baglanti.close()


def teslim_bilgisi(teslim_id):
    """Teslim + ödevin sınıfının öğretmeni (puanlama yetkisi için)."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT t.*, o.sinif_id, s.ogretmen_id FROM teslimler t
            JOIN odevler o ON o.id = t.odev_id JOIN siniflar s ON s.id = o.sinif_id WHERE t.id = ?
        """, (teslim_id,)).fetchone()
    finally:
        baglanti.close()


def teslimi_goruldu_yap(odev_id, ogrenci_id):
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE teslimler SET goruldu = 1 WHERE odev_id = ? AND ogrenci_id = ?",
                         (odev_id, ogrenci_id))
        baglanti.commit()
    finally:
        baglanti.close()


def bekleyen_odev_sayisi(ogrenci_id, bugun):
    """Menüdeki "Ödevler" rozeti: süresi geçmemiş, teslim edilmemiş ödevler + görülmemiş puanlar."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT
              (SELECT COUNT(*) FROM odevler o
                 JOIN sinif_uyeleri u ON u.sinif_id = o.sinif_id AND u.ogrenci_id = :k
                WHERE o.son_tarih >= :bugun
                  AND NOT EXISTS (SELECT 1 FROM teslimler t WHERE t.odev_id = o.id AND t.ogrenci_id = :k))
            + (SELECT COUNT(*) FROM teslimler t WHERE t.ogrenci_id = :k AND t.goruldu = 0)
        """, {"k": ogrenci_id, "bugun": bugun}).fetchone()[0]
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 29) GRUP PROJELERİ: gruplar, görev panosu, grup sohbeti
# ---------------------------------------------------------------------------

def grup_olustur(sinif_id, ad, proje, ogrenci_idleri):
    """Grubu kurar ve seçilen öğrencileri ekler (sadece o sınıfın üyeleri eklenir)."""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        grup_id = baglanti.ekle("INSERT INTO gruplar (sinif_id, ad, proje, olusturma_zamani) VALUES (?, ?, ?, ?)",
                                (sinif_id, ad, proje or None, zaman))
        for ogrenci_id in ogrenci_idleri:
            baglanti.execute("""INSERT INTO grup_uyeleri (grup_id, ogrenci_id)
                                SELECT ?, ? WHERE EXISTS (SELECT 1 FROM sinif_uyeleri
                                                          WHERE sinif_id = ? AND ogrenci_id = ?)
                                ON CONFLICT DO NOTHING""", (grup_id, ogrenci_id, sinif_id, ogrenci_id))
        baglanti.commit()
        return grup_id
    finally:
        baglanti.close()


def grup_getir(grup_id):
    """Grup + sınıfın adı ve öğretmeni."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT gr.*, s.ad AS sinif_adi, s.ogretmen_id FROM gruplar gr JOIN siniflar s ON s.id = gr.sinif_id
            WHERE gr.id = ?
        """, (grup_id,)).fetchone()
    finally:
        baglanti.close()


def grup_uyeleri_listesi(grup_id):
    """Grubun üyeleri; sohbet sayfası için öğretmen de başa eklenir."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT k.id, k.kullanici_adi, k.rol FROM kullanicilar k
              JOIN siniflar s ON s.ogretmen_id = k.id JOIN gruplar gr ON gr.sinif_id = s.id WHERE gr.id = :g
            UNION ALL
            SELECT k.id, k.kullanici_adi, k.rol FROM kullanicilar k
              JOIN grup_uyeleri u ON u.ogrenci_id = k.id WHERE u.grup_id = :g
            ORDER BY rol DESC, kullanici_adi
        """, {"g": grup_id}).fetchall()
    finally:
        baglanti.close()


def grubu_gorebilir_mi(kullanici_id, grup_id):
    """Grup sayfasını kim açabilir? Grubun üyesi ve sınıfın öğretmeni. Değilse None, ise grup satırı."""
    grup = grup_getir(grup_id)
    if grup is None:
        return None
    if grup["ogretmen_id"] == kullanici_id:
        return grup
    baglanti = baglan()
    try:
        uye = baglanti.execute("SELECT 1 FROM grup_uyeleri WHERE grup_id = ? AND ogrenci_id = ?",
                               (grup_id, kullanici_id)).fetchone()
    finally:
        baglanti.close()
    return grup if uye else None


def sinifin_gruplari(sinif_id):
    """Öğretmenin sınıf sayfası: gruplar, üyeleri (virgülle) ve görev ilerlemesi."""
    baglanti = baglan()
    try:
        gruplar = baglanti.execute("""
            SELECT gr.id, gr.ad, gr.proje,
                   (SELECT COUNT(*) FROM gorevler g WHERE g.grup_id = gr.id)                      AS gorev_sayisi,
                   (SELECT COUNT(*) FROM gorevler g WHERE g.grup_id = gr.id AND g.durum = 'bitti') AS biten_gorev
            FROM gruplar gr WHERE gr.sinif_id = ? AND gr.olusturan_id IS NULL ORDER BY gr.ad
        """, (sinif_id,)).fetchall()
        uyeler = baglanti.execute("""
            SELECT u.grup_id, k.kullanici_adi FROM grup_uyeleri u JOIN kullanicilar k ON k.id = u.ogrenci_id
            JOIN gruplar gr ON gr.id = u.grup_id WHERE gr.sinif_id = ? ORDER BY LOWER(k.kullanici_adi)
        """, (sinif_id,)).fetchall()
    finally:
        baglanti.close()
    adlar = {}
    for u in uyeler:
        adlar.setdefault(u["grup_id"], []).append(u["kullanici_adi"])
    return [{**dict(gr), "uyeler": adlar.get(gr["id"], [])} for gr in gruplar]


def ogrencinin_gruplari(ogrenci_id):
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT gr.id, gr.ad, gr.sinif_id, s.ad AS sinif_adi FROM grup_uyeleri u
            JOIN gruplar gr ON gr.id = u.grup_id JOIN siniflar s ON s.id = gr.sinif_id
            WHERE u.ogrenci_id = ? AND gr.olusturan_id IS NULL ORDER BY gr.ad
        """, (ogrenci_id,)).fetchall()
    finally:
        baglanti.close()


def _grubu_sil(baglanti, grup_id):
    """Grubu, sohbetini, görevlerini ve bildirimlerini siler (commit'i çağıran yapar)."""
    baglanti.execute("DELETE FROM sikayetler WHERE mesaj_id IN (SELECT id FROM mesajlar WHERE grup_id = ?)",
                     (grup_id,))
    for tablo in ("mesajlar", "gorevler", "grup_uyeleri", "grup_okuma", "grup_davetleri"):
        baglanti.execute(f"DELETE FROM {tablo} WHERE grup_id = ?", (grup_id,))
    _sahipsizleri_temizle(baglanti)
    baglanti.execute("DELETE FROM gruplar WHERE id = ?", (grup_id,))


def grup_sil(grup_id):
    baglanti = baglan()
    try:
        _grubu_sil(baglanti, grup_id)
        baglanti.commit()
    finally:
        baglanti.close()


def _yoneticiligi_devret(baglanti, kullanici_id, sinif_id=None):
    """
    Kullanıcı kurduğu sohbet grubundan çıktıysa (sınıftan ayrıldı ya da hesabını sildi)
    yöneticilik gruptaki başka bir üyeye geçer; kimse kalmadıysa grup silinir.
    sinif_id verilirse sadece o sınıftaki gruplara bakılır. (commit'i çağıran yapar)
    """
    sorgu = "SELECT id FROM gruplar WHERE olusturan_id = ?"
    degerler = [kullanici_id]
    if sinif_id is not None:
        sorgu += " AND sinif_id = ?"
        degerler.append(sinif_id)
    for satir in baglanti.execute(sorgu, degerler).fetchall():
        yeni = baglanti.execute("""SELECT MIN(ogrenci_id) FROM grup_uyeleri
                                   WHERE grup_id = ? AND ogrenci_id <> ?""",
                                (satir["id"], kullanici_id)).fetchone()[0]
        if yeni is None:
            _grubu_sil(baglanti, satir["id"])
        else:
            baglanti.execute("UPDATE gruplar SET olusturan_id = ? WHERE id = ?", (yeni, satir["id"]))


# ---------------------------------------------------------------------------
# 29b) SOHBET GRUPLARI: kullanıcıların sınıf arkadaşlarıyla kendi kurduğu gruplar
# ---------------------------------------------------------------------------
#
# Kurallar (özel mesajla aynı):
#   - Grup bir sınıfın içinde kurulur; üyeler o sınıfın öğrencileridir.
#   - Öğrenci grup kuracaksa, o sınıfta öğretmen öğrenciler arası mesajı açık bırakmış olmalı.
#   - Engelleme hangi yönde olursa olsun, engelli kişi gruba eklenemez.
#   - Sınıfın öğretmeni gruptaki mesajları görebilir ve silebilir (çocukların güvenliği için).

def grup_eklenebilecekler(kullanici_id, sinif_id, grup_id=0):
    """
    Kullanıcının bu sınıfta gruba ekleyebileceği öğrenciler (ada göre).
    grup_id verilirse, o grupta zaten olanlar listeye girmez.
    Öğrenci için sınıfın özel mesaj ayarı kapalıysa liste boştur.
    """
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT k.id, k.kullanici_adi FROM kullanicilar k
            JOIN sinif_uyeleri u ON u.ogrenci_id = k.id AND u.sinif_id = :s
            JOIN siniflar s ON s.id = u.sinif_id
            WHERE k.id <> :k
              AND (s.ogretmen_id = :k OR (s.ozel_mesaj = 1 AND EXISTS
                     (SELECT 1 FROM sinif_uyeleri b WHERE b.sinif_id = :s AND b.ogrenci_id = :k)))
              AND NOT EXISTS (SELECT 1 FROM engellemeler e
                              WHERE (e.engelleyen_id = :k AND e.engellenen_id = k.id)
                                 OR (e.engelleyen_id = k.id AND e.engellenen_id = :k))
              AND NOT EXISTS (SELECT 1 FROM grup_uyeleri gu WHERE gu.grup_id = :g AND gu.ogrenci_id = k.id)
              AND NOT EXISTS (SELECT 1 FROM grup_davetleri d WHERE d.grup_id = :g AND d.davet_edilen_id = k.id)
            ORDER BY LOWER(k.kullanici_adi)
        """, {"k": kullanici_id, "s": sinif_id, "g": grup_id}).fetchall()
    finally:
        baglanti.close()


def grup_kurabilecegi_siniflar(kullanici_id):
    """Sohbet grubu kurabileceği sınıflar: öğretmeniyse hepsi, öğrenciyse özel mesajı açık olanlar."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT s.id, s.ad FROM siniflar s
            WHERE s.ogretmen_id = :k
               OR (s.ozel_mesaj = 1 AND s.id IN (SELECT sinif_id FROM sinif_uyeleri WHERE ogrenci_id = :k))
            ORDER BY s.ad
        """, {"k": kullanici_id}).fetchall()
    finally:
        baglanti.close()


def kurdugu_grup_sayisi(kullanici_id):
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT COUNT(*) FROM gruplar WHERE olusturan_id = ?",
                                (kullanici_id,)).fetchone()[0]
    finally:
        baglanti.close()


def sohbet_grubu_kur(olusturan_id, sinif_id, ad, davet_idleri, ogrenci_mi):
    """
    Sohbet grubunu kurar, id'sini döndürür. Kuran öğrenciyse kendisi üye olur;
    seçilen kişilere DAVET gider (kabul edince üye olurlar).
    davet_idleri app.py'de grup_eklenebilecekler ile süzülmüş olmalı.
    """
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        grup_id = baglanti.ekle("""INSERT INTO gruplar (sinif_id, ad, olusturma_zamani, olusturan_id)
                                   VALUES (?, ?, ?, ?)""", (sinif_id, ad, zaman, olusturan_id))
        if ogrenci_mi:
            baglanti.execute("INSERT INTO grup_uyeleri (grup_id, ogrenci_id) VALUES (?, ?)", (grup_id, olusturan_id))
        for kisi_id in sorted(set(davet_idleri) - {olusturan_id}):
            baglanti.execute("""INSERT INTO grup_davetleri (grup_id, davet_edilen_id, davet_eden_id, zaman)
                                VALUES (?, ?, ?, ?)""", (grup_id, kisi_id, olusturan_id, zaman))
        baglanti.commit()
        return grup_id
    finally:
        baglanti.close()


def gruptan_cikar(grup_id, ogrenci_id):
    """
    Üyeyi gruptan çıkarır (ya da üye kendisi ayrılır). Görev atamaları boşalır.
    Çıkan kişi yöneticiyse yöneticilik başka üyeye geçer; kimse kalmadıysa grup silinir.
    """
    baglanti = baglan()
    try:
        baglanti.execute("DELETE FROM grup_uyeleri WHERE grup_id = ? AND ogrenci_id = ?", (grup_id, ogrenci_id))
        baglanti.execute("DELETE FROM grup_okuma WHERE grup_id = ? AND kullanici_id = ?", (grup_id, ogrenci_id))
        baglanti.execute("UPDATE gorevler SET atanan_id = NULL WHERE grup_id = ? AND atanan_id = ?",
                         (grup_id, ogrenci_id))
        grup = baglanti.execute("SELECT olusturan_id FROM gruplar WHERE id = ?", (grup_id,)).fetchone()
        if grup and grup["olusturan_id"] == ogrenci_id:
            yeni = baglanti.execute("SELECT MIN(ogrenci_id) FROM grup_uyeleri WHERE grup_id = ?",
                                    (grup_id,)).fetchone()[0]
            if yeni is None:
                _grubu_sil(baglanti, grup_id)
            else:
                baglanti.execute("UPDATE gruplar SET olusturan_id = ? WHERE id = ?", (yeni, grup_id))
        baglanti.commit()
    finally:
        baglanti.close()


def grup_adini_degistir(grup_id, ad):
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE gruplar SET ad = ? WHERE id = ?", (ad, grup_id))
        baglanti.commit()
    finally:
        baglanti.close()


def sinifin_sohbet_gruplari(sinif_id):
    """Öğretmenin sınıf sayfası için: öğrencilerin kurduğu sohbet grupları, kuranı ve üye sayısı."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT gr.id, gr.ad, k.kullanici_adi AS kuran,
                   (SELECT COUNT(*) FROM grup_uyeleri u WHERE u.grup_id = gr.id) AS uye_sayisi
            FROM gruplar gr
            JOIN siniflar s ON s.id = gr.sinif_id
            JOIN kullanicilar k ON k.id = gr.olusturan_id
            WHERE gr.sinif_id = ? AND gr.olusturan_id IS NOT NULL AND gr.olusturan_id <> s.ogretmen_id
            ORDER BY gr.ad
        """, (sinif_id,)).fetchall()
    finally:
        baglanti.close()


def grup_gorevleri(grup_id):
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT g.*, k.kullanici_adi AS atanan_adi FROM gorevler g
            LEFT JOIN kullanicilar k ON k.id = g.atanan_id
            WHERE g.grup_id = ? ORDER BY g.id
        """, (grup_id,)).fetchall()
    finally:
        baglanti.close()


def gorev_ekle(grup_id, metin, atanan_id, olusturan_id):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        baglanti.execute("""INSERT INTO gorevler (grup_id, metin, atanan_id, olusturan_id, zaman)
                            VALUES (?, ?, ?, ?, ?)""", (grup_id, metin, atanan_id, olusturan_id, zaman))
        baglanti.commit()
    finally:
        baglanti.close()


def gorev_getir(gorev_id):
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT * FROM gorevler WHERE id = ?", (gorev_id,)).fetchone()
    finally:
        baglanti.close()


def gorev_guncelle(gorev_id, durum, atanan_id):
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE gorevler SET durum = ?, atanan_id = ? WHERE id = ?", (durum, atanan_id, gorev_id))
        baglanti.commit()
    finally:
        baglanti.close()


def gorev_sil(gorev_id):
    baglanti = baglan()
    try:
        baglanti.execute("DELETE FROM gorevler WHERE id = ?", (gorev_id,))
        baglanti.commit()
    finally:
        baglanti.close()


def grup_mesajlari(grup_id, sonra=0, sinir=100, izleyen_id=0):
    """Grup sohbetinin mesajları (eskiden yeniye); izleyenin engellediklerininki gösterilmez."""
    baglanti = baglan()
    try:
        return baglanti.execute(f"""
            SELECT * FROM (
                SELECT {_MESAJ_SUTUNLARI} FROM mesajlar m JOIN kullanicilar k ON k.id = m.gonderen_id
                WHERE m.grup_id = :g AND m.id > :sonra
                  AND m.gonderen_id NOT IN (SELECT e.engellenen_id FROM engellemeler e
                                            WHERE e.engelleyen_id = :izleyen)
                ORDER BY m.id DESC LIMIT :sinir
            ) AS son ORDER BY id
        """, {"g": grup_id, "sonra": sonra, "sinir": sinir, "izleyen": izleyen_id}).fetchall()
    finally:
        baglanti.close()


def grup_mesaji_ekle(gonderen_id, grup_id, metin):
    return mesaj_ekle(gonderen_id, metin, grup_id=grup_id)


# ---------------------------------------------------------------------------
# 29c) ANKETLER
# ---------------------------------------------------------------------------

def anket_olustur(olusturan_id, soru, secenekler, coklu, bitis):
    """Anketi ve seçeneklerini kaydeder, anketin id'sini döndürür (mesajı app.py ekler)."""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        anket_id = baglanti.ekle("""INSERT INTO anketler (olusturan_id, soru, coklu, bitis, zaman)
                                    VALUES (?, ?, ?, ?, ?)""", (olusturan_id, soru, 1 if coklu else 0, bitis, zaman))
        for sira, metin in enumerate(secenekler, start=1):
            baglanti.execute("INSERT INTO anket_secenekleri (anket_id, sira, metin) VALUES (?, ?, ?)",
                             (anket_id, sira, metin))
        baglanti.commit()
        return anket_id
    finally:
        baglanti.close()


def anketler_bilgisi(anket_idleri, kullanici_id):
    """
    Anketlerin soruları, seçenekleri, oy sayıları ve kullanıcının kendi oyları.
    {anket_id: {"satir": anket, "secenekler": [...], "oy_veren": kişi sayısı}} döndürür.
    Bir sohbetteki bütün anketler tek seferde okunur (her anket için ayrı sorgu yerine).
    """
    if not anket_idleri:
        return {}
    idler = ", ".join(str(int(i)) for i in anket_idleri)        # int(): sadece sayı girebilir
    baglanti = baglan()
    try:
        anketler = baglanti.execute(f"SELECT * FROM anketler WHERE id IN ({idler})").fetchall()
        secenekler = baglanti.execute(f"""
            SELECT s.id, s.anket_id, s.metin,
                   (SELECT COUNT(*) FROM anket_oylari o WHERE o.secenek_id = s.id) AS oy,
                   (SELECT COUNT(*) FROM anket_oylari o WHERE o.secenek_id = s.id AND o.kullanici_id = ?) AS benim
            FROM anket_secenekleri s WHERE s.anket_id IN ({idler}) ORDER BY s.anket_id, s.sira
        """, (kullanici_id,)).fetchall()
        oy_verenler = baglanti.execute(f"""
            SELECT anket_id, COUNT(DISTINCT kullanici_id) AS sayi FROM anket_oylari
            WHERE anket_id IN ({idler}) GROUP BY anket_id
        """).fetchall()
    finally:
        baglanti.close()
    sonuc = {a["id"]: {"satir": a, "secenekler": [], "oy_veren": 0} for a in anketler}
    for s in secenekler:
        sonuc[s["anket_id"]]["secenekler"].append(s)
    for o in oy_verenler:
        sonuc[o["anket_id"]]["oy_veren"] = int(o["sayi"])
    return sonuc


def anket_mesaji(anket_id):
    """Anketin bulunduğu mesaj (+ sınıfın öğretmeni), yetki kontrolü için. Yoksa None."""
    baglanti = baglan()
    try:
        satir = baglanti.execute("SELECT id FROM mesajlar WHERE anket_id = ? AND silindi = 0",
                                 (anket_id,)).fetchone()
    finally:
        baglanti.close()
    return mesaj_getir(satir["id"]) if satir else None


def oy_ver(anket_id, kullanici_id, secenek_idleri):
    """Kullanıcının bu anketteki oylarını verilen seçeneklerle değiştirir (oy değiştirmek serbest)."""
    baglanti = baglan()
    try:
        baglanti.execute("DELETE FROM anket_oylari WHERE anket_id = ? AND kullanici_id = ?", (anket_id, kullanici_id))
        for secenek_id in secenek_idleri:
            baglanti.execute("""INSERT INTO anket_oylari (anket_id, secenek_id, kullanici_id)
                                SELECT ?, ?, ? WHERE EXISTS (SELECT 1 FROM anket_secenekleri
                                                             WHERE id = ? AND anket_id = ?)""",
                             (anket_id, secenek_id, kullanici_id, secenek_id, anket_id))
        baglanti.commit()
    finally:
        baglanti.close()


def anketi_kapat(anket_id):
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE anketler SET kapali = 1 WHERE id = ?", (anket_id,))
        baglanti.commit()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 29d) RESİMLER
# ---------------------------------------------------------------------------

def resim_ekle(sahip_id, veri, tur):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        resim_id = baglanti.ekle("INSERT INTO resimler (sahip_id, veri, tur, boyut, zaman) VALUES (?, ?, ?, ?, ?)",
                                 (sahip_id, veri, tur, len(veri), zaman))
        baglanti.commit()
        return resim_id
    finally:
        baglanti.close()


def resim_getir(resim_id):
    """Resim + onu gösteren (silinmemiş) mesajın id'si. Yoksa None."""
    baglanti = baglan()
    try:
        return baglanti.execute("""SELECT r.veri, r.tur, m.id AS mesaj_id FROM resimler r
                                   JOIN mesajlar m ON m.resim_id = r.id AND m.silindi = 0
                                   WHERE r.id = ?""", (resim_id,)).fetchone()
    finally:
        baglanti.close()


def resim_sayilari(kullanici_id):
    """(bugün yüklediği resim sayısı, saklanan toplam resim sayısı) - kota için."""
    bugun = datetime.now().strftime("%Y-%m-%d")
    baglanti = baglan()
    try:
        satir = baglanti.execute("""SELECT COUNT(*) AS toplam,
                                           COALESCE(SUM(CASE WHEN zaman >= ? THEN 1 ELSE 0 END), 0) AS bugun
                                    FROM resimler WHERE sahip_id = ?""", (bugun, kullanici_id)).fetchone()
        return int(satir["bugun"]), int(satir["toplam"])
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 29e) GRUP DAVETLERİ
# ---------------------------------------------------------------------------

def davet_et(grup_id, davet_eden_id, kisi_idleri):
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        for kisi_id in kisi_idleri:
            baglanti.execute("""INSERT INTO grup_davetleri (grup_id, davet_edilen_id, davet_eden_id, zaman)
                                VALUES (?, ?, ?, ?) ON CONFLICT DO NOTHING""",
                             (grup_id, kisi_id, davet_eden_id, zaman))
        baglanti.commit()
    finally:
        baglanti.close()


def davetlerim(kullanici_id):
    """Kullanıcıya gelen bekleyen davetler (grubun adı, sınıfı, davet eden)."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT d.grup_id, gr.ad AS grup_adi, s.ad AS sinif_adi, k.kullanici_adi AS davet_eden, d.zaman,
                   (SELECT COUNT(*) FROM grup_uyeleri u WHERE u.grup_id = d.grup_id) AS uye_sayisi
            FROM grup_davetleri d
            JOIN gruplar gr ON gr.id = d.grup_id
            JOIN siniflar s ON s.id = gr.sinif_id
            JOIN kullanicilar k ON k.id = d.davet_eden_id
            WHERE d.davet_edilen_id = ? ORDER BY d.zaman DESC
        """, (kullanici_id,)).fetchall()
    finally:
        baglanti.close()


def davet_getir(grup_id, kullanici_id):
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT * FROM grup_davetleri WHERE grup_id = ? AND davet_edilen_id = ?",
                                (grup_id, kullanici_id)).fetchone()
    finally:
        baglanti.close()


def daveti_kabul_et(grup_id, kullanici_id):
    baglanti = baglan()
    try:
        baglanti.execute("DELETE FROM grup_davetleri WHERE grup_id = ? AND davet_edilen_id = ?", (grup_id, kullanici_id))
        baglanti.execute("INSERT INTO grup_uyeleri (grup_id, ogrenci_id) VALUES (?, ?) ON CONFLICT DO NOTHING",
                         (grup_id, kullanici_id))
        baglanti.commit()
    finally:
        baglanti.close()


def davet_sil(grup_id, kullanici_id):
    """Daveti reddeder ya da (yönetici) geri çeker."""
    baglanti = baglan()
    try:
        baglanti.execute("DELETE FROM grup_davetleri WHERE grup_id = ? AND davet_edilen_id = ?", (grup_id, kullanici_id))
        baglanti.commit()
    finally:
        baglanti.close()


def grubun_davetleri(grup_id):
    """Grup sayfası için: henüz cevap vermemiş davetliler."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT k.id, k.kullanici_adi FROM grup_davetleri d JOIN kullanicilar k ON k.id = d.davet_edilen_id
            WHERE d.grup_id = ? ORDER BY LOWER(k.kullanici_adi)
        """, (grup_id,)).fetchall()
    finally:
        baglanti.close()


def yonetici_yap(grup_id, uye_id):
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE gruplar SET olusturan_id = ? WHERE id = ?", (uye_id, grup_id))
        baglanti.commit()
    finally:
        baglanti.close()


def grup_okundu_yap(kullanici_id, grup_id, son_id):
    baglanti = baglan()
    try:
        baglanti.execute(f"""
            INSERT INTO grup_okuma (kullanici_id, grup_id, son_okunan_id) VALUES (?, ?, ?)
            ON CONFLICT (kullanici_id, grup_id)
            DO UPDATE SET son_okunan_id = {BUYUGU}(grup_okuma.son_okunan_id, excluded.son_okunan_id)
        """, (kullanici_id, grup_id, son_id))
        baglanti.commit()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 30) ÖĞRETMEN ARAÇLARI: proje şablonları, katılım, takvim
# ---------------------------------------------------------------------------

def sablon_kaydet(ogretmen_id, ad, adimlar, sablon_id=None):
    """Yeni şablon ekler ya da (sablon_id verilirse ve öğretmenin kendisininse) günceller."""
    zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        if sablon_id:
            baglanti.execute("UPDATE sablonlar SET ad = ?, adimlar = ? WHERE id = ? AND ogretmen_id = ?",
                             (ad, adimlar, sablon_id, ogretmen_id))
        else:
            sablon_id = baglanti.ekle("""INSERT INTO sablonlar (ogretmen_id, ad, adimlar, olusturma_zamani)
                                         VALUES (?, ?, ?, ?)""", (ogretmen_id, ad, adimlar, zaman))
        baglanti.commit()
        return sablon_id
    finally:
        baglanti.close()


def ogretmenin_sablonlari(ogretmen_id):
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT t.*, (SELECT COUNT(*) FROM siniflar s WHERE s.sablon_id = t.id) AS sinif_sayisi
            FROM sablonlar t WHERE t.ogretmen_id = ? ORDER BY LOWER(t.ad)
        """, (ogretmen_id,)).fetchall()
    finally:
        baglanti.close()


def sablon_getir(sablon_id):
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT * FROM sablonlar WHERE id = ?", (sablon_id,)).fetchone()
    finally:
        baglanti.close()


def sablon_sil(sablon_id):
    """Şablonu siler; onu kullanan sınıflar yapay zekâya döner. Çıkarılmış yol haritaları kalır."""
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE siniflar SET sablon_id = NULL WHERE sablon_id = ?", (sablon_id,))
        baglanti.execute("DELETE FROM sablonlar WHERE id = ?", (sablon_id,))
        baglanti.commit()
    finally:
        baglanti.close()


def sinif_sablonu_ayarla(sinif_id, sablon_id):
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE siniflar SET sablon_id = ? WHERE id = ?", (sablon_id, sinif_id))
        baglanti.commit()
    finally:
        baglanti.close()


def son_giris_guncelle(kullanici_id, gun):
    """Kullanıcının son giriş gününü yazar (sadece gün değiştiyse; her istekte yazmamak için)."""
    baglanti = baglan()
    try:
        baglanti.execute("""UPDATE kullanicilar SET son_giris = ?
                            WHERE id = ? AND (son_giris IS NULL OR son_giris <> ?)""", (gun, kullanici_id, gun))
        baglanti.commit()
    finally:
        baglanti.close()


def takvim_hedefleri(kullanici_id, bas, son):
    """Öğrencinin hedef tarihi [bas, son] aralığındaki adımları (bitenler dahil)."""
    baglanti = baglan()
    try:
        return baglanti.execute("""
            SELECT a.id AS adim_id, a.baslik, a.sira, a.hedef_tarih, a.tamamlandi, y.id AS harita_id
            FROM adimlar a JOIN yol_haritalari y ON y.id = a.yol_haritasi_id
            WHERE y.kullanici_id = ? AND a.hedef_tarih BETWEEN ? AND ?
            ORDER BY a.hedef_tarih, a.sira
        """, (kullanici_id, bas, son)).fetchall()
    finally:
        baglanti.close()


def takvim_odevleri(kullanici_id, bas, son):
    """Son tarihi [bas, son] aralığındaki ödevler: öğrenciyse sınıflarının, öğretmense açtığı sınıfların."""
    baglanti = baglan()
    try:
        return baglanti.execute(f"""
            SELECT o.id, o.baslik, o.son_tarih, s.ad AS sinif_adi,
                   (SELECT t.id FROM teslimler t WHERE t.odev_id = o.id AND t.ogrenci_id = :k) AS teslim_id
            FROM odevler o JOIN siniflar s ON s.id = o.sinif_id
            WHERE o.sinif_id IN {_SINIFLARI} AND o.son_tarih BETWEEN :bas AND :son
            ORDER BY o.son_tarih, o.id
        """, {"k": kullanici_id, "bas": bas, "son": son}).fetchall()
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 31) E-POSTA VE ŞİFRE SIFIRLAMA
# ---------------------------------------------------------------------------

def eposta_kaydet(kullanici_id, eposta):
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE kullanicilar SET eposta = ? WHERE id = ?", (eposta or None, kullanici_id))
        baglanti.commit()
    finally:
        baglanti.close()


def eposta_getir(kullanici_id):
    baglanti = baglan()
    try:
        satir = baglanti.execute("SELECT eposta FROM kullanicilar WHERE id = ?", (kullanici_id,)).fetchone()
        return satir["eposta"] if satir else None
    finally:
        baglanti.close()


def sifirlama_icin_kullanici(kullanici_adi):
    """Kullanıcı adına göre (büyük/küçük harf fark etmez) id ve e-posta; yoksa None."""
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT id, kullanici_adi, eposta FROM kullanicilar WHERE LOWER(kullanici_adi) = LOWER(?)",
                                (kullanici_adi,)).fetchone()
    finally:
        baglanti.close()


def sifirlama_jetonu_ekle(kullanici_id, jeton_ozeti, dakika=60):
    simdi = datetime.now()
    baglanti = baglan()
    try:
        baglanti.execute("""INSERT INTO sifre_sifirlama (kullanici_id, jeton_ozeti, olusturma, son_gecerlilik)
                            VALUES (?, ?, ?, ?)""",
                         (kullanici_id, jeton_ozeti, simdi.strftime("%Y-%m-%d %H:%M:%S"),
                          (simdi + timedelta(minutes=dakika)).strftime("%Y-%m-%d %H:%M:%S")))
        baglanti.commit()
    finally:
        baglanti.close()


def son_saat_sifirlama_sayisi(kullanici_id):
    """Son 1 saatte istenen sıfırlama bağlantısı sayısı (birinin e-posta kutusunu doldurmayı önler)."""
    sinir = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        return baglanti.execute("SELECT COUNT(*) FROM sifre_sifirlama WHERE kullanici_id = ? AND olusturma >= ?",
                                (kullanici_id, sinir)).fetchone()[0]
    finally:
        baglanti.close()


def gecerli_sifirlama(jeton_ozeti):
    """Kullanılmamış ve süresi dolmamış jetonun satırı; yoksa None."""
    simdi = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    baglanti = baglan()
    try:
        return baglanti.execute("""SELECT * FROM sifre_sifirlama
                                   WHERE jeton_ozeti = ? AND kullanildi = 0 AND son_gecerlilik >= ?""",
                                (jeton_ozeti, simdi)).fetchone()
    finally:
        baglanti.close()


def sifreyi_jetonla_degistir(jeton_ozeti, yeni_sifre):
    """
    Jeton geçerliyse şifreyi değiştirir, jetonu (ve kişinin diğer jetonlarını) kullanılmış yapar.
    Hepsi tek işlemde. Başarılıysa kullanıcı id'si, değilse None.
    """
    satir = gecerli_sifirlama(jeton_ozeti)
    if satir is None:
        return None
    baglanti = baglan()
    try:
        baglanti.execute("UPDATE kullanicilar SET sifre_hash = ?, gecici_sifre = 0 WHERE id = ?",
                         (generate_password_hash(yeni_sifre), satir["kullanici_id"]))
        baglanti.execute("UPDATE sifre_sifirlama SET kullanildi = 1 WHERE kullanici_id = ?", (satir["kullanici_id"],))
        baglanti.execute("""DELETE FROM giris_denemeleri WHERE LOWER(kullanici_adi) =
                            (SELECT LOWER(kullanici_adi) FROM kullanicilar WHERE id = ?)""", (satir["kullanici_id"],))
        baglanti.commit()
        return satir["kullanici_id"]
    finally:
        baglanti.close()


# ---------------------------------------------------------------------------
# 32) YEDEK: bütün tabloları sözlük olarak oku (yedek_al.py kullanır)
# ---------------------------------------------------------------------------

def tablo_adlari():
    baglanti = baglan()
    try:
        if POSTGRES:
            satirlar = baglanti.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()
        else:
            satirlar = baglanti.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall()
        return sorted(s[0] for s in satirlar)
    finally:
        baglanti.close()


def tablonun_satirlari(tablo):
    if tablo not in tablo_adlari():                  # Tablo adı SQL'e yazılacak; sadece gerçek adlar
        raise ValueError(tablo)
    baglanti = baglan()
    try:
        return [dict(s) for s in baglanti.execute(f"SELECT * FROM {tablo}").fetchall()]
    finally:
        baglanti.close()
