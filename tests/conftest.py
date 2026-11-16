"""
KodKoç testleri - ortak hazırlık (pytest "fixture"ları)

pytest nedir?
  Python'da test yazmayı kolaylaştıran bir araç. "test_" ile başlayan her
  fonksiyonu bir test olarak çalıştırır; içindeki "assert" yanlış çıkarsa
  testi başarısız sayar.

fixture nedir?
  Testlerin ihtiyaç duyduğu hazırlığı yapan fonksiyon. Bir test, parametre
  olarak fixture'ın adını yazınca pytest onu otomatik çalıştırır.
  Örnek: def test_x(kayit_ol): ...  -> kayit_ol fixture'ı hazırlanır.

Bu dosya testlerden önce otomatik yüklenir. Burada:
  - Her test için BOŞ ve GEÇİCİ bir veritabanı hazırlıyoruz (gerçek kodkoc.db'ye dokunmayız).
  - Yapay zekâyı (Gemini) taklit ediyoruz: testler internete çıkmaz, API kotası harcanmaz.
  - Formlara CSRF jetonunu otomatik ekleyen bir test istemcisi tanımlıyoruz.
"""

import os
import re
import sys
import tempfile

import pytest
from flask.testing import FlaskClient

# Proje klasörünü Python'un arama yoluna ekle ki "import app" çalışsın
PROJE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJE)

# app.py içe aktarılırken gerçek .env'e ve gerçek veritabanına dokunmasın diye
# önce test değerlerini veriyoruz.
os.environ["FLASK_SECRET_KEY"] = "test-gizli-anahtari"
os.environ.pop("GITHUB_TOKEN", None)
os.environ["KODKOC_CANLI"] = ""          # Testler yerel modda çalışır (.env'de 1 yazsa bile)

# Testler ASLA gerçek veritabanına (ör. .env'deki DATABASE_URL) bağlanmamalı.
# Normalde testler SQLite ile çalışır. PostgreSQL ile denemek için ayrı, BOŞ bir test
# veritabanının adresi TEST_DATABASE_URL olarak verilir (her testte tabloları boşaltılır!).
# (Boş metin vermek de önemli: load_dotenv var olan bir ayarın üstüne yazmaz.)
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", "")

import veritabani                                                    # noqa: E402
veritabani.VERITABANI_DOSYASI = os.path.join(tempfile.mkdtemp(), "ilk.db")

import app as uygulama                                               # noqa: E402
import kodkoc                                                        # noqa: E402


# Yapay zekânın verdiği cevabı taklit eden örnek (gerçek bir cevaptan kısaltıldı)
ORNEK_CEVAP = """Harika bir proje seçmişsin, adım adım ilerleyelim.

### Adım 1: Menüyü Planlama
- **Ne yapılacak:** Kullanıcının göreceği menüyü tasarla.
- **Öğrenilecek konular:** while döngüsü, input
- **Nasıl anlarsın:** Menü çıkış komutuna kadar dönüyor.

### Adım 2: Görev Ekleme
- **Ne yapılacak:** Yeni görevleri listeye ekle.
- **Öğrenilecek konular:** Liste metotları
- **Nasıl anlarsın:** Eklenen görev listede görünüyor.

### Adım 3: Görevleri Listeleme
- **Ne yapılacak:** Görevleri numaralı yazdır.
- **Öğrenilecek konular:** for döngüsü, enumerate
- **Nasıl anlarsın:** Görevler alt alta numaralı çıkıyor.

### Adım 4: Dosyaya Kaydetme
- **Ne yapılacak:** Görevleri dosyaya yaz ve geri oku.
- **Öğrenilecek konular:** open, read, write
- **Nasıl anlarsın:** Program kapanıp açılınca görevler duruyor.

## Dikkat et
- Sayı yerine harf girilmesine karşı hazırlıklı ol.
- Dosya yoksa programın çökmemesini sağla.

Hemen ilk adıma başla!
"""


class JetonluIstemci(FlaskClient):
    """
    Gerçek tarayıcıda formların içinde gizli bir CSRF jetonu olur.
    Testlerde her POST'a bu jetonu kendimiz eklemek yerine bu sınıf ekler.
    (Kalıtım: FlaskClient'ın her şeyini alır, sadece post'u değiştirir.)
    """
    def post(self, *args, **kwargs):
        veri = kwargs.setdefault("data", {})
        if "csrf" not in veri:
            with self.session_transaction() as oturum:
                veri["csrf"] = oturum.setdefault("csrf", "test-jetonu")
        return super().post(*args, **kwargs)


@pytest.fixture(autouse=True)
def bos_veritabani(tmp_path, monkeypatch):
    """autouse=True: HER testten önce kendiliğinden çalışır. Her teste temiz bir veritabanı."""
    if veritabani.POSTGRES:
        # PostgreSQL'de her test için yeni dosya açamayız; tabloları boşaltıyoruz.
        # RESTART IDENTITY: id'ler yine 1'den başlasın. CASCADE: bağlı tablolar da boşalsın.
        veritabani.hazirla()
        b = veritabani.baglan()
        tablolar = [s[0] for s in b.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()]
        b.execute(f"TRUNCATE {', '.join(tablolar)} RESTART IDENTITY CASCADE")
        b.commit()
        b.close()
        return
    monkeypatch.setattr(veritabani, "VERITABANI_DOSYASI", str(tmp_path / "test.db"))
    veritabani.hazirla()


@pytest.fixture(autouse=True)
def sahte_yapay_zeka(monkeypatch):
    """
    Gemini yerine sabit cevap döndüren sahte fonksiyonlar koyar (monkeypatch:
    test süresince bir fonksiyonu geçici olarak değiştirir, test bitince eski haline döner).
    Testler, yapay zekâya ne gönderildiğini 'cagrilar' listesinden kontrol edebilir.
    """
    cagrilar = {"yol_haritasi": [], "ipucu": [], "inceleme": [], "soru": []}

    def sahte_yol_haritasi(istemci, proje, bilgi):
        cagrilar["yol_haritasi"].append(proje)
        return ORNEK_CEVAP

    def sahte_ipucu(istemci, proje, baslik, icerik, onceki, soru, seviye):
        cagrilar["ipucu"].append({"proje": proje, "onceki": list(onceki), "soru": soru, "seviye": seviye})
        return f"Seviye {seviye} ipucu: **liste** yapısına bak."

    def sahte_kod_incele(istemci, proje, baslik, icerik, kod, aciklama):
        cagrilar["inceleme"].append({"kod": kod, "aciklama": aciklama, "baslik": baslik})
        return "**İyi gidenler:** Döngün doğru.\n\n**Bakman gerekenler:**\n- **Satır 2:** Liste boşsa ne olur?"

    def sahte_soru_sor(istemci, proje, baslik, icerik, konusma, soru):
        cagrilar["soru"].append({"soru": soru, "konusma": list(konusma), "baslik": baslik})
        return f"Güzel soru! **Liste**, bir alışveriş listesi gibidir. ({len(konusma)} önceki soru)"

    monkeypatch.setattr(kodkoc, "yol_haritasi_iste", sahte_yol_haritasi)
    monkeypatch.setattr(kodkoc, "soru_sor", sahte_soru_sor)
    monkeypatch.setattr(kodkoc, "kod_incele", sahte_kod_incele)
    monkeypatch.setattr(kodkoc, "proje_fikirleri_iste", lambda istemci, bilgi, ilgi: [
        {"baslik": "Not Defteri", "aciklama": "Not ekleyip silebileceğin bir program."},
        {"baslik": "Maç Skoru Takibi", "aciklama": f"{ilgi or 'Spor'} skorlarını kaydeden bir program."},
        {"baslik": "Tarif Kutusu", "aciklama": "Malzemeye göre tarif arayan bir program."},
    ])
    monkeypatch.setattr(kodkoc, "ipucu_iste", sahte_ipucu)
    monkeypatch.setattr(kodkoc, "kaydet", lambda proje, cevap: None)   # .md dosyası yazma
    monkeypatch.setattr(uygulama, "api_anahtari", lambda: "sahte-anahtar")
    return cagrilar


@pytest.fixture
def istemci():
    """Giriş yapmamış bir ziyaretçi."""
    uygulama.app.test_client_class = JetonluIstemci
    return uygulama.app.test_client()


@pytest.fixture
def kayit_ol():
    """
    Yeni kullanıcı kaydedip giriş yapmış bir istemci döndüren fonksiyon verir.
    Kullanım: ali = kayit_ol("ali")   /   hoca = kayit_ol("hoca", "ogretmen")
    """
    uygulama.app.test_client_class = JetonluIstemci

    def _kayit_ol(ad, rol="ogrenci", sifre="sifre123"):
        k = uygulama.app.test_client()
        cevap = k.post("/kayit", data={"kullanici_adi": ad, "sifre": sifre,
                                       "sifre_tekrar": sifre, "rol": rol})
        assert cevap.status_code == 302, "kayıt başarısız oldu"
        k.kullanici = veritabani.kullanici_dogrula(ad, sifre)   # id'sine testlerde ulaşmak için
        return k
    return _kayit_ol


def yol_haritasi_cikar(k, proje="Yapılacaklar listesi"):
    """Öğrenci olarak yol haritası çıkarır; (yol haritası id'si, adım id'leri listesi) döndürür."""
    cevap = k.post("/yol-haritasi", data={"proje": proje, "bilgi": ""})
    harita_id = int(cevap.headers["Location"].rsplit("/", 1)[1])
    sayfa = k.get(f"/yol-haritasi/{harita_id}").text
    adim_idleri = [int(x) for x in re.findall(r'id="adim-(\d+)"', sayfa)]
    return harita_id, adim_idleri


def adim_bolumu(sayfa, adim_id):
    """Sayfa HTML'inden sadece bir adımın kutusunu (section) kesip alır."""
    return re.search(rf'id="adim-{adim_id}"(.*?)</section>', sayfa, re.S).group(1)
