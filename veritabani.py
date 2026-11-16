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

def yol_haritasi_ekle(proje, bilgi, cevap, dosya_yolu=None, kullanici_id=None):
    """
    Yeni bir yol haritasını ve adımlarını, sahibi olan kullanıcıyla birlikte kaydeder.
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
                   (proje, bilgi, giris, dikkat, ham_cevap, dosya_yolu, olusturma_zamani, kullanici_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (proje, bilgi, parcalar["giris"], parcalar["dikkat"], cevap, dosya_yolu, zaman,
             kullanici_id),
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
        SELECT y.id, y.proje, y.olusturma_zamani,
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
            SELECT a.*, y.proje
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
            "SELECT id, kullanici_adi, rol FROM kullanicilar WHERE id = ?", (kullanici_id,)
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
            SELECT s.id, s.ad, k.kullanici_adi AS ogretmen_adi, u.katilma_zamani
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
        return baglanti.execute(f"""
            SELECT k.id, k.kullanici_adi, u.katilma_zamani,
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
        """, (sinif_id,)).fetchall()
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
        for tablo in ("ipuclari", "ogretmen_yorumlari", "kod_incelemeleri", "koc_sorulari"):
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
                WHERE y.kullanici_id = :k)                                          AS soru_sayisi
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
        baglanti.execute("UPDATE kullanicilar SET sifre_hash = ? WHERE id = ?",
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
            SELECT u.kullanici_adi, u.rol, u.olusturma_zamani,
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