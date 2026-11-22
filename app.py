"""
KodKoç - 3. sürüm (8. hafta): Veritabanı, ilerleme takibi ve kullanıcı girişi

Bu dosya KodKoç'u tarayıcıda çalışan bir web uygulamasına çevirir.
Yapay zekâ ile konuşan kısım değişmedi: 6. haftada yazdığımız kodkoc.py
dosyasındaki fonksiyonları burada aynen kullanıyoruz.

8. haftada eklenenler:
  - Yol haritaları artık SQLite veritabanına da kaydediliyor (veritabani.py).
  - Her adım "tamamlandı" olarak işaretlenebiliyor, ilerleme çubuğu görünüyor.
  - /gecmis sayfası eski yol haritalarını listeliyor (arama ve filtreyle).
  - Takılınca 3 kademeli ipucu, adımlara not, yol haritası silme.
  - Kullanıcı girişi: herkes sadece kendi yol haritalarını görür.
  - Öğretmen paneli: öğretmen sınıf açar, öğrenciler kodla katılır,
    öğretmen sınıfının ilerlemesini ve takıldığı yerleri görür.
  - GitHub takibi: yol haritasına bir depo bağlanır, commit'ler adımlara eşlenir.
  - Kodumu incelet: öğrenci kodunu gönderir, düzeltilmiş kod almadan geri bildirim alır.
  - Koça soru sor: adımla ilgili serbest sorular, kod vermeden cevaplanır.
  - Profil: şifre değiştirme, çalışma serisi ve etkinlik takvimi.

Çalıştırınca tarayıcıda http://127.0.0.1:5000 adresi açılır.
"""

import csv
import html
import io
import os
import re
import secrets
import threading
import time
import webbrowser
from datetime import date, datetime, timedelta
from functools import wraps

import markdown                      # Yapay zekânın cevabındaki ** ve ### işaretlerini HTML'e çevirir
from flask import (Flask, abort, flash, g, jsonify, make_response, render_template, request,
                   redirect, send_file, session, url_for)
from dotenv import load_dotenv, set_key
from google import genai

import github_takip                  # 8. hafta: GitHub'dan commit okuma
import kodkoc                        # 6. haftanın kodu: talimat, yapay zekâ ve kaydetme fonksiyonları
import veritabani                    # 8. haftanın kodu: SQLite veritabanı işlemleri

# Program nereden başlatılırsa başlatılsın kendi klasöründe çalışsın,
# böylece .env dosyası ve yol_haritalari klasörü hep aynı yerde olur.
KLASOR = os.path.dirname(os.path.abspath(__file__))
os.chdir(KLASOR)
ENV_DOSYASI = os.path.join(KLASOR, ".env")
load_dotenv(ENV_DOSYASI)

# ---------------------------------------------------------------------------
# Canlı mod (sunucuda herkesin ortak kullandığı site)
# ---------------------------------------------------------------------------
#
# KodKoç iki şekilde çalışabilir:
#   - Yerel: Her öğrenci kendi bilgisayarında açar (baslat.bat). API anahtarını kendisi girer.
#   - Canlı: Tek bir sunucuda çalışır, herkes aynı siteye girer.
#     Sunucu ayarlarına KODKOC_CANLI=1 yazılınca canlı mod açılır.
#
# Canlı modda farklı olanlar:
#   - Gemini anahtarı sadece sunucu ayarından okunur; siteden değiştirilemez.
#   - FLASK_SECRET_KEY sunucu ayarında olmak ZORUNDA (yoksa program başlamaz).
#   - Oturum çerezi sadece HTTPS üzerinden gönderilir.
#   - Yol haritaları .md dosyasına yazılmaz (zaten veritabanında duruyorlar).
CANLI = os.getenv("KODKOC_CANLI") == "1"

# Saat dilimi: Sunucular genelde Türkiye saatinde değil (UTC) çalışır.
# Tarihlerin ve "bugün"ün Türkiye'ye göre hesaplanması için saat dilimini ayarlıyoruz.
# (time.tzset sadece Linux/Mac'te var; Windows'ta bilgisayarın kendi saati zaten doğru.)
os.environ.setdefault("TZ", "Europe/Istanbul")
if hasattr(time, "tzset"):
    time.tzset()

# Öğretmen hesabı açmak için gereken davet kodu (sunucu ayarında OGRETMEN_KODU).
# Yoksa: yerelde herkes öğretmen olabilir, canlıda öğretmen kaydı kapalıdır.
OGRETMEN_KODU = os.getenv("OGRETMEN_KODU", "")

# Bir öğrencinin bir günde yapay zekâya gönderebileceği en fazla istek
# (yol haritası, proje fikri, ipucu, kod inceleme, koça soru toplamı).
GUNLUK_YZ_SINIRI = int(os.getenv("GUNLUK_YZ_SINIRI", "40"))

# Bütün sitenin bir günde yapay zekâya gönderebileceği en fazla istek (0 = sınır yok).
# Neden? Biri çok sayıda hesap açarak kişi başı sınırı aşabilir; ortak Gemini
# anahtarının günlük kotası herkes için biterdi. Bu sınır anahtarın kotasının biraz altına ayarlanır.
GUNLUK_TOPLAM_YZ_SINIRI = int(os.getenv("GUNLUK_TOPLAM_YZ_SINIRI", "0"))

# Şifre deneme sınırı: DENEME_SURESI dakika içinde EN_FAZLA_YANLIS_GIRIS kez
# yanlış şifre girilirse o kullanıcı adı bir süre kilitlenir.
EN_FAZLA_YANLIS_GIRIS = 5
DENEME_SURESI = 10

app = Flask(__name__)

if CANLI:
    # Render gibi sunucularda istekler önce bir "ara sunucudan" (proxy) geçer: HTTPS'i o
    # çözer, uygulamaya düz http olarak iletir. ProxyFix, ara sunucunun eklediği
    # X-Forwarded-For / X-Forwarded-Proto başlıklarını okuyup ziyaretçinin gerçek
    # adresini ve bağlantının HTTPS olduğunu Flask'a doğru bildirir.
    # Sadece canlıda: yerelde ara sunucu yok, bu başlıklara güvenmek yanlış olurdu.
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# Tarayıcıya "bu siteyi nasıl korumalısın" diyen güvenlik başlıkları (her cevaba eklenir)
GUVENLIK_BASLIKLARI = {
    # Dosya türünü tahmin etme, söylediğimiz türe güven (ör. metni betik sanma)
    "X-Content-Type-Options": "nosniff",
    # Başka siteye giderken adres çubuğundaki tam adresi (ör. ?proje=...) gönderme
    "Referrer-Policy": "same-origin",
    # İçerik Güvenlik Politikası (CSP): sayfa sadece izin verilen yerlerden dosya yükleyebilir.
    #   script-src 'self' 'unsafe-inline': betikler sadece bizden (sayfadaki küçük betikler dahil)
    #   frame-ancestors 'none': KodKoç başka bir sitenin içine gömülemez ("clickjacking" koruması)
    #   form-action 'self': formlar sadece KodKoç'a gönderilebilir
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    ),
}


# Tarayıcıda Python çalıştıran işçi dosyası (static/python_isci.js) için ayrı, daha geniş bir CSP.
# Pyodide'yi jsdelivr'den indirir ve WebAssembly derler ('wasm-unsafe-eval'). Bu izinler SADECE
# işçiye verilir: işçinin sayfaya (HTML'e, çerezlere, formlara) erişimi yoktur, sayfaların kendi
# CSP'si değişmez.
ISCI_CSP = ("default-src 'self'; "
            "script-src 'self' https://cdn.jsdelivr.net 'unsafe-eval' 'wasm-unsafe-eval'; "
            "connect-src 'self' https://cdn.jsdelivr.net")


@app.after_request
def guvenlik_basliklari_ekle(cevap):
    """Her cevaptan SONRA çalışır ve güvenlik başlıklarını ekler."""
    if request.path == "/static/python_isci.js":
        cevap.headers["Content-Security-Policy"] = ISCI_CSP
    for ad, deger in GUVENLIK_BASLIKLARI.items():
        cevap.headers.setdefault(ad, deger)
    if CANLI:
        # HSTS: "Bu siteye bir yıl boyunca sadece HTTPS ile bağlan" (yerelde http kullandığımız için sadece canlıda)
        cevap.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return cevap

# Bir adım için verilebilecek en fazla ipucu sayısı
EN_FAZLA_IPUCU = 3

# "Kodumu incelet": bir adım için en fazla kaç inceleme ve gönderilebilecek en uzun kod
EN_FAZLA_INCELEME = 5
EN_UZUN_KOD = 5000

# "Koça soru sor": bir adımda en fazla kaç soru sorulabilir, bir soru en fazla kaç karakter
# (sınır, öğrencinin her şeyi koça sorup kendisi düşünmemesini ve API kotasının bitmesini önler)
EN_FAZLA_SORU = 10
EN_UZUN_SORU = 500

# GitHub "Yenile" düğmesine iki basış arasında en az kaç saniye olmalı
# (GitHub'ın saatlik istek sınırını boşuna harcamamak için)
GITHUB_BEKLEME_SANIYESI = 30


# ---------------------------------------------------------------------------
# Gizli anahtar (oturum için)
# ---------------------------------------------------------------------------

def gizli_anahtari_hazirla():
    """
    Flask, giriş yapan kullanıcıyı hatırlamak için tarayıcıya imzalı bir
    "oturum çerezi" (session cookie) bırakır. Bu imzayı atmak için bir gizli
    anahtara ihtiyaç var. Bu, Gemini API anahtarı DEĞİLDİR.

    Anahtar koda yazılmaz: ilk açılışta rastgele üretilip .env dosyasına
    kaydedilir. Böylece program kapanıp açılınca kullanıcılar tekrar giriş
    yapmak zorunda kalmaz.
    """
    anahtar = os.getenv("FLASK_SECRET_KEY")
    if not anahtar:
        if CANLI:
            # Sunucularda dosyalar yeniden başlatınca silinebilir; anahtar her seferinde
            # değişirse herkesin oturumu kapanır. Bu yüzden canlıda ayardan gelmeli.
            raise RuntimeError("Canlı modda FLASK_SECRET_KEY sunucu ayarlarında tanımlı olmalı.")
        anahtar = secrets.token_hex(32)       # 64 karakterlik rastgele metin
        # set_key: .env'deki SADECE bu satırı ekler/günceller, diğerlerine dokunmaz
        set_key(ENV_DOSYASI, "FLASK_SECRET_KEY", anahtar)
    return anahtar


app.secret_key = gizli_anahtari_hazirla()

# Oturum çerezinin ayarları:
# HTTPONLY: Sayfadaki JavaScript çerezi okuyamaz (çalınmasını zorlaştırır).
# SAMESITE="Lax": Başka bir siteden gönderilen POST isteklerine çerez eklenmez.
#                 Bu, aşağıdaki CSRF korumasının yanında ikinci bir kalkan.
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
# SECURE: Çerez sadece şifreli bağlantıda (HTTPS) gönderilir. Yerelde http kullandığımız
# için sadece canlıda açıyoruz, yoksa yerelde giriş yapılamazdı.
app.config["SESSION_COOKIE_SECURE"] = CANLI

# Program açılırken veritabanı tablolarını hazırla (yoksa oluşturur, varsa dokunmaz)
veritabani.hazirla()


# ---------------------------------------------------------------------------
# Kullanıcı oturumu
# ---------------------------------------------------------------------------

@app.before_request
def kullaniciyi_yukle():
    """
    Her istekten ÖNCE çalışır: oturumda bir kullanıcı id'si varsa o kullanıcıyı
    veritabanından okuyup g.kullanici'ye koyar. "g", tek bir isteğin süresince
    bilgi saklamak için Flask'ın verdiği bir kutudur. Şablonlarda da kullanılabilir.
    """
    kullanici_id = session.get("kullanici_id")
    g.kullanici = veritabani.kullanici_getir(kullanici_id) if kullanici_id else None

    # Öğrencinin henüz görmediği öğretmen yorumu sayısı (menüdeki rozet için)
    g.okunmamis = 0
    g.yeni_duyuru = 0             # Görülmemiş sınıf duyurusu sayısı ("Sınıfım" yanındaki rozet)
    g.yeni_mesaj = 0              # Okunmamış mesaj sayısı ("Mesajlar" yanındaki rozet)
    if g.kullanici and request.endpoint != "static":
        g.yeni_mesaj = veritabani.okunmamis_mesaj_sayisi(kullanici_id)
    if g.kullanici and g.kullanici["rol"] == "ogrenci":
        g.okunmamis = veritabani.okunmamis_bildirim_sayisi(kullanici_id)   # Yorum + değerlendirme
        g.yeni_duyuru = veritabani.okunmamis_duyuru_sayisi(kullanici_id)

    # Öğretmen şifreyi sıfırladıysa öğrenci geçici şifreyle girmiştir. Geçici şifreyi
    # öğretmen de bildiği için, öğrenci kendi şifresini belirlemeden başka sayfa açamaz.
    # (before_request bir cevap döndürürse Flask asıl sayfayı hiç çalıştırmaz.)
    if (g.kullanici and g.kullanici["gecici_sifre"]
            and request.endpoint not in SIFRE_DEGISMEDEN_ACIK_SAYFALAR):
        flash("Öğretmeninin verdiği geçici şifreyle girdin. Devam etmeden önce kendi şifreni belirle.", "hata")
        return redirect(url_for("profil") + "#sifre")


# Geçici şifreyle giren öğrencinin açabildiği sayfalar (şifre değiştirme, çıkış, sağlık kontrolü, CSS)
SIFRE_DEGISMEDEN_ACIK_SAYFALAR = {"profil", "sifre_degistir", "cikis", "saglik", "static", "gizlilik"}


# ---------------------------------------------------------------------------
# CSRF koruması
# ---------------------------------------------------------------------------
#
# CSRF (Cross-Site Request Forgery, "siteler arası istek sahteciliği"):
#   Sen KodKoç'a giriş yapmışken kötü niyetli başka bir siteye girdiğini düşün.
#   O site gizlice KodKoç'a bir form gönderebilir (ör. "yol haritasını sil").
#   Tarayıcın oturum çerezini de eklediği için KodKoç bunu senin isteğin sanır.
#
# Çözüm: Her oturuma rastgele bir "jeton" (token) veriyoruz ve KodKoç'un kendi
# formlarına gizli bir alan olarak koyuyoruz. Başka bir site bu jetonu bilemez.
# Jetonu olmayan ya da yanlış olan her POST isteği reddedilir.

def csrf_jetonu():
    """Oturumun CSRF jetonunu döndürür; yoksa yeni bir tane üretir."""
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


# Şablonlarda {{ csrf_jetonu() }} yazabilmek için fonksiyonu Jinja'ya tanıtıyoruz
app.jinja_env.globals["csrf_jetonu"] = csrf_jetonu


@app.before_request
def csrf_kontrol():
    """Her POST isteğinden önce formdaki jetonu oturumdaki jetonla karşılaştırır."""
    if request.method != "POST":
        return
    gelen = request.form.get("csrf", "")
    beklenen = session.get("csrf", "")
    # compare_digest: iki metni, karşılaştırma süresinden ipucu sızdırmadan karşılaştırır
    if not beklenen or not secrets.compare_digest(gelen, beklenen):
        abort(400)


@app.errorhandler(400)
def gecersiz_istek(hata):
    """CSRF jetonu tutmazsa (ör. sayfa çok uzun süre açık kaldıysa) gösterilir."""
    return render_template("gecersiz_istek.html"), 400


def giris_gerekli(fonksiyon):
    """
    "Dekoratör": Bir route'un üstüne @giris_gerekli yazınca, o sayfa açılmadan
    önce bu kontrol çalışır. Giriş yapılmamışsa kullanıcı giriş sayfasına gönderilir.
    @wraps: Flask'ın route adlarını (url_for için) karıştırmaması için gerekli.
    """
    @wraps(fonksiyon)
    def kontrol(*args, **kwargs):
        if g.kullanici is None:
            return redirect(url_for("giris"))
        return fonksiyon(*args, **kwargs)
    return kontrol


def ogretmen_gerekli(fonksiyon):
    """
    @giris_gerekli gibi, ama ek olarak kullanıcının ÖĞRETMEN olmasını ister.
    Rol tabanlı yetkilendirme: Aynı uygulamada kişinin rolüne göre
    açılabilen sayfalar farklıdır.
    """
    @wraps(fonksiyon)
    def kontrol(*args, **kwargs):
        if g.kullanici is None:
            return redirect(url_for("giris"))
        if g.kullanici["rol"] != "ogretmen":
            flash("Bu sayfa sadece öğretmenler için.", "hata")
            return redirect(url_for("ana_sayfa"))
        return fonksiyon(*args, **kwargs)
    return kontrol


def aktif_id():
    """Giriş yapmış kullanıcının id'si (kısa yazmak için)."""
    return g.kullanici["id"]


def giris_sonrasi_adres(rol):
    """Girişten sonra öğretmen paneline, öğrenci ana sayfaya gider."""
    return url_for("ogretmen_paneli") if rol == "ogretmen" else url_for("ana_sayfa")


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------

def api_anahtari():
    """
    Yerelde: .env dosyasındaki API anahtarını her seferinde yeniden okur
    (öğrenci anahtarı siteden girince program yeniden başlatmadan kullanılsın diye).
    Canlıda: Anahtar sadece sunucu ayarından gelir.
    """
    if not CANLI:
        load_dotenv(ENV_DOSYASI, override=True)
    return os.getenv("GEMINI_API_KEY")


def site_kotasi_doldu():
    """Bütün site bugünkü ortak yapay zekâ sınırına ulaştıysa True."""
    return (GUNLUK_TOPLAM_YZ_SINIRI > 0
            and veritabani.bugunku_toplam_yz_kullanimi() >= GUNLUK_TOPLAM_YZ_SINIRI)


def yz_kotasi_doldu():
    """Kullanıcının kendi günlük hakkı ya da sitenin ortak günlük sınırı dolduysa True."""
    return veritabani.bugunku_yz_kullanimi(aktif_id()) >= GUNLUK_YZ_SINIRI or site_kotasi_doldu()


def kalan_yz_hakki(kullanici_id):
    """Kullanıcının bugün kalan yapay zekâ hakkı (eksiye düşmez)."""
    return max(0, GUNLUK_YZ_SINIRI - veritabani.bugunku_yz_kullanimi(kullanici_id))


def kota_mesaji():
    """Hangi sınır dolduysa ona uygun mesaj (sadece kota dolunca çağrılır)."""
    if site_kotasi_doldu():
        return ("KodKoç bugün çok yoğun çalıştı ve günlük yapay zekâ sınırına ulaştı. "
                "Yarın yine buradayım! Bu arada adımlarını kendin denemeye devam edebilirsin.")
    return (f"Bugünkü yapay zekâ hakkını ({GUNLUK_YZ_SINIRI} istek) doldurdun. Yarın yine buradayım! "
            "Bu arada elindeki ipuçlarıyla kendin denemeye ne dersin?")


def html_e_cevir(metin):
    """
    Yapay zekânın cevabını web sayfasında gösterilecek HTML'e çevirir.
    1) Güvenlik için cevaptaki olası HTML etiketleri etkisiz hale getirilir.
    2) Markdown işaretleri (**kalın**, ### başlık) gerçek HTML'e çevrilir.
    3) Her "### Adım" başlığı ayrı bir kutuya, "## Dikkat et" bölümü de
       ayrı bir kutuya konur.
    """
    guvenli = html.escape(metin, quote=False)
    icerik = markdown.markdown(guvenli)

    parcalar = re.split(r"(?=<h[23]>)", icerik)   # Her başlıktan önce böl
    sonuc = []
    for parca in parcalar:
        if parca.startswith("<h3>"):
            sonuc.append(f'<section class="adim">{parca}</section>')
        elif parca.startswith("<h2>"):
            sonuc.append(f'<section class="dikkat">{parca}</section>')
        elif parca.strip():
            sonuc.append(f'<div class="giris">{parca}</div>')
    return "\n".join(sonuc)


def guvenli_markdown(metin):
    """Tek bir parçayı (ör. bir adımın maddelerini) güvenli şekilde HTML'e çevirir."""
    return markdown.markdown(html.escape(metin or "", quote=False))


def ilerleme_hesapla(tamamlanan, toplam):
    """Tamamlanan adım oranını yüzde olarak döndürür (adım yoksa 0)."""
    if toplam == 0:
        return 0
    return round(tamamlanan * 100 / toplam)


def anlasilir_hata(hata):
    """Yapay zekâ hatasını öğrencinin anlayacağı bir cümleye çevirir."""
    if kodkoc.gecici_hata_mi(hata):
        return "Yapay zekâ şu an çok yoğun. Birkaç kez denedim olmadı; bir dakika sonra tekrar dener misin?"
    if CANLI:
        # Canlıda hatanın ayrıntısını ziyaretçiye göstermiyoruz (sunucu hakkında bilgi
        # sızdırabilir); ayrıntı, sunucunun kayıtlarına (log) yazılır.
        app.logger.error("Yapay zekâ hatası: %s", hata)
        return "Yapay zekâya şu an bağlanılamadı. Biraz sonra tekrar dener misin?"
    return f"Yapay zekâya bağlanılamadı. İnternetini ve API anahtarını kontrol et. ({hata})"


def adim_adresi(adim):
    """Bir adımın, yol haritası sayfasındaki adresi (ör. /yol-haritasi/3#adim-12)."""
    return url_for("yol_haritasi_goster", harita_id=adim["yol_haritasi_id"]) + f"#adim-{adim['id']}"


# Başlığın başındaki "Adım 3:" kısmını yakalar ("Adım 3 -", "ADIM 3." gibi yazımlar dahil)
ADIM_ON_EKI = re.compile(r"^\s*ad[ıi]m\s*\d+\s*[:.\-–]\s*", re.IGNORECASE)


def sade_baslik(baslik):
    """
    'Adım 3: Görev Silme' -> 'Görev Silme'. Başında numara yoksa olduğu gibi döner.
    Sadece 'Adım 3:' yazılmışsa boş metin döner (formda "başlık boş" hatası verilsin diye).
    """
    return ADIM_ON_EKI.sub("", baslik or "").strip()


@app.template_filter("adim_basligi")
def adim_basligi(baslik, sira):
    """
    Başlığı her zaman GÜNCEL sıra numarasıyla gösterir: "Adım {sira}: {sade başlık}".
    Neden? Öğrenci bir adımı silince numaralar kayar; yapay zekânın yazdığı "Adım 4:"
    eskide kalırdı. Numarayı veritabanındaki sira sütunundan alıyoruz.
    Şablonda kullanımı: {{ adim.baslik | adim_basligi(adim.sira) }}
    """
    # Temizleyince boş kalırsa (çok eski/garip bir kayıt) orijinal başlığı göster
    return f"Adım {sira}: {sade_baslik(baslik) or baslik}"


@app.template_filter("tarih")
def tarih_bicimle(metin):
    """Veritabanındaki '2026-11-10 16:49:00' tarihini '10.11.2026 16:49' şeklinde gösterir."""
    return datetime.strptime(metin, "%Y-%m-%d %H:%M:%S").strftime("%d.%m.%Y %H:%M")


@app.template_filter("gun")
def gun_bicimle(metin):
    """'2026-11-21' -> '21.11.2026' (hedef tarihler saatsiz, sadece gün)."""
    return date.fromisoformat(metin).strftime("%d.%m.%Y")


YAKLASIYOR_GUN = 2          # Hedefe bu kadar gün (ya da daha az) kaldıysa "Yaklaşıyor"


def hedef_durumu(hedef_tarih, tamamlandi, bugun):
    """
    Bir adımın hedef tarihine göre durumu:
      None         : hedef yok
      "tamam"      : adım bitmiş (tarih artık önemli değil)
      "gecikti"    : tarih geçti, adım bitmedi
      "yaklasiyor" : en fazla YAKLASIYOR_GUN gün kaldı
      "var"        : hedef var, daha zaman var
    """
    if not hedef_tarih:
        return None
    if tamamlandi:
        return "tamam"
    kalan = (date.fromisoformat(hedef_tarih) - bugun).days
    if kalan < 0:
        return "gecikti"
    return "yaklasiyor" if kalan <= YAKLASIYOR_GUN else "var"


def hafta_basi(gun):
    """Verilen günün haftasının pazartesisi. weekday(): pazartesi 0, pazar 6."""
    return gun - timedelta(days=gun.weekday())


@app.route("/saglik")
def saglik():
    """
    Sağlık kontrolü: Sunucu (ör. Render) birkaç saniyede bir bu adresi açar.
    "tamam" cevabı gelmezse uygulamanın çöktüğünü anlar ve yeniden başlatır.
    Veritabanına da basit bir sorgu atıyoruz; bağlantı kopuksa hata (500) döner.
    """
    try:
        veritabani.kullanici_sayisi()
    except Exception as hata:
        # Asıl sebebi sunucu kayıtlarına (log) yaz; ziyaretçiye ayrıntı gösterme
        app.logger.error("Sağlık kontrolü: veritabanına ulaşılamadı (%s). Teşhis: %s",
                         type(hata).__name__, veritabani.baglanti_teshisi())
        return "veritabani yok", 503, {"Content-Type": "text/plain; charset=utf-8"}
    # Hangi sürüm çalışıyor? Render, çalışan commit'in numarasını RENDER_GIT_COMMIT ayarıyla verir.
    # Cevaba ekliyoruz: "yeni sürüm gerçekten yayına girdi mi?" sorusu tek istekle cevaplanır.
    surum = os.getenv("RENDER_GIT_COMMIT", "yerel")[:7]
    return "tamam", 200, {"Content-Type": "text/plain; charset=utf-8", "X-KodKoc-Surum": surum}


@app.errorhandler(500)
def sunucu_hatasi(hata):
    """
    Programda beklenmedik bir hata olunca (ör. veritabanına bağlanılamadı) gösterilir.
    Hatanın ayrıntısı ziyaretçiye gösterilmez; Flask onu sunucunun kayıtlarına (log) yazar.
    """
    return render_template("sunucu_hatasi.html"), 500


@app.errorhandler(404)
def bulunamadi(hata):
    """Olmayan (ya da başkasına ait) bir sayfa istenince tasarıma uygun bir sayfa göster."""
    return render_template("bulunamadi.html"), 404


# ---------------------------------------------------------------------------
# Kayıt, giriş, çıkış
# ---------------------------------------------------------------------------

# Kullanıcı adı kuralı: 3-20 karakter; harf (Türkçe dahil), rakam, nokta, alt çizgi.
# \w = harf, rakam ya da alt çizgi. Bu bir "düzenli ifade" (regex).
KULLANICI_ADI_KURALI = re.compile(r"^[\w.]{3,20}$")
EN_KISA_SIFRE = 6


@app.route("/kayit", methods=["GET", "POST"])
def kayit():
    """GET: Kayıt formunu gösterir. POST: Yeni kullanıcı oluşturur ve giriş yaptırır."""
    if g.kullanici:
        return redirect(giris_sonrasi_adres(g.kullanici["rol"]))

    # Öğretmen kaydı nasıl? "serbest": kod gerekmez (yerel), "kodlu": davet kodu ister,
    # "kapali": canlıda kod tanımlanmamışsa kimse kendini öğretmen yapamaz.
    if OGRETMEN_KODU:
        ogretmen_kaydi = "kodlu"
    else:
        ogretmen_kaydi = "kapali" if CANLI else "serbest"

    def formu_goster(**degerler):
        return render_template("kayit.html", ogretmen_kaydi=ogretmen_kaydi, **degerler)

    if request.method == "GET":
        return formu_goster(rol="ogrenci")

    kullanici_adi = request.form.get("kullanici_adi", "").strip()
    sifre = request.form.get("sifre", "")
    sifre_tekrar = request.form.get("sifre_tekrar", "")
    rol = request.form.get("rol", "ogrenci")
    if rol not in ("ogrenci", "ogretmen"):      # Formdan gelen değere asla körü körüne güvenme
        rol = "ogrenci"

    # Sunucu tarafında doğrulama: tarayıcıdaki kontroller atlatılabilir,
    # bu yüzden asıl kontrol her zaman burada yapılır.
    hata = None
    if not KULLANICI_ADI_KURALI.match(kullanici_adi):
        hata = "Kullanıcı adı 3-20 karakter olmalı; sadece harf, rakam, nokta ve alt çizgi kullanabilirsin."
    elif len(sifre) < EN_KISA_SIFRE:
        hata = f"Şifren en az {EN_KISA_SIFRE} karakter olmalı."
    elif sifre != sifre_tekrar:
        hata = "İki şifre birbirinin aynısı değil."
    elif rol == "ogretmen" and ogretmen_kaydi == "kapali":
        hata = "Öğretmen kaydı şu an kapalı. Site yöneticisinden davet kodu iste."
    elif rol == "ogretmen" and ogretmen_kaydi == "kodlu" and not secrets.compare_digest(
            request.form.get("ogretmen_kodu", "").strip(), OGRETMEN_KODU):
        hata = "Öğretmen davet kodu yanlış."
    if hata:
        return formu_goster(hata=hata, kullanici_adi=kullanici_adi, rol=rol)

    kullanici_id = veritabani.kullanici_ekle(kullanici_adi, sifre, rol)
    if kullanici_id is None:
        return formu_goster(kullanici_adi=kullanici_adi, rol=rol,
                            hata="Bu kullanıcı adı alınmış, başka bir tane dene.")

    # Önce eski oturumu temizle. DİKKAT: flash mesajları da oturumda saklandığı için
    # clear() mutlaka flash()'lardan ÖNCE çağrılmalı, yoksa mesajlar silinir.
    session.clear()
    session["kullanici_id"] = kullanici_id      # Artık giriş yapmış sayılır
    flash(f"Hoş geldin, {kullanici_adi}!", "bilgi")

    # İlk kayıt olan kişi, giriş özelliği gelmeden önceki yol haritalarını devralır
    if veritabani.kullanici_sayisi() == 1:
        aktarilan = veritabani.sahipsiz_kayitlari_aktar(kullanici_id)
        if aktarilan:
            flash(f"Daha önce çıkardığın {aktarilan} yol haritası hesabına aktarıldı.", "bilgi")
    return redirect(giris_sonrasi_adres(rol))


@app.route("/giris", methods=["GET", "POST"])
def giris():
    """GET: Giriş formunu gösterir. POST: Kullanıcı adı ve şifreyi kontrol eder."""
    if g.kullanici:
        return redirect(giris_sonrasi_adres(g.kullanici["rol"]))
    if request.method == "GET":
        # Hiç kullanıcı yoksa doğrudan kayıt sayfasına yönlendir (ilk açılış)
        if veritabani.kullanici_sayisi() == 0:
            return redirect(url_for("kayit"))
        return render_template("giris.html")

    kullanici_adi = request.form.get("kullanici_adi", "").strip()[:40]   # Veritabanına çöp yazılmasın
    sifre = request.form.get("sifre", "")

    # Çok fazla yanlış deneme varsa şifreyi hiç kontrol etmeden reddet.
    # Böylece biri şifreleri sırayla deneyerek ("kaba kuvvet" saldırısı) bulamaz.
    if veritabani.son_yanlis_giris_sayisi(kullanici_adi, DENEME_SURESI) >= EN_FAZLA_YANLIS_GIRIS:
        return render_template("giris.html", kullanici_adi=kullanici_adi,
                               hata=f"Çok fazla yanlış deneme oldu. {DENEME_SURESI} dakika sonra tekrar dene."), 429

    kullanici = veritabani.kullanici_dogrula(kullanici_adi, sifre)
    if kullanici is None:
        veritabani.yanlis_giris_ekle(kullanici_adi)
        # Hangisinin yanlış olduğunu söylemiyoruz; böylece kötü niyetli biri
        # hangi kullanıcı adlarının var olduğunu öğrenemez.
        return render_template("giris.html", kullanici_adi=kullanici_adi,
                               hata="Kullanıcı adı ya da şifre yanlış.")

    veritabani.yanlis_girisleri_temizle(kullanici_adi)
    session.clear()
    session["kullanici_id"] = kullanici["id"]
    return redirect(giris_sonrasi_adres(kullanici["rol"]))


@app.route("/cikis", methods=["POST"])
def cikis():
    """POST: Oturumu kapatır."""
    session.clear()
    flash("Çıkış yaptın. Görüşmek üzere!", "bilgi")
    return redirect(url_for("giris"))


# ---------------------------------------------------------------------------
# Sayfalar (route'lar): Hangi adreste ne olacağını belirler
# ---------------------------------------------------------------------------

def bugun_onerisi(hedefler, devam, devam_ipucu, sinifta, seri, bugun_calisti):
    """
    Ana sayfadaki "Bugün ne yapayım?" kartı için TEK bir öneri seçer.
    Kurallar öncelik sırasıyla denenir; ilk uyan kazanır:
      1) Hedefi geçmiş adım        2) Hedefi bugün/yarın olan adım
      3) Takıldığı adım (2+ ipucu)  4) Seri bozulmasın (dün çalıştı, bugün henüz değil)
      5) Sıradaki adım              6) Hiç devam eden yol haritası yok
    Veritabanına dokunmaz; bütün bilgiyi parametre olarak alır (kolay test edilsin diye).
    Dönüş: {"metin": ..., "adres": ...}
    """
    def adim_adresi_(h):
        return url_for("yol_haritasi_goster", harita_id=h["harita_id"]) + f"#adim-{h['adim_id']}"

    for h in hedefler:
        if h["kalan"] < 0:
            return {"metin": f"“{adim_basligi(h['baslik'], h['sira'])}” adımının hedefi {-h['kalan']} gün önce geçti. "
                             "Bugün ona odaklan; takıldıysan ipucu iste.",
                    "adres": adim_adresi_(h)}
    for h in hedefler:
        if h["kalan"] <= 1:
            ne_zaman = "bugün" if h["kalan"] == 0 else "yarın"
            return {"metin": f"“{adim_basligi(h['baslik'], h['sira'])}” adımının hedefi {ne_zaman}. "
                             "Bitirmeye çok yakınsın!",
                    "adres": adim_adresi_(h)}
    if devam and devam_ipucu >= 2:
        kime = "öğretmenine sor" if sinifta else "koça bir soru sor"
        return {"metin": f"“{adim_basligi(devam['baslik'], devam['sira'])}” adımında {devam_ipucu} ipucu aldın. "
                         f"Hâlâ takıldıysan {kime}; bazen bir cümlelik açıklama yeter.",
                "adres": adim_adresi_(devam)}
    if devam and seri > 0 and not bugun_calisti:
        return {"metin": f"Serin {seri} gün. Bugün küçük bir adım atarsan seri devam eder: "
                         f"“{adim_basligi(devam['baslik'], devam['sira'])}”.",
                "adres": adim_adresi_(devam)}
    if devam:
        return {"metin": f"Sıradaki adımın: “{adim_basligi(devam['baslik'], devam['sira'])}”. "
                         "İlk küçük parçasıyla başla.",
                "adres": adim_adresi_(devam)}
    return {"metin": "Devam eden bir yol haritan yok. Aşağıya yeni bir proje anlat ya da fikir al.",
            "adres": "#form"}


def sinif_projesi_bul(sinif_id):
    """
    Giriş yapmış öğrencinin ÜYE OLDUĞU ve projesi olan bir sınıfı döndürür, yoksa None.
    Formdan/adresten gelen sınıf numarasına körü körüne güvenmiyoruz: öğrenci başka
    bir sınıfın numarasını yazarsa o sınıfa yol haritası bağlanamaz.
    """
    if not sinif_id:
        return None
    for sinif in veritabani.ogrencinin_siniflari(aktif_id()):
        if sinif["id"] == sinif_id and sinif["proje"]:
            return sinif
    return None


@app.route("/", methods=["GET"])
@giris_gerekli
def ana_sayfa():
    """
    GET: Proje formunu gösterir.
    - "Kaldığın yerden devam et" kartı için bitmemiş en son adımı bulur.
    - Adreste ?proje=...&bilgi=... varsa (bir proje fikri seçildiyse) formu onlarla doldurur.
    """
    devam = veritabani.devam_edilecek_adim(aktif_id())
    # Öğretmenden gelen, henüz görülmemiş en fazla 3 duyuru (ana sayfanın en üstünde gösterilir)
    yeni_duyurular = veritabani.ogrencinin_duyurulari(aktif_id(), sadece_yeniler=True, sinir=3)

    # Yaklaşan hedefler: önümüzdeki 7 gün içindeki (ve gecikmiş) bitmemiş adımlar
    bugun = date.today()
    hedefler = [
        {**dict(h), "durum": hedef_durumu(h["hedef_tarih"], False, bugun),
         "kalan": (date.fromisoformat(h["hedef_tarih"]) - bugun).days}
        for h in veritabani.yaklasan_hedefler(aktif_id(), (bugun + timedelta(days=7)).isoformat())
    ]
    # Haftalık özet: bu hafta ve geçen hafta bitirilen adımlar (hafta pazartesi başlar)
    pazartesi = hafta_basi(bugun)
    hafta = veritabani.haftalik_ozet(aktif_id(), pazartesi.isoformat(),
                                     (pazartesi - timedelta(days=7)).isoformat())

    # Öğretmenlerin verdiği sınıf projeleri (öğrencinin üye olduğu, projesi olan sınıflar)
    siniflari = veritabani.ogrencinin_siniflari(aktif_id())
    sinif_projeleri = [s for s in siniflari if s["proje"]]

    # "Bugün ne yapayım?": hedefler, sıradaki adım, ipucu sayısı ve seriye bakarak tek öneri
    gunler = {date.fromisoformat(gun) for gun in veritabani.calisma_gunleri(aktif_id())}
    seri, _ = seri_hesapla(gunler, bugun)
    devam_ipucu = len(veritabani.ipuclarini_getir(devam["adim_id"])) if devam else 0
    oneri = bugun_onerisi(hedefler, devam, devam_ipucu, bool(siniflari), seri, bugun in gunler)
    # "Bu projeyle başla"ya basıldıysa (/?sinif_proje=3) formu sınıf projesiyle doldur
    secilen = sinif_projesi_bul(request.args.get("sinif_proje", type=int))
    proje = secilen["proje"] if secilen else request.args.get("proje", "")[:1000]

    return render_template("index.html", anahtar_var=bool(api_anahtari()), canli=CANLI,
                           yz_kalan=kalan_yz_hakki(aktif_id()), yz_sinir=GUNLUK_YZ_SINIRI,
                           hedefler=hedefler, hafta=hafta,
                           sinif_projeleri=sinif_projeleri, sinif_proje=secilen, oneri=oneri,
                           devam=devam, yeni_duyurular=yeni_duyurular,
                           devam_yuzde=ilerleme_hesapla(devam["biten"], devam["toplam"]) if devam else 0,
                           proje=proje,
                           bilgi=request.args.get("bilgi", "")[:200])


@app.route("/fikir", methods=["POST"])
@giris_gerekli
def proje_fikri():
    """POST: Öğrencinin ilgi alanına ve bildiklerine göre 3 proje fikri ister."""
    ilgi = request.form.get("ilgi", "").strip()[:200]
    bilgi = request.form.get("bilgi", "").strip()[:200]

    anahtar = api_anahtari()
    if not anahtar:
        return redirect(url_for("ana_sayfa"))
    if yz_kotasi_doldu():
        return render_template("index.html", anahtar_var=True, bilgi=bilgi, ilgi=ilgi,
                               fikir_hatasi=kota_mesaji())

    try:
        istemci = genai.Client(api_key=anahtar)
        fikirler = kodkoc.proje_fikirleri_iste(istemci, bilgi, ilgi)
    except ValueError:
        # Yapay zekâ cevap verdi ama biçimi bozuktu (JSON değil ya da eksik)
        fikirler, hata = None, "Fikirler hazırlanırken bir aksilik oldu, bir kez daha dener misin?"
    except Exception as e:
        fikirler, hata = None, anlasilir_hata(e)
    else:
        hata = None
        veritabani.yz_kullanimi_ekle(aktif_id())

    return render_template("index.html", anahtar_var=True, bilgi=bilgi, ilgi=ilgi,
                           fikirler=fikirler, fikir_hatasi=hata)


@app.route("/anahtar", methods=["POST"])
@giris_gerekli
def anahtar_kaydet():
    """
    POST: İlk kurulumda girilen API anahtarını .env dosyasına kaydeder.
    Canlıda KAPALI: Yoksa siteye giren herkes sunucunun ortak anahtarını değiştirebilirdi.
    """
    if CANLI:
        abort(404)
    anahtar = request.form.get("anahtar", "").strip()
    if anahtar:
        # set_key: .env'deki diğer ayarlara (ör. FLASK_SECRET_KEY) dokunmadan
        # sadece GEMINI_API_KEY satırını ekler ya da günceller.
        set_key(ENV_DOSYASI, "GEMINI_API_KEY", anahtar)
    return redirect(url_for("ana_sayfa"))


@app.route("/yol-haritasi", methods=["POST"])
@giris_gerekli
def yol_haritasi():
    """POST: Formdan gelen projeyi yapay zekâya gönderir ve sonucu gösterir."""
    proje = request.form.get("proje", "").strip()
    bilgi = request.form.get("bilgi", "").strip()
    # Sınıf projesi için mi? (Gizli alan; öğrenci gerçekten o sınıftaysa kabul edilir)
    sinif_proje = sinif_projesi_bul(request.form.get("sinif_proje", type=int))

    def formu_tekrar_goster(hata):
        """Hata olursa formu, yazılanlar ve sınıf projesi bağı kaybolmadan yeniden göster."""
        return render_template("index.html", anahtar_var=True, proje=proje, bilgi=bilgi,
                               sinif_proje=sinif_proje, hata=hata)

    # Boş form gönderilirse uyarı ver
    if not proje:
        return formu_tekrar_goster("Lütfen önce projeni anlat.")

    anahtar = api_anahtari()
    if not anahtar:
        return redirect(url_for("ana_sayfa"))
    if yz_kotasi_doldu():
        return formu_tekrar_goster(kota_mesaji())

    try:
        istemci = genai.Client(api_key=anahtar)
        cevap = kodkoc.yol_haritasi_iste(istemci, proje, bilgi)
    except Exception as hata:
        return formu_tekrar_goster(anlasilir_hata(hata))
    veritabani.yz_kullanimi_ekle(aktif_id())

    # 7. haftadaki gibi .md dosyasına da kaydet (sadece yerelde), ayrıca (8. hafta) veritabanına ekle
    dosya_yolu = None if CANLI else kodkoc.kaydet(proje, cevap)
    harita_id = veritabani.yol_haritasi_ekle(proje, bilgi, cevap, dosya_yolu, kullanici_id=aktif_id(),
                                            sinif_id=sinif_proje["id"] if sinif_proje else None)

    # Sonucu doğrudan göstermek yerine yol haritasının kendi sayfasına yönlendir.
    # Böylece sayfa yenilenince form tekrar gönderilmez (yapay zekâya boşuna
    # ikinci kez gidilmez) ve her yol haritasının kalıcı bir adresi olur.
    return redirect(url_for("yol_haritasi_goster", harita_id=harita_id))


@app.route("/yol-haritasi/<int:harita_id>", methods=["GET"])
@giris_gerekli
def yol_haritasi_goster(harita_id):
    """GET: Kayıtlı bir yol haritasını, adımları ve ilerleme çubuğuyla gösterir."""
    harita, adim_satirlari = veritabani.yol_haritasi_getir(harita_id, aktif_id())
    if harita is None:
        abort(404)                         # Yoksa ya da başkasınınsa "bulunamadı" sayfası

    # Öğrenci sayfayı açtı: yeni yorumları "okundu" yap, menüdeki sayıyı güncelle.
    # Hangilerinin yeni olduğunu da sayfaya iletiyoruz ki bir kereliğine "Yeni" yazsın.
    yeni_yorumlar = veritabani.yorumlari_okundu_yap(harita_id)
    yeni_degerlendirme = veritabani.degerlendirmeyi_goruldu_yap(harita_id)
    yeni_cevaplar = veritabani.cevaplari_goruldu_yap(harita_id)
    g.okunmamis = veritabani.okunmamis_bildirim_sayisi(aktif_id())
    return yol_haritasi_sayfasi(harita, adim_satirlari, yeni_yorum_idleri=set(yeni_yorumlar),
                                yeni_degerlendirme=yeni_degerlendirme,
                                yeni_cevap_idleri=set(yeni_cevaplar),
                                ogretmene_sorabilir=bool(veritabani.ogrencinin_siniflari(aktif_id())))


def yol_haritasi_sayfasi(harita, adim_satirlari, ogretmen_gorunumu=None, yeni_yorum_idleri=(),
                         yeni_degerlendirme=False, yeni_cevap_idleri=(), ogretmene_sorabilir=False):
    """
    Yol haritası sayfasını hazırlar. Hem öğrencinin kendi sayfası hem de
    öğretmenin salt okunur görünümü bu fonksiyonu kullanır (kod tekrarı olmasın diye).
    ogretmen_gorunumu: öğretmen bakıyorsa {"ogrenci_adi": ..., "geri_adres": ...},
                       öğrenci bakıyorsa None. Şablon buna göre düğmeleri gizler.
    """
    harita_id = harita["id"]

    # Bu yol haritasındaki bütün ipuçlarını tek seferde al: {adim_id: [ipuçları]}
    ipuclari = veritabani.yol_haritasinin_ipuclari(harita_id)

    # Öğretmen yorumları ve kod incelemeleri: {adim_id: [...]}
    yorumlar = veritabani.yol_haritasinin_yorumlari(harita_id)
    incelemeler = veritabani.yol_haritasinin_incelemeleri(harita_id)
    sorular = veritabani.yol_haritasinin_sorulari(harita_id)       # "Koça soru sor" konuşmaları
    ogretmen_sorulari = veritabani.yol_haritasinin_ogretmen_sorulari(harita_id)   # "Öğretmenime sor"

    # GitHub commit'leri: hepsi (en yeniden eskiye) ve adımlara göre gruplanmış hali
    commitler = veritabani.yol_haritasinin_commitleri(harita_id)
    adim_commitleri = {}
    for c in commitler:
        if c["adim_id"]:
            adim_commitleri.setdefault(c["adim_id"], []).append(c)

    # Her adımın maddelerini HTML'e çevirip şablona hazır hale getir
    bugun = date.today()
    adimlar = []
    for satir in adim_satirlari:
        adim_ipuclari = [
            {"seviye": i["seviye"], "soru": i["soru"], "cevap_html": guvenli_markdown(i["cevap"])}
            for i in ipuclari.get(satir["id"], [])
        ]
        adimlar.append({
            "id": satir["id"],
            "sira": satir["sira"],
            "baslik": satir["baslik"],
            "baslik_sade": sade_baslik(satir["baslik"]),       # Düzenleme kutusunda gösterilir
            "icerik": satir["icerik"] or "",
            "kendi_eklendi": bool(satir["kendi_eklendi"]),
            "icerik_html": guvenli_markdown(satir["icerik"]),
            "tamamlandi": bool(satir["tamamlandi"]),
            "ogretmen_sorulari": ogretmen_sorulari.get(satir["id"], []),
            "hedef_tarih": satir["hedef_tarih"],
            "hedef_durumu": hedef_durumu(satir["hedef_tarih"], satir["tamamlandi"], bugun),
            # Eski kayıtlarda boş: öğretmen koymuş sayılır (öğrenci değiştiremesin)
            "hedef_koyan": satir["hedef_koyan"] or ("ogretmen" if satir["hedef_tarih"] else None),
            "not_metni": satir["not_metni"] or "",
            "ipuclari": adim_ipuclari,
            "ipucu_hakki_var": len(adim_ipuclari) < EN_FAZLA_IPUCU,
            "commitler": adim_commitleri.get(satir["id"], []),
            "yorumlar": yorumlar.get(satir["id"], []),
            "incelemeler": [
                {"kod": k["kod"], "aciklama": k["aciklama"], "zaman": k["olusturma_zamani"],
                 "geri_bildirim_html": guvenli_markdown(k["geri_bildirim"])}
                for k in incelemeler.get(satir["id"], [])
            ],
            "inceleme_hakki": EN_FAZLA_INCELEME - len(incelemeler.get(satir["id"], [])),
            "sorular": [
                {"soru": s["soru"], "zaman": s["olusturma_zamani"],
                 "cevap_html": guvenli_markdown(s["cevap"])}
                for s in sorular.get(satir["id"], [])
            ],
            "soru_hakki": EN_FAZLA_SORU - len(sorular.get(satir["id"], [])),
        })

    tamamlanan = sum(1 for adim in adimlar if adim["tamamlandi"])
    toplam = len(adimlar)

    # Yapay zekâ beklenen biçimde cevap vermediyse adım bulunamaz;
    # o zaman cevabın tamamını 7. haftadaki gibi gösteririz.
    if toplam == 0:
        giris_html = html_e_cevir(harita["ham_cevap"])
        dikkat_html = ""
    else:
        giris_html = html_e_cevir(harita["giris"] or "")
        dikkat_html = html_e_cevir(harita["dikkat"] or "")

    return render_template("yol_haritasi.html", harita=harita, adimlar=adimlar,
                           giris_html=giris_html, dikkat_html=dikkat_html,
                           tamamlanan=tamamlanan, toplam=toplam,
                           yuzde=ilerleme_hesapla(tamamlanan, toplam),
                           en_fazla_ipucu=EN_FAZLA_IPUCU,
                           en_fazla_inceleme=EN_FAZLA_INCELEME,
                           en_uzun_kod=EN_UZUN_KOD,
                           en_fazla_soru=EN_FAZLA_SORU,
                           en_uzun_soru=EN_UZUN_SORU,
                           ogretmen_gorunumu=ogretmen_gorunumu,
                           bugun=bugun.isoformat(),
                           degerlendiren=veritabani.degerlendiren_adi(harita["degerlendiren_id"]),
                           yeni_degerlendirme=yeni_degerlendirme,
                           yeni_cevap_idleri=yeni_cevap_idleri, ogretmene_sorabilir=ogretmene_sorabilir,
                           commitler=commitler,
                           yeni_yorum_idleri=yeni_yorum_idleri)


# ---------------------------------------------------------------------------
# GitHub commit takibi
# ---------------------------------------------------------------------------

def commitleri_guncelle(harita_id, depo):
    """
    GitHub'dan commit'leri çekip veritabanına kaydeder ve sonucu flash ile bildirir.
    github_takip.GithubHatasi: GitHub tarafındaki sorunlar için Türkçe mesaj taşır.
    """
    try:
        commitler = github_takip.commitleri_getir(depo)
    except github_takip.GithubHatasi as hata:
        flash(str(hata), "hata")
        return
    yeni = veritabani.commitleri_kaydet(harita_id, commitler, github_takip.adim_numarasi_bul)
    if not commitler:
        flash("Depo bağlandı ama henüz hiç commit yok. İlk commit'ini atınca 'Yenile'ye bas.", "bilgi")
    elif yeni:
        flash(f"{yeni} yeni commit bulundu.", "bilgi")
    else:
        flash("Yeni commit yok.", "bilgi")


@app.route("/yol-haritasi/<int:harita_id>/github", methods=["POST"])
@giris_gerekli
def github_bagla(harita_id):
    """POST: Yol haritasına bir GitHub deposu bağlar ve commit'leri hemen çeker."""
    depo = github_takip.depo_adini_coz(request.form.get("depo"))
    geri = url_for("yol_haritasi_goster", harita_id=harita_id)
    if depo is None:
        flash("Depo adresini anlayamadım. Örnek: kullanici/proje ya da https://github.com/kullanici/proje", "hata")
        return redirect(geri)
    if not veritabani.github_depo_ayarla(harita_id, aktif_id(), depo):
        abort(404)
    commitleri_guncelle(harita_id, depo)
    return redirect(geri)


@app.route("/yol-haritasi/<int:harita_id>/github/yenile", methods=["POST"])
@giris_gerekli
def github_yenile(harita_id):
    """POST: Bağlı depodan yeni commit'leri çeker."""
    harita, _ = veritabani.yol_haritasi_getir(harita_id, aktif_id())
    if harita is None or not harita["github_depo"]:
        abort(404)
    geri = url_for("yol_haritasi_goster", harita_id=harita_id)

    # Çok sık basılırsa GitHub'a gitme
    if harita["github_son_kontrol"]:
        son = datetime.strptime(harita["github_son_kontrol"], "%Y-%m-%d %H:%M:%S")
        gecen = (datetime.now() - son).total_seconds()
        if gecen < GITHUB_BEKLEME_SANIYESI:
            flash(f"Az önce kontrol ettim. {int(GITHUB_BEKLEME_SANIYESI - gecen) + 1} saniye sonra tekrar dene.", "bilgi")
            return redirect(geri)

    commitleri_guncelle(harita_id, harita["github_depo"])
    return redirect(geri)


@app.route("/yol-haritasi/<int:harita_id>/github/kaldir", methods=["POST"])
@giris_gerekli
def github_kaldir(harita_id):
    """POST: Depo bağlantısını ve kaydedilmiş commit'leri kaldırır (GitHub'daki depoya dokunmaz)."""
    if not veritabani.github_depo_ayarla(harita_id, aktif_id(), None):
        abort(404)
    flash("GitHub bağlantısı kaldırıldı.", "bilgi")
    return redirect(url_for("yol_haritasi_goster", harita_id=harita_id))


@app.route("/yol-haritasi/<int:harita_id>/sil", methods=["POST"])
@giris_gerekli
def yol_haritasi_sil(harita_id):
    """POST: Bir yol haritasını veritabanından siler (.md dosyası yedek olarak kalır)."""
    if not veritabani.yol_haritasi_sil(harita_id, aktif_id()):
        abort(404)
    flash("Yol haritası silindi.", "bilgi")
    return redirect(url_for("gecmis"))


@app.route("/adim/<int:adim_id>/ipucu", methods=["POST"])
@giris_gerekli
def ipucu(adim_id):
    """POST: Öğrenci bir adımda takıldı; yapay zekâdan bir sonraki seviye ipucunu ister."""
    adim = veritabani.adim_getir(adim_id, aktif_id())
    if adim is None:
        abort(404)

    onceki = veritabani.ipuclarini_getir(adim_id)
    seviye = len(onceki) + 1                # 1. ipucu, 2. ipucu, 3. ipucu
    if seviye > EN_FAZLA_IPUCU:
        flash("Bu adım için bütün ipuçlarını kullandın. Şimdi araştırıp denemek sende!", "bilgi")
        return redirect(adim_adresi(adim))

    anahtar = api_anahtari()
    if not anahtar:
        return redirect(url_for("ana_sayfa"))
    if yz_kotasi_doldu():
        flash(kota_mesaji(), "hata")
        return redirect(adim_adresi(adim))

    soru = request.form.get("soru", "").strip()
    try:
        istemci = genai.Client(api_key=anahtar)
        cevap = kodkoc.ipucu_iste(istemci, adim["proje"], adim["baslik"], adim["icerik"],
                                  [i["cevap"] for i in onceki], soru, seviye, bilgi=adim["bilgi"])
    except Exception as hata:
        flash(anlasilir_hata(hata), "hata")
        return redirect(adim_adresi(adim))
    veritabani.yz_kullanimi_ekle(aktif_id())

    veritabani.ipucu_ekle(adim_id, seviye, soru, cevap)
    return redirect(adim_adresi(adim))


@app.route("/adim/<int:adim_id>/incele", methods=["POST"])
@giris_gerekli
def kod_incele(adim_id):
    """POST: Öğrencinin kodunu yapay zekâya gönderir; düzeltilmiş kod VERMEDEN geri bildirim alır."""
    adim = veritabani.adim_getir(adim_id, aktif_id())
    if adim is None:
        abort(404)

    if veritabani.adimin_inceleme_sayisi(adim_id) >= EN_FAZLA_INCELEME:
        flash(f"Bu adım için {EN_FAZLA_INCELEME} inceleme hakkını kullandın. "
              "Öğretmeninden de yardım isteyebilirsin.", "bilgi")
        return redirect(adim_adresi(adim))

    # rstrip: sondaki boş satırları at, ama baştaki girintiyi (Python için önemli) koru
    kod = request.form.get("kod", "").rstrip()
    aciklama = request.form.get("aciklama", "").strip()
    if not kod.strip():
        flash("İncelenecek kodu yapıştırmayı unuttun.", "hata")
        return redirect(adim_adresi(adim))
    if len(kod) > EN_UZUN_KOD:
        flash(f"Kod çok uzun (en fazla {EN_UZUN_KOD} karakter). Sadece bu adımla ilgili kısmı gönder.", "hata")
        return redirect(adim_adresi(adim))

    anahtar = api_anahtari()
    if not anahtar:
        return redirect(url_for("ana_sayfa"))
    if yz_kotasi_doldu():
        flash(kota_mesaji(), "hata")
        return redirect(adim_adresi(adim))

    try:
        istemci = genai.Client(api_key=anahtar)
        geri_bildirim = kodkoc.kod_incele(istemci, adim["proje"], adim["baslik"], adim["icerik"],
                                          kod, aciklama, bilgi=adim["bilgi"])
    except Exception as hata:
        flash(anlasilir_hata(hata), "hata")
        return redirect(adim_adresi(adim))
    veritabani.yz_kullanimi_ekle(aktif_id())

    veritabani.kod_incelemesi_ekle(adim_id, kod, aciklama, geri_bildirim)
    return redirect(adim_adresi(adim))


@app.route("/adim/<int:adim_id>/soru", methods=["POST"])
@giris_gerekli
def koca_soru_sor(adim_id):
    """POST: Öğrenci adımla ilgili serbest bir soru sorar; koç kod vermeden cevaplar."""
    adim = veritabani.adim_getir(adim_id, aktif_id())
    if adim is None:
        abort(404)

    onceki = veritabani.adimin_sorulari(adim_id)
    if len(onceki) >= EN_FAZLA_SORU:
        flash(f"Bu adımda {EN_FAZLA_SORU} soru hakkını kullandın. Öğrendiklerini denemenin zamanı!", "bilgi")
        return redirect(adim_adresi(adim))

    soru = request.form.get("soru", "").strip()
    if not soru:
        flash("Sorunu yazmayı unuttun.", "hata")
        return redirect(adim_adresi(adim))
    if len(soru) > EN_UZUN_SORU:
        flash(f"Sorun çok uzun (en fazla {EN_UZUN_SORU} karakter). Kısaltıp tekrar dener misin?", "hata")
        return redirect(adim_adresi(adim))

    anahtar = api_anahtari()
    if not anahtar:
        return redirect(url_for("ana_sayfa"))
    if yz_kotasi_doldu():
        flash(kota_mesaji(), "hata")
        return redirect(adim_adresi(adim))

    try:
        istemci = genai.Client(api_key=anahtar)
        # Son 3 soru-cevabı "hafıza" olarak gönder (hepsini göndermek mesajı gereksiz uzatır)
        konusma = [(s["soru"], s["cevap"]) for s in onceki[-3:]]
        cevap = kodkoc.soru_sor(istemci, adim["proje"], adim["baslik"], adim["icerik"], konusma, soru,
                                bilgi=adim["bilgi"])
    except Exception as hata:
        flash(anlasilir_hata(hata), "hata")
        return redirect(adim_adresi(adim))
    veritabani.yz_kullanimi_ekle(aktif_id())

    veritabani.koc_sorusu_ekle(adim_id, soru, cevap)
    return redirect(adim_adresi(adim))


# ---------------------------------------------------------------------------
# Adımları düzenleme
# ---------------------------------------------------------------------------

EN_UZUN_BASLIK = 120
EN_UZUN_ICERIK = 2000


def adim_formunu_oku():
    """
    Düzenleme ve ekleme formlarından başlık ile içeriği okuyup doğrular.
    (baslik, icerik, hata) döndürür; sorun yoksa hata None olur.
    Başlığa "Adım 5:" yazılsa bile temizlenir, çünkü numarayı sistem veriyor.
    """
    baslik = sade_baslik(request.form.get("baslik", "").strip())
    icerik = request.form.get("icerik", "").strip()
    if not baslik or len(baslik) > EN_UZUN_BASLIK:
        return baslik, icerik, f"Adım başlığı 1-{EN_UZUN_BASLIK} karakter olmalı."
    if len(icerik) > EN_UZUN_ICERIK:
        return baslik, icerik, f"Adım açıklaması en fazla {EN_UZUN_ICERIK} karakter olabilir."
    return baslik, icerik, None


@app.route("/yol-haritasi/<int:harita_id>/adim-ekle", methods=["POST"])
@giris_gerekli
def adim_ekle(harita_id):
    """POST: Öğrenci yol haritasının sonuna kendi adımını ekler."""
    harita, _ = veritabani.yol_haritasi_getir(harita_id, aktif_id())
    if harita is None:
        abort(404)
    baslik, icerik, hata = adim_formunu_oku()
    if hata:
        flash(hata, "hata")
        return redirect(url_for("yol_haritasi_goster", harita_id=harita_id))
    adim_id = veritabani.adim_ekle(harita_id, baslik, icerik)
    flash("Adımın eklendi.", "bilgi")
    return redirect(url_for("yol_haritasi_goster", harita_id=harita_id) + f"#adim-{adim_id}")


@app.route("/adim/<int:adim_id>/duzenle", methods=["POST"])
@giris_gerekli
def adim_duzenle(adim_id):
    """POST: Adımın başlığını ve açıklamasını değiştirir."""
    adim = veritabani.adim_getir(adim_id, aktif_id())
    if adim is None:
        abort(404)
    baslik, icerik, hata = adim_formunu_oku()
    if hata:
        flash(hata, "hata")
    else:
        veritabani.adim_duzenle(adim_id, baslik, icerik)
        flash("Adım güncellendi.", "bilgi")
    return redirect(adim_adresi(adim))


@app.route("/adim/<int:adim_id>/sil", methods=["POST"])
@giris_gerekli
def adim_sil(adim_id):
    """POST: Adımı siler; sonraki adımların numaraları birer azalır."""
    adim = veritabani.adim_getir(adim_id, aktif_id())
    if adim is None:
        abort(404)
    if veritabani.adim_sil(adim_id):
        flash("Adım silindi, numaralar yeniden sıralandı.", "bilgi")
    else:
        flash("Yol haritasında en az bir adım kalmalı.", "hata")
    return redirect(url_for("yol_haritasi_goster", harita_id=adim["yol_haritasi_id"]))


# ---------------------------------------------------------------------------
# Rozetler
# ---------------------------------------------------------------------------

# (anahtar, rozet adı, nasıl kazanılır, veritabani.rozet_verileri'nden hangi sayı, en az kaç)
ROZETLER = [
    ("ilk_adim",    "İlk Adım",       "Bir adımı tamamla.",                                  "biten_adim",      1),
    ("kendi_basina", "Kendi Başına",  "Hiç ipucu almadan 3 adım tamamla.",                    "ipucusuz_biten",  3),
    ("pes_etmeyen", "Pes Etmeyen",    "3 ipucunun hepsini kullandığın bir adımı yine de bitir.", "israrci_biten", 1),
    ("kod_okuyucu", "Kod Okuyucu",    "Kodunu bir kez incelet.",                              "inceleme_sayisi", 1),
    ("merakli",     "Meraklı",        "Koça 3 soru sor.",                                     "soru_sayisi",     3),
    ("not_defteri", "Not Defteri",    "3 farklı adıma not yaz.",                              "not_sayisi",      3),
    ("ilk_commit",  "İlk Commit",     "GitHub'a ilk commit'ini at ve deponu bağla.",          "commit_sayisi",   1),
    ("bitis",       "Bitiş Çizgisi",  "Bir yol haritasını baştan sona bitir.",                "biten_harita",    1),
    ("zamaninda",   "Tam Zamanında",  "Hedef tarihi olan 2 adımı zamanında bitir.",           "zamaninda_biten", 2),
    ("soru_soran",  "Soru Soran",     "Öğretmenine bir soru sor.",                            "ogretmen_sorusu", 1),
    ("istikrarli",  "İstikrarlı",     "7 gün üst üste çalış.",                                "en_uzun_seri",    7),
]


def rozetleri_hesapla(kullanici_id):
    """Her rozet için {ad, aciklama, kazanildi, ilerleme} listesi döndürür."""
    veri = veritabani.rozet_verileri(kullanici_id)
    # En uzun çalışma serisi veritabanında tek sayı olarak yok; profil sayfasındaki gibi hesaplanır
    gunler = {date.fromisoformat(gun) for gun in veritabani.calisma_gunleri(kullanici_id)}
    veri["en_uzun_seri"] = seri_hesapla(gunler, date.today())[1]
    sonuc = []
    for anahtar, ad, aciklama, sayi_adi, hedef in ROZETLER:
        sayi = veri[sayi_adi]
        sonuc.append({"anahtar": anahtar, "ad": ad, "aciklama": aciklama,
                      "kazanildi": sayi >= hedef,
                      "ilerleme": f"{min(sayi, hedef)} / {hedef}"})
    return sonuc


def kazanilan_rozetler(kullanici_id):
    """Kazanılmış rozetlerin adları (küme). Bir işlemden önce ve sonra karşılaştırmak için."""
    return {r["ad"] for r in rozetleri_hesapla(kullanici_id) if r["kazanildi"]}


def yeni_rozetleri_bildir(onceki):
    """İşlemden önce kazanılmış rozetlerle (onceki) şimdikileri karşılaştırır; yenileri kutlar."""
    for ad in sorted(kazanilan_rozetler(aktif_id()) - onceki):
        flash(f"Yeni rozet kazandın: ★ {ad}! Bütün rozetlerin Geçmiş sayfasında.", "bilgi")


# ---------------------------------------------------------------------------
# Profil: hesap bilgileri, çalışma serisi, şifre değiştirme
# ---------------------------------------------------------------------------

def seri_hesapla(gunler, bugun):
    """
    Çalışma serisi: üst üste kaç gün çalışılmış?
    gunler: çalışılan günlerin kümesi (date nesneleri), bugun: bugünün tarihi.
    - Şu anki seri: bugünden (bugün çalışmadıysa dünden) geriye doğru kesintisiz günler.
      Neden dün? Öğrenci sabah sayfayı açınca seri "0" görünmesin; gün bitmedi.
    - En uzun seri: bütün geçmişteki en uzun kesintisiz gün dizisi.
    """
    gun = bugun if bugun in gunler else bugun - timedelta(days=1)
    simdiki = 0
    while gun in gunler:                 # Geriye doğru, boş bir güne gelene kadar say
        simdiki += 1
        gun -= timedelta(days=1)

    en_uzun = 0
    for ilk in gunler:
        if ilk - timedelta(days=1) not in gunler:     # Bir serinin İLK günü mü? (önceki gün boş)
            uzunluk = 1
            while ilk + timedelta(days=uzunluk) in gunler:
                uzunluk += 1
            en_uzun = max(en_uzun, uzunluk)
    return simdiki, en_uzun


def takvim_olustur(etkinlik, bugun, hafta_sayisi=4):
    """
    Son birkaç haftanın etkinlik takvimi (her satır bir hafta, Pazartesi'den Pazar'a).
    etkinlik: {"2026-11-10": 3, ...}. Her gün için {tarih, sayi, seviye, gelecek} döner.
    seviye 0-3: kutunun ne kadar koyu boyanacağı (0 = hiç çalışılmamış).
    """
    # weekday(): Pazartesi = 0 ... Pazar = 6. Bu haftanın pazartesisinden geriye git.
    baslangic = bugun - timedelta(days=bugun.weekday() + 7 * (hafta_sayisi - 1))
    haftalar = []
    for h in range(hafta_sayisi):
        hafta = []
        for d in range(7):
            gun = baslangic + timedelta(days=7 * h + d)
            sayi = etkinlik.get(gun.isoformat(), 0)
            seviye = 0 if sayi == 0 else 1 if sayi == 1 else 2 if sayi <= 3 else 3
            hafta.append({"tarih": gun.strftime("%d.%m.%Y"), "sayi": sayi,
                          "seviye": seviye, "gelecek": gun > bugun})
        haftalar.append(hafta)
    return haftalar


@app.route("/profil", methods=["GET"])
@giris_gerekli
def profil():
    """GET: Hesap bilgileri, çalışma serisi, etkinlik takvimi ve şifre değiştirme formu."""
    bugun = date.today()
    etkinlik = veritabani.calisma_gunleri(aktif_id())
    # Metin tarihleri ("2026-11-10") date nesnesine çevir; böylece gün ekleyip çıkarabiliriz
    gunler = {date.fromisoformat(gun) for gun in etkinlik}
    simdiki_seri, en_uzun_seri = seri_hesapla(gunler, bugun)
    return render_template("profil.html", bilgi=veritabani.hesap_bilgileri(aktif_id()),
                           simdiki_seri=simdiki_seri, en_uzun_seri=en_uzun_seri,
                           bugun_calisti=bugun in gunler,
                           takvim=takvim_olustur(etkinlik, bugun),
                           en_kisa_sifre=EN_KISA_SIFRE, en_uzun_hakkimda=EN_UZUN_HAKKIMDA,
                           engellenenler=veritabani.engelledikleri(aktif_id()),
                           yz_kalan=kalan_yz_hakki(aktif_id()), yz_sinir=GUNLUK_YZ_SINIRI)


@app.route("/profil/sifre", methods=["POST"])
@giris_gerekli
def sifre_degistir():
    """POST: Eski şifre doğruysa şifreyi değiştirir."""
    eski = request.form.get("eski_sifre", "")
    yeni = request.form.get("yeni_sifre", "")
    tekrar = request.form.get("yeni_sifre_tekrar", "")

    if len(yeni) < EN_KISA_SIFRE:
        flash(f"Yeni şifren en az {EN_KISA_SIFRE} karakter olmalı.", "hata")
    elif yeni != tekrar:
        flash("Yeni şifreler birbirinin aynısı değil.", "hata")
    elif yeni == eski:
        flash("Yeni şifren eskisiyle aynı olamaz.", "hata")
    elif not veritabani.sifre_degistir(aktif_id(), eski, yeni):
        flash("Şu anki şifreni yanlış girdin.", "hata")
    else:
        flash("Şifren değiştirildi.", "bilgi")
        return redirect(url_for("ana_sayfa") if g.kullanici["gecici_sifre"] else url_for("profil"))
    return redirect(url_for("profil") + "#sifre")


@app.route("/profil/sil", methods=["POST"])
@giris_gerekli
def hesabi_sil():
    """
    POST: Kullanıcı kendi hesabını ve bütün verilerini kalıcı olarak siler.
    Kişisel verilerin sahibi kullanıcıdır; istediği zaman silebilmeli.
    Yanlışlıkla ya da başkası tarafından silinmesin diye şifre ve "SİL" yazması isteniyor.
    """
    # Python "sil".upper() -> "SIL" verir (Türkçe İ'yi bilmez); iki yazımı da kabul ediyoruz
    if request.form.get("onay", "").strip().upper().replace("İ", "I") != "SIL":
        flash('Hesabını silmek için kutuya büyük harflerle "SİL" yaz.', "hata")
        return redirect(url_for("profil") + "#hesap-sil")
    if not veritabani.hesap_sil(aktif_id(), request.form.get("sifre", "")):
        flash("Şifreni yanlış girdin; hesabın silinmedi.", "hata")
        return redirect(url_for("profil") + "#hesap-sil")
    session.clear()
    flash("Hesabın ve bütün verilerin silindi. Görüşmek üzere!", "bilgi")
    return redirect(url_for("giris"))


EN_UZUN_OGRETMEN_SORUSU = 500
EN_FAZLA_ACIK_SORU = 5          # Aynı anda cevap bekleyen en fazla soru (öğretmeni boğmasın)


@app.route("/adim/<int:adim_id>/ogretmene-sor", methods=["POST"])
@giris_gerekli
def ogretmene_sor(adim_id):
    """
    POST: Öğrenci bir adım için öğretmenine soru sorar. Koça sormaktan farkı: cevabı
    yapay zekâ değil, öğrenciyi tanıyan öğretmen verir. Sadece bir sınıfa üye olan sorabilir.
    """
    adim = veritabani.adim_getir(adim_id, aktif_id())       # Sadece kendi adımı
    if adim is None:
        abort(404)
    if not veritabani.ogrencinin_siniflari(aktif_id()):
        flash("Öğretmenine soru sorabilmek için önce bir sınıfa katıl.", "hata")
        return redirect(adim_adresi(adim))
    soru = request.form.get("soru", "").strip()
    if not soru or len(soru) > EN_UZUN_OGRETMEN_SORUSU:
        flash(f"Sorun 1-{EN_UZUN_OGRETMEN_SORUSU} karakter olmalı.", "hata")
        return redirect(adim_adresi(adim))
    if veritabani.acik_soru_sayisi(aktif_id()) >= EN_FAZLA_ACIK_SORU:
        flash(f"Cevap bekleyen {EN_FAZLA_ACIK_SORU} sorun var. Öğretmenin onları cevaplayınca yenisini sorabilirsin.", "hata")
        return redirect(adim_adresi(adim))
    onceki = kazanilan_rozetler(aktif_id())
    veritabani.ogretmene_soru_ekle(adim_id, soru)
    flash("Sorun öğretmenine iletildi. Cevaplayınca menüde bildirim göreceksin.", "bilgi")
    yeni_rozetleri_bildir(onceki)
    return redirect(adim_adresi(adim))


@app.route("/adim/<int:adim_id>/hedef", methods=["POST"])
@giris_gerekli
def kendi_hedefim(adim_id):
    """
    POST: Öğrenci kendi adımına hedef tarih koyar ya da kaldırır (kendi planını yapsın diye).
    Öğretmenin koyduğu hedefi DEĞİŞTİREMEZ: öğretmen tarihi bir sebeple koymuştur.
    """
    adim = veritabani.adim_getir(adim_id, aktif_id())       # Sadece kendi adımı
    if adim is None:
        abort(404)
    if adim["hedef_tarih"] and (adim["hedef_koyan"] or "ogretmen") == "ogretmen":
        flash("Bu hedefi öğretmenin koydu; değiştirmek için öğretmenine sor.", "hata")
        return redirect(adim_adresi(adim))

    metin = request.form.get("tarih", "").strip()
    if not metin:
        veritabani.hedef_tarih_ayarla(adim_id, None)
        flash("Hedefin kaldırıldı.", "bilgi")
        return redirect(adim_adresi(adim))
    tarih, hata = hedef_tarihi_oku(metin)
    if hata:
        flash(hata, "hata")
        return redirect(adim_adresi(adim))
    veritabani.hedef_tarih_ayarla(adim_id, tarih.isoformat(), "ogrenci")
    flash(f"Hedefin {tarih.strftime('%d.%m.%Y')}. Başarabilirsin!", "bilgi")
    return redirect(adim_adresi(adim))


@app.route("/adim/<int:adim_id>/not", methods=["POST"])
@giris_gerekli
def not_kaydet(adim_id):
    """POST: Öğrencinin bir adıma yazdığı notu kaydeder."""
    adim = veritabani.adim_getir(adim_id, aktif_id())
    if adim is None:
        abort(404)
    onceki = kazanilan_rozetler(aktif_id())
    veritabani.not_kaydet(adim_id, request.form.get("not_metni", "").strip())
    flash("Notun kaydedildi.", "bilgi")
    yeni_rozetleri_bildir(onceki)
    return redirect(adim_adresi(adim))


@app.route("/notlarim", methods=["GET"])
@giris_gerekli
def notlarim():
    """GET: Öğrencinin bütün adım notları, yol haritalarına göre gruplanmış (aranabilir)."""
    ara = request.args.get("ara", "").strip()[:100]
    gruplar = []                                   # [{harita_id, proje, notlar: [...]}, ...]
    for satir in veritabani.tum_notlar(aktif_id(), ara):
        if not gruplar or gruplar[-1]["harita_id"] != satir["harita_id"]:
            gruplar.append({"harita_id": satir["harita_id"], "proje": satir["proje"], "notlar": []})
        gruplar[-1]["notlar"].append(satir)
    return render_template("notlarim.html", gruplar=gruplar, ara=ara,
                           not_sayisi=sum(len(g_["notlar"]) for g_ in gruplar))


@app.route("/notlarim/indir", methods=["GET"])
@giris_gerekli
def notlarimi_indir():
    """GET: Bütün notları tek bir Markdown (.md) dosyası olarak indirir (defter gibi saklasın diye)."""
    satirlar = ["# KodKoç notlarım", ""]
    son_harita = None
    for satir in veritabani.tum_notlar(aktif_id()):
        if satir["harita_id"] != son_harita:
            son_harita = satir["harita_id"]
            satirlar += [f"## {satir['proje'].splitlines()[0][:120]}", ""]
        satirlar += [f"### {adim_basligi(satir['baslik'], satir['sira'])}", "", satir["not_metni"], ""]
    veri = "\n".join(satirlar).encode("utf-8")
    return send_file(io.BytesIO(veri), mimetype="text/markdown", as_attachment=True,
                     download_name="kodkoc-notlarim.md")


@app.route("/adim/<int:adim_id>", methods=["POST"])
@giris_gerekli
def adim_isaretle(adim_id):
    """POST: Bir adımı tamamlandı / tamamlanmadı olarak işaretler."""
    adim = veritabani.adim_getir(adim_id, aktif_id())    # Bu adım bu kullanıcının mı?
    if adim is None:
        abort(404)

    tamamlandi = request.form.get("tamamlandi") == "1"
    onceki = kazanilan_rozetler(aktif_id()) if tamamlandi else None
    veritabani.adim_durumunu_degistir(adim_id, tamamlandi)
    if tamamlandi:
        yeni_rozetleri_bildir(onceki)

    # Aynı sayfaya geri dön; "#adim-5" kısmı sayfanın o adıma kaymasını sağlar
    return redirect(adim_adresi(adim))


@app.route("/gecmis", methods=["GET"])
@giris_gerekli
def gecmis():
    """GET: Daha önce çıkarılan yol haritalarını listeler (arama ve durum filtresiyle)."""
    # Adres çubuğundaki ?ara=...&durum=... değerlerini oku (GET formu bunları gönderir)
    ara = request.args.get("ara", "").strip()
    durum = request.args.get("durum", "hepsi")
    if durum not in ("hepsi", "devam", "bitti"):
        durum = "hepsi"

    haritalar = []
    for satir in veritabani.tum_yol_haritalari(aktif_id(), ara, durum):
        haritalar.append({
            "id": satir["id"],
            "proje": satir["proje"],
            "olusturma_zamani": satir["olusturma_zamani"],
            "toplam": satir["toplam_adim"],
            "tamamlanan": satir["tamamlanan_adim"],
            "yuzde": ilerleme_hesapla(satir["tamamlanan_adim"], satir["toplam_adim"]),
            "yorum_sayisi": satir["yorum_sayisi"],
            "yeni_yorum_sayisi": satir["yeni_yorum_sayisi"],
            "puan": satir["degerlendirme_puan"],             # Öğretmenin değerlendirmesi (1-5)
            "yeni_puan": satir["degerlendirme_goruldu"] == 0,
        })
    return render_template("gecmis.html", haritalar=haritalar, ara=ara, durum=durum,
                           ozet=veritabani.istatistikler(aktif_id()),
                           rozetler=rozetleri_hesapla(aktif_id()))


# ---------------------------------------------------------------------------
# Öğrenci: sınıfa katılma
# ---------------------------------------------------------------------------

@app.route("/sinifim", methods=["GET"])
@giris_gerekli
def sinifim():
    """GET: Öğrencinin katıldığı sınıfları ve "sınıfa katıl" formunu gösterir."""
    if g.kullanici["rol"] == "ogretmen":
        return redirect(url_for("ogretmen_paneli"))
    # Önce duyuruları (hangileri yeni bilgisiyle) oku, SONRA okundu yap.
    # Sıra ters olsaydı sayfada hiçbir duyuru "Yeni" görünmezdi.
    duyurular = veritabani.ogrencinin_duyurulari(aktif_id())
    veritabani.duyurulari_okundu_yap(aktif_id())
    g.yeni_duyuru = 0                      # Menüdeki sayı bu sayfada hemen sıfırlansın
    return render_template("sinifim.html", siniflar=veritabani.ogrencinin_siniflari(aktif_id()),
                           duyurular=duyurular,
                           paylasilan_sorular=veritabani.paylasilan_sorular(aktif_id()))


@app.route("/sinifim/katil", methods=["POST"])
@giris_gerekli
def sinifa_katil():
    """POST: Öğrenciyi, öğretmenin verdiği kodla sınıfa ekler."""
    if g.kullanici["rol"] == "ogretmen":
        abort(404)
    # Kodu büyük harfe çevir ve boşlukları at: "k7m 2qx" -> "K7M2QX"
    kod = request.form.get("kod", "").upper().replace(" ", "")
    durum, sinif = veritabani.sinifa_katil(aktif_id(), kod)
    if durum == "yok":
        flash("Bu kodla bir sınıf bulunamadı. Kodu öğretmeninden tekrar kontrol et.", "hata")
    elif durum == "zaten":
        flash(f"Zaten \"{sinif['ad']}\" sınıfındasın.", "bilgi")
    else:
        flash(f"\"{sinif['ad']}\" sınıfına katıldın!", "bilgi")
    return redirect(url_for("sinifim"))


@app.route("/sinifim/<int:sinif_id>/ayril", methods=["POST"])
@giris_gerekli
def siniftan_ayril(sinif_id):
    """POST: Öğrenciyi sınıftan çıkarır; öğretmen artık onun verilerini göremez."""
    veritabani.siniftan_ayril(aktif_id(), sinif_id)
    flash("Sınıftan ayrıldın.", "bilgi")
    return redirect(url_for("sinifim"))


# ---------------------------------------------------------------------------
# Öğretmen paneli
# ---------------------------------------------------------------------------

@app.route("/ogretmen", methods=["GET"])
@ogretmen_gerekli
def ogretmen_paneli():
    """GET: Öğretmenin sınıflarını listeler ve yeni sınıf açma formunu gösterir."""
    siniflar = []
    for sinif in veritabani.ogretmenin_siniflari(aktif_id()):
        ozet = veritabani.sinif_ozeti(sinif["id"])
        baslayan = [o for o in ozet if o["toplam_adim"] > 0]
        siniflar.append({
            **dict(sinif),
            # Ortalama ilerleme: sadece yol haritası olan öğrencilerin ortalaması
            "ortalama": round(sum(ilerleme_hesapla(o["biten_adim"], o["toplam_adim"]) for o in baslayan)
                              / len(baslayan)) if baslayan else 0,
            "geciken": sum(o["geciken_adim"] for o in ozet),
            "baslamayan": len(ozet) - len(baslayan),
        })
    return render_template("ogretmen_paneli.html", siniflar=siniflar,
                           bekleyen_sorular=veritabani.ogretmenin_bekleyen_sorulari(aktif_id()),
                           sikayetler=veritabani.ogretmenin_sikayetleri(aktif_id()), sebepler=SIKAYET_SEBEPLERI)


@app.route("/ogretmen/sinif", methods=["POST"])
@ogretmen_gerekli
def sinif_olustur():
    """POST: Yeni sınıf açar."""
    ad = request.form.get("ad", "").strip()
    if not ad or len(ad) > 60:
        flash("Sınıf adı 1-60 karakter olmalı.", "hata")
        return redirect(url_for("ogretmen_paneli"))
    sinif_id = veritabani.sinif_olustur(aktif_id(), ad)
    return redirect(url_for("sinif_detay", sinif_id=sinif_id))


ISTATISTIK_GUN = 14                      # Sınıf grafiği kaç günü göstersin
GUN_ADLARI = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]   # weekday() sırasıyla

# İlerleme dağılımı grupları: (etiket, en az yüzde, en çok yüzde)
ILERLEME_GRUPLARI = [("%0-25", 0, 25), ("%26-50", 26, 50), ("%51-75", 51, 75), ("%76-100", 76, 100)]


def sinif_istatistigi(ogrenciler, etkinlikler, bugun, gun_sayisi=ISTATISTIK_GUN):
    """
    Öğretmenin sınıf sayfasındaki istatistik kutuları ve iki grafik için verileri hazırlar.
    ogrenciler : sinif_detay'daki liste (her biri yuzde, toplam, biten içerir)
    etkinlikler: {(ogrenci_id, '2026-11-10'), ...}  -> kim hangi gün çalıştı
    Döndürdüğü sözlük:
      ortalama   : yol haritası olan öğrencilerin ortalama ilerlemesi (%)
      aktif_hafta: son 7 günde en az bir kez çalışan FARKLI öğrenci sayısı
      baslamayan : henüz hiç yol haritası (adımı) olmayan öğrenci sayısı
      dagilim    : [{etiket, sayi, oran}]   -> yatay çubuk grafiği
      gunler     : [{etiket, tarih, sayi, oran}] -> son 14 günün sütun grafiği
    "oran": çubuğun ne kadar dolu çizileceği (0-100), en büyük değere göre.
    """
    baslamis = [o for o in ogrenciler if o["toplam"] > 0]
    ortalama = round(sum(o["yuzde"] for o in baslamis) / len(baslamis)) if baslamis else 0

    # Son 7 gün: bugün dahil 7 gün. Küme ile aynı öğrenci iki kez sayılmaz.
    hafta_basi = (bugun - timedelta(days=6)).isoformat()
    aktif_hafta = len({ogrenci for ogrenci, gun in etkinlikler if gun >= hafta_basi})

    # İlerleme dağılımı: her öğrenci yüzdesine göre bir gruba düşer
    dagilim = []
    for etiket, en_az, en_cok in ILERLEME_GRUPLARI:
        sayi = sum(1 for o in baslamis if en_az <= o["yuzde"] <= en_cok)
        dagilim.append({"etiket": etiket, "sayi": sayi})
    # Çubuk uzunluğu sınıf mevcuduna göre: 10 kişilik sınıfta 5 öğrenci = yarım çubuk
    for grup in dagilim:
        grup["oran"] = round(100 * grup["sayi"] / len(ogrenciler)) if ogrenciler else 0

    # Günlük etkinlik: her gün kaç FARKLI öğrenci çalışmış?
    gunler = []
    for geri in range(gun_sayisi - 1, -1, -1):          # En eski gün solda, bugün sağda
        gun = bugun - timedelta(days=geri)
        sayi = sum(1 for _, g in etkinlikler if g == gun.isoformat())
        gunler.append({"etiket": GUN_ADLARI[gun.weekday()], "tarih": gun.strftime("%d.%m"),
                       "sayi": sayi, "bugun": geri == 0})
    en_cok = max((g["sayi"] for g in gunler), default=0)
    for g in gunler:
        g["oran"] = round(100 * g["sayi"] / en_cok) if en_cok else 0

    return {"ortalama": ortalama, "aktif_hafta": aktif_hafta,
            "baslamayan": len(ogrenciler) - len(baslamis),
            "dagilim": dagilim, "gunler": gunler}


@app.route("/ogretmen/sinif/<int:sinif_id>", methods=["GET"])
@ogretmen_gerekli
def sinif_detay(sinif_id):
    """GET: Sınıftaki öğrencilerin ilerleme tablosu ve takıldıkları adımlar."""
    sinif = veritabani.sinif_getir(sinif_id, aktif_id())
    if sinif is None:
        abort(404)                         # Yoksa ya da başka öğretmenin sınıfıysa
    ogrenciler = sinif_ogrencileri(sinif_id)

    # Sınıf istatistikleri: son 14 günün etkinliği veritabanından, gerisi Python'da hesaplanır
    bugun = date.today()
    baslangic = bugun - timedelta(days=ISTATISTIK_GUN - 1)
    etkinlikler = veritabani.sinif_etkinlikleri(sinif_id, baslangic.isoformat())

    return render_template("sinif_detay.html", sinif=sinif, ogrenciler=ogrenciler,
                           istatistik=sinif_istatistigi(ogrenciler, etkinlikler, bugun),
                           takilanlar=veritabani.takilan_adimlar(sinif_id),
                           duyurular=veritabani.sinifin_duyurulari(sinif_id),
                           akis=veritabani.sinif_etkinlik_akisi(sinif_id),
                           proje_adimlari=proje_adim_dagilimi(sinif_id) if sinif["proje"] else [],
                           en_uzun_duyuru=EN_UZUN_DUYURU, en_uzun_proje=EN_UZUN_SINIF_PROJESI)


@app.route("/ogretmen/sinif/<int:sinif_id>/rapor", methods=["GET"])
@ogretmen_gerekli
def sinif_raporu(sinif_id):
    """
    GET: Sınıfın tek sayfalık, yazdırılabilir özeti (veli toplantısı, not verme için).
    Sınıf sayfasıyla AYNI verileri kullanır (sinif_ogrencileri, sinif_istatistigi...);
    sadece düğmeler ve formlar yok, yazdırmaya uygun bir düzen var.
    """
    sinif = veritabani.sinif_getir(sinif_id, aktif_id())
    if sinif is None:
        abort(404)
    ogrenciler = sinif_ogrencileri(sinif_id)
    bugun = date.today()
    etkinlikler = veritabani.sinif_etkinlikleri(
        sinif_id, (bugun - timedelta(days=ISTATISTIK_GUN - 1)).isoformat())
    return render_template("sinif_raporu.html", sinif=sinif, ogrenciler=ogrenciler,
                           istatistik=sinif_istatistigi(ogrenciler, etkinlikler, bugun),
                           takilanlar=veritabani.takilan_adimlar(sinif_id),
                           proje_adimlari=proje_adim_dagilimi(sinif_id) if sinif["proje"] else [],
                           gecikenler=[o for o in ogrenciler if o["geciken"]],
                           tarih=datetime.now().strftime("%d.%m.%Y %H:%M"))


def sinif_ogrencileri(sinif_id):
    """Sınıf sayfası ve sınıf raporu için öğrenci listesi (veritabanı satırları -> sözlükler)."""
    ogrenciler = []
    for satir in veritabani.sinif_ozeti(sinif_id):
        ogrenciler.append({
            "id": satir["id"],
            "kullanici_adi": satir["kullanici_adi"],
            "harita_sayisi": satir["harita_sayisi"],
            "biten": satir["biten_adim"],
            "toplam": satir["toplam_adim"],
            "yuzde": ilerleme_hesapla(satir["biten_adim"], satir["toplam_adim"]),
            "ipucu_sayisi": satir["ipucu_sayisi"],
            "commit_sayisi": satir["commit_sayisi"],
            "yz_hafta": satir["yz_hafta"],                   # Son 7 günde yapay zekâ isteği
            "geciken": satir["geciken_adim"],                # Hedef tarihi geçmiş, bitmemiş adım
            # Sınıf projesi: bu sınıfın projesi için çıkardığı yol haritası ve ilerlemesi
            "proje_harita_id": satir["proje_harita_id"],
            "proje_yuzde": ilerleme_hesapla(satir["proje_biten"], satir["proje_toplam"]),
            "proje_puan": satir["proje_puan"],
            "son_etkinlik": satir["son_etkinlik"] or None,   # '' ise "henüz yok"
        })
    return ogrenciler


EN_UZUN_DUYURU = 1000
EN_UZUN_SINIF_PROJESI = 1000


def proje_adim_dagilimi(sinif_id):
    """
    Sınıf projesinde her adım için: kaç öğrenci bitirdi, kaçı şu an o adımda, kaçı orada takıldı.
    "Şu an o adımda" = bitirmediği EN KÜÇÜK numaralı adım (sırayla ilerlediği varsayılır).
    "Takıldı" = şu an o adımda VE o adımda en az 2 ipucu almış.
    Örnek dönüş: [{"sira": 1, "biten": 3, "burada": 0, "takilan": 0, "oran": 100}, ...]
    """
    haritalar = {}                        # {harita_id: [(sira, tamamlandi, ipucu), ...]}
    for s in veritabani.sinif_projesi_adimlari(sinif_id):
        haritalar.setdefault(s["harita_id"], []).append((s["sira"], s["tamamlandi"], s["ipucu_sayisi"]))
    if not haritalar:
        return []

    en_cok_adim = max(len(adimlar) for adimlar in haritalar.values())
    dagilim = {sira: {"sira": sira, "biten": 0, "burada": 0, "takilan": 0}
               for sira in range(1, en_cok_adim + 1)}
    for adimlar in haritalar.values():
        bitmemisler = [(sira, ipucu) for sira, bitti, ipucu in adimlar if not bitti]
        for sira, bitti, _ in adimlar:
            if bitti:
                dagilim[sira]["biten"] += 1
        if bitmemisler:
            sira, ipucu = min(bitmemisler)                  # İlk bitmemiş adım
            dagilim[sira]["burada"] += 1
            if ipucu >= 2:
                dagilim[sira]["takilan"] += 1
    ogrenci_sayisi = len(haritalar)
    for satir in dagilim.values():
        satir["oran"] = round(satir["biten"] * 100 / ogrenci_sayisi)
    return list(dagilim.values())


@app.route("/ogretmen/sinif/<int:sinif_id>/proje", methods=["POST"])
@ogretmen_gerekli
def sinif_projesi(sinif_id):
    """
    POST: Öğretmen sınıfa ortak bir proje verir (boş gönderilirse projeyi kaldırır).
    Öğrenciler ana sayfada görür ve tek tıkla bu projeden yol haritası çıkarır.
    """
    if veritabani.sinif_getir(sinif_id, aktif_id()) is None:
        abort(404)
    proje = request.form.get("proje", "").strip()
    if len(proje) > EN_UZUN_SINIF_PROJESI:
        flash(f"Proje açıklaması en fazla {EN_UZUN_SINIF_PROJESI} karakter olabilir.", "hata")
    elif not proje:
        veritabani.sinif_proje_ayarla(sinif_id, None)
        flash("Sınıf projesi kaldırıldı. Öğrencilerin çıkardığı yol haritaları yerinde duruyor.", "bilgi")
    else:
        veritabani.sinif_proje_ayarla(sinif_id, proje)
        flash("Sınıf projesi kaydedildi. Öğrenciler ana sayfalarında görecek.", "bilgi")
    return redirect(url_for("sinif_detay", sinif_id=sinif_id) + "#sinif-projesi")


@app.route("/ogretmen/sinif/<int:sinif_id>/duyuru", methods=["POST"])
@ogretmen_gerekli
def duyuru_yaz(sinif_id):
    """POST: Öğretmen sınıfına duyuru yazar; sınıftaki bütün öğrenciler görür."""
    if veritabani.sinif_getir(sinif_id, aktif_id()) is None:
        abort(404)                         # Başka öğretmenin sınıfına duyuru yazılamaz
    metin = request.form.get("metin", "").strip()
    if not metin or len(metin) > EN_UZUN_DUYURU:
        flash(f"Duyuru 1-{EN_UZUN_DUYURU} karakter olmalı.", "hata")
    else:
        veritabani.duyuru_ekle(sinif_id, metin)
        flash("Duyuru gönderildi. Öğrenciler ana sayfalarında görecek.", "bilgi")
    return redirect(url_for("sinif_detay", sinif_id=sinif_id) + "#duyurular")


@app.route("/ogretmen/duyuru/<int:duyuru_id>/sil", methods=["POST"])
@ogretmen_gerekli
def duyuru_sil(duyuru_id):
    """POST: Öğretmen kendi sınıfındaki bir duyuruyu siler."""
    sinif_id = veritabani.duyuru_sil(duyuru_id, aktif_id())
    if sinif_id is None:
        abort(404)
    flash("Duyuru silindi.", "bilgi")
    return redirect(url_for("sinif_detay", sinif_id=sinif_id) + "#duyurular")


@app.route("/ogretmen/sinif/<int:sinif_id>/indir", methods=["GET"])
@ogretmen_gerekli
def sinif_indir(sinif_id):
    """
    GET: Sınıfın ilerleme tablosunu CSV dosyası olarak indirir (Excel'de açılır).

    CSV (Comma-Separated Values): Her satırın bir kayıt, değerlerin ayraçla
    ayrıldığı düz metin tablo. Türkçe Excel ondalık için virgül kullandığından
    ayraç olarak noktalı virgül (;) seçtik.
    """
    sinif = veritabani.sinif_getir(sinif_id, aktif_id())
    if sinif is None:
        abort(404)

    # Dosyayı diske yazmadan, bellekte (StringIO) oluşturuyoruz
    bellek = io.StringIO()
    yazici = csv.writer(bellek, delimiter=";")
    yazici.writerow(["Öğrenci", "Yol haritası", "Tamamlanan adım", "Toplam adım",
                     "İlerleme (%)", "İpucu", "Commit", "Yapay zekâ (7 gün)", "Son etkinlik",
                     "Sınıfa katılma", "Geciken adım"])
    # Not: Kullanıcı adları sadece harf/rakam/nokta/alt çizgi içerebildiği için
    # Excel'in formül sanabileceği (=, +, -, @ ile başlayan) bir değer oluşamaz.
    for satir in veritabani.sinif_ozeti(sinif_id):
        yazici.writerow([
            satir["kullanici_adi"],
            satir["harita_sayisi"],
            satir["biten_adim"],
            satir["toplam_adim"],
            ilerleme_hesapla(satir["biten_adim"], satir["toplam_adim"]),
            satir["ipucu_sayisi"],
            satir["commit_sayisi"],
            satir["yz_hafta"],
            tarih_bicimle(satir["son_etkinlik"]) if satir["son_etkinlik"] else "",
            tarih_bicimle(satir["katilma_zamani"]),
            satir["geciken_adim"],
        ])

    # "﻿" (BOM): Excel'e dosyanın UTF-8 olduğunu söyler; yoksa ğ, ş, ı bozuk görünür
    veri = ("﻿" + bellek.getvalue()).encode("utf-8")
    # Dosya adında sadece harf, rakam, boşluk ve tire kalsın
    ad = re.sub(r"[^\w\- ]", "", sinif["ad"])
    ad = re.sub(r"\s+", " ", ad).strip() or "sinif"         # Art arda boşlukları teke indir
    tarih = datetime.now().strftime("%Y-%m-%d")
    return send_file(io.BytesIO(veri), mimetype="text/csv", as_attachment=True,
                     download_name=f"{ad} - {tarih}.csv")


@app.route("/ogretmen/sinif/<int:sinif_id>/sil", methods=["POST"])
@ogretmen_gerekli
def sinif_sil(sinif_id):
    """POST: Sınıfı kapatır (öğrencilerin yol haritaları silinmez)."""
    if not veritabani.sinif_sil(sinif_id, aktif_id()):
        abort(404)
    flash("Sınıf silindi. Öğrencilerin yol haritaları yerinde duruyor.", "bilgi")
    return redirect(url_for("ogretmen_paneli"))


@app.route("/ogretmen/ogrenci/<int:ogrenci_id>", methods=["GET"])
@ogretmen_gerekli
def ogrenci_detay(ogrenci_id, gecici_sifre=None):
    """
    GET: Bir öğrencinin bütün yol haritalarını listeler (sadece kendi sınıfındaysa).
    gecici_sifre: Şifre az önce sıfırlandıysa sayfada bir kez gösterilir.
    """
    if not veritabani.ogretmen_gorebilir_mi(aktif_id(), ogrenci_id):
        abort(404)
    ogrenci = veritabani.kullanici_getir(ogrenci_id)
    haritalar = []
    for satir in veritabani.tum_yol_haritalari(ogrenci_id):
        haritalar.append({
            "id": satir["id"],
            "proje": satir["proje"],
            "olusturma_zamani": satir["olusturma_zamani"],
            "toplam": satir["toplam_adim"],
            "tamamlanan": satir["tamamlanan_adim"],
            "yuzde": ilerleme_hesapla(satir["tamamlanan_adim"], satir["toplam_adim"]),
            "yorum_sayisi": satir["yorum_sayisi"],
            "yeni_yorum_sayisi": satir["yeni_yorum_sayisi"],
            "puan": satir["degerlendirme_puan"],             # Öğretmenin değerlendirmesi (1-5)
        })
    # "Geri" bağlantısı: adreste ?sinif=3 varsa ve o sınıf bu öğretmeninse sınıfa dön,
    # yoksa panele dön. type=int: sayı olmayan değerleri yok sayar.
    sinif_id = request.args.get("sinif", type=int)
    if sinif_id and veritabani.sinif_getir(sinif_id, aktif_id()):
        geri_adres = url_for("sinif_detay", sinif_id=sinif_id)
    else:
        geri_adres = url_for("ogretmen_paneli")
    return render_template("ogrenci_detay.html", ogrenci=ogrenci, haritalar=haritalar,
                           geri_adres=geri_adres, rozetler=rozetleri_hesapla(ogrenci_id),
                           gecici_sifre=gecici_sifre)


@app.route("/ogretmen/ogrenci/<int:ogrenci_id>/sifre-sifirla", methods=["POST"])
@ogretmen_gerekli
def ogrenci_sifre_sifirla(ogrenci_id):
    """
    POST: Şifresini unutan öğrenciye geçici şifre verir. (E-posta sistemimiz yok;
    okulda şifresini unutan öğrenci zaten öğretmenine gider.)
    Sadece kendi sınıfındaki ÖĞRENCİLER için: başka bir öğretmenin şifresi sıfırlanamaz.
    Geçici şifre bir kez, bu sayfada gösterilir; hiçbir yere kaydedilmez (sadece hash'i).
    """
    ogrenci = veritabani.kullanici_getir(ogrenci_id)
    if (ogrenci is None or ogrenci["rol"] != "ogrenci"
            or not veritabani.ogretmen_gorebilir_mi(aktif_id(), ogrenci_id)):
        abort(404)
    sifre = veritabani.gecici_sifre_ver(ogrenci_id)
    # Yönlendirme (redirect) yapmıyoruz: şifreyi flash ile çereze koymak yerine sayfayı
    # doğrudan gösteriyoruz. Böylece geçici şifre tarayıcının çerezinde saklanmıyor.
    cevap = make_response(ogrenci_detay(ogrenci_id, gecici_sifre=sifre))
    cevap.headers["Cache-Control"] = "no-store"     # Tarayıcı bu sayfayı (şifreyi) önbellekte saklamasın
    return cevap


@app.route("/ogretmen/ogrenci/<int:ogrenci_id>/yol-haritasi/<int:harita_id>", methods=["GET"])
@ogretmen_gerekli
def ogrenci_yol_haritasi(ogrenci_id, harita_id):
    """GET: Öğrencinin bir yol haritasını SALT OKUNUR olarak gösterir."""
    if not veritabani.ogretmen_gorebilir_mi(aktif_id(), ogrenci_id):
        abort(404)
    harita, adim_satirlari = veritabani.yol_haritasi_getir(harita_id, ogrenci_id)
    if harita is None:
        abort(404)
    ogrenci = veritabani.kullanici_getir(ogrenci_id)
    return yol_haritasi_sayfasi(harita, adim_satirlari, ogretmen_gorunumu={
        "ogrenci_id": ogrenci_id,
        "ogrenci_adi": ogrenci["kullanici_adi"],
        "geri_adres": url_for("ogrenci_detay", ogrenci_id=ogrenci_id),
    })


EN_UZUN_YORUM = 1000


@app.route("/ogretmen/ogrenci/<int:ogrenci_id>/adim/<int:adim_id>/yorum", methods=["POST"])
@ogretmen_gerekli
def yorum_yaz(ogrenci_id, adim_id):
    """POST: Öğretmen, sınıfındaki bir öğrencinin adımına yorum bırakır."""
    if not veritabani.ogretmen_gorebilir_mi(aktif_id(), ogrenci_id):
        abort(404)
    adim = veritabani.adim_getir(adim_id, ogrenci_id)     # Adım gerçekten bu öğrencinin mi?
    if adim is None:
        abort(404)

    geri = url_for("ogrenci_yol_haritasi", ogrenci_id=ogrenci_id,
                   harita_id=adim["yol_haritasi_id"]) + f"#adim-{adim_id}"
    metin = request.form.get("metin", "").strip()
    if not metin or len(metin) > EN_UZUN_YORUM:
        flash(f"Yorum 1-{EN_UZUN_YORUM} karakter olmalı.", "hata")
        return redirect(geri)

    veritabani.yorum_ekle(adim_id, aktif_id(), metin)
    flash("Yorumun öğrenciye iletildi.", "bilgi")
    return redirect(geri)


def hedef_tarihi_oku(metin):
    """
    Formdan gelen tarihi kontrol eder. (tarih, None) ya da (None, hata mesajı) döndürür.
    Tarayıcının tarih kutusu "2026-11-21" gönderir; yine de gerçekten tarih mi diye bakıyoruz
    ve bugünden en fazla bir yıl önce/sonra olmasına izin veriyoruz.
    """
    try:
        tarih = date.fromisoformat(metin)
    except ValueError:
        return None, "Tarihi anlayamadım."
    bugun = date.today()
    if not bugun - timedelta(days=365) <= tarih <= bugun + timedelta(days=365):
        return None, "Hedef tarih bugünden en fazla bir yıl önce ya da sonra olabilir."
    return tarih, None


@app.route("/ogretmen/ogrenci/<int:ogrenci_id>/adim/<int:adim_id>/hedef", methods=["POST"])
@ogretmen_gerekli
def hedef_tarih_koy(ogrenci_id, adim_id):
    """
    POST: Öğretmen öğrencinin bir adımına hedef tarih koyar (boş gönderilirse hedefi kaldırır).
    Tarayıcının tarih kutusu (<input type="date">) değeri "2026-11-21" biçiminde gönderir;
    yine de formdan gelene güvenmeyip date.fromisoformat ile gerçekten tarih mi diye bakıyoruz.
    """
    if not veritabani.ogretmen_gorebilir_mi(aktif_id(), ogrenci_id):
        abort(404)
    adim = veritabani.adim_getir(adim_id, ogrenci_id)     # Adım gerçekten bu öğrencinin mi?
    if adim is None:
        abort(404)
    geri = url_for("ogrenci_yol_haritasi", ogrenci_id=ogrenci_id,
                   harita_id=adim["yol_haritasi_id"]) + f"#adim-{adim_id}"

    metin = request.form.get("tarih", "").strip()
    if not metin:
        veritabani.hedef_tarih_ayarla(adim_id, None)
        flash("Hedef tarih kaldırıldı.", "bilgi")
        return redirect(geri)
    tarih, hata = hedef_tarihi_oku(metin)
    if hata:
        flash(hata, "hata")
        return redirect(geri)
    veritabani.hedef_tarih_ayarla(adim_id, tarih.isoformat(), "ogretmen")
    flash(f"Hedef tarih {tarih.strftime('%d.%m.%Y')} olarak kaydedildi. Öğrenci ana sayfasında görecek.", "bilgi")
    return redirect(geri)


EN_UZUN_DEGERLENDIRME = 1000
EN_UZUN_OGRETMEN_CEVABI = 1000


@app.route("/ogretmen/soru/<int:soru_id>/cevap", methods=["POST"])
@ogretmen_gerekli
def ogretmen_cevapla(soru_id):
    """POST: Öğretmen, sınıfındaki bir öğrencinin sorusunu cevaplar (cevap sonradan düzeltilebilir)."""
    soru = veritabani.ogretmen_sorusu_getir(soru_id)
    if soru is None or not veritabani.ogretmen_gorebilir_mi(aktif_id(), soru["ogrenci_id"]):
        abort(404)
    geri = url_for("ogrenci_yol_haritasi", ogrenci_id=soru["ogrenci_id"],
                   harita_id=soru["harita_id"]) + f"#adim-{soru['adim_id']}"
    cevap = request.form.get("cevap", "").strip()
    if not cevap or len(cevap) > EN_UZUN_OGRETMEN_CEVABI:
        flash(f"Cevap 1-{EN_UZUN_OGRETMEN_CEVABI} karakter olmalı.", "hata")
        return redirect(geri)
    paylas = request.form.get("paylas") == "1"      # Onay kutusu işaretliyse "1" gelir, değilse hiç gelmez
    veritabani.ogretmen_sorusunu_cevapla(soru_id, aktif_id(), cevap, paylas)
    flash("Cevabın öğrenciye iletildi." + (" Soru-cevap sınıflarınla da paylaşıldı (soranın adı görünmez)."
                                           if paylas else ""), "bilgi")
    return redirect(geri)


@app.route("/ogretmen/sinif/<int:sinif_id>/toplu-hedef", methods=["POST"])
@ogretmen_gerekli
def toplu_hedef(sinif_id):
    """
    POST: Sınıf projesinde bütün öğrencilerin N. adımına aynı hedef tarihi koyar
    (ör. "herkes 2. adımı Cuma'ya kadar bitirsin"). Tek tek her öğrenciye girmek gerekmez.
    """
    sinif = veritabani.sinif_getir(sinif_id, aktif_id())
    if sinif is None:
        abort(404)
    geri = url_for("sinif_detay", sinif_id=sinif_id) + "#sinif-projesi"
    if not sinif["proje"]:
        flash("Toplu hedef için önce sınıfa bir proje ver.", "hata")
        return redirect(geri)
    sira = request.form.get("sira", type=int)
    if not sira or not 1 <= sira <= 50:
        flash("Adım numarası 1 ile 50 arasında olmalı.", "hata")
        return redirect(geri)
    tarih, hata = hedef_tarihi_oku(request.form.get("tarih", "").strip())
    if hata:
        flash(hata, "hata")
        return redirect(geri)
    sayi = veritabani.toplu_hedef_koy(sinif_id, sira, tarih.isoformat())
    if sayi:
        flash(f"{sayi} öğrencinin {sira}. adımına {tarih.strftime('%d.%m.%Y')} hedefi kondu.", "bilgi")
    else:
        flash(f"Sınıf projesinde {sira}. adımı olan öğrenci yok (henüz kimse başlamamış olabilir).", "hata")
    return redirect(geri)


@app.route("/ogretmen/ogrenci/<int:ogrenci_id>/yol-haritasi/<int:harita_id>/degerlendir", methods=["POST"])
@ogretmen_gerekli
def degerlendir(ogrenci_id, harita_id):
    """
    POST: Öğretmen öğrencinin yol haritasına 1-5 puan ve kısa geri bildirim verir.
    Puan boş gönderilirse değerlendirme kaldırılır.
    """
    if not veritabani.ogretmen_gorebilir_mi(aktif_id(), ogrenci_id):
        abort(404)
    harita, _ = veritabani.yol_haritasi_getir(harita_id, ogrenci_id)   # Gerçekten bu öğrencinin mi?
    if harita is None:
        abort(404)
    geri = url_for("ogrenci_yol_haritasi", ogrenci_id=ogrenci_id, harita_id=harita_id) + "#degerlendirme"

    puan_metni = request.form.get("puan", "").strip()
    metin = request.form.get("metin", "").strip()
    if not puan_metni:
        veritabani.yol_haritasi_degerlendir(harita_id, aktif_id(), None, None)
        flash("Değerlendirme kaldırıldı.", "bilgi")
        return redirect(geri)
    if puan_metni not in {"1", "2", "3", "4", "5"}:
        flash("Puan 1 ile 5 arasında olmalı.", "hata")
        return redirect(geri)
    if len(metin) > EN_UZUN_DEGERLENDIRME:
        flash(f"Geri bildirim en fazla {EN_UZUN_DEGERLENDIRME} karakter olabilir.", "hata")
        return redirect(geri)
    veritabani.yol_haritasi_degerlendir(harita_id, aktif_id(), int(puan_metni), metin or None)
    flash("Değerlendirme kaydedildi. Öğrenci yol haritasının en üstünde görecek.", "bilgi")
    return redirect(geri)


@app.route("/ogretmen/sinif/<int:sinif_id>/ogrenci/<int:ogrenci_id>/cikar", methods=["POST"])
@ogretmen_gerekli
def siniftan_cikar(sinif_id, ogrenci_id):
    """
    POST: Öğretmen bir öğrenciyi sınıfından çıkarır (ör. yanlışlıkla katılan biri).
    Öğrencinin yol haritalarına DOKUNULMAZ; sadece öğretmen artık onu göremez.
    """
    if veritabani.sinif_getir(sinif_id, aktif_id()) is None:
        abort(404)                          # Başka öğretmenin sınıfından kimse çıkarılamaz
    veritabani.siniftan_ayril(ogrenci_id, sinif_id)
    flash("Öğrenci sınıftan çıkarıldı. Yol haritaları silinmedi; isterse kodla yeniden katılabilir.", "bilgi")
    return redirect(url_for("sinif_detay", sinif_id=sinif_id))


@app.route("/ogretmen/yorum/<int:yorum_id>/sil", methods=["POST"])
@ogretmen_gerekli
def yorum_sil(yorum_id):
    """POST: Öğretmen kendi yorumunu siler."""
    sonuc = veritabani.yorum_sil(yorum_id, aktif_id())
    if sonuc is None:
        abort(404)
    ogrenci_id, harita_id, adim_id = sonuc          # "Demet açma": üç değeri tek satırda al
    flash("Yorum silindi.", "bilgi")
    return redirect(url_for("ogrenci_yol_haritasi", ogrenci_id=ogrenci_id,
                            harita_id=harita_id) + f"#adim-{adim_id}")


# ---------------------------------------------------------------------------
# Profiller ve mesajlaşma (sınıf sohbeti + özel mesaj)
# ---------------------------------------------------------------------------
#
# Yeni mesajlar sayfayı yenilemeden nasıl geliyor?
#   Sohbet sayfasındaki küçük betik birkaç saniyede bir /sohbet/yeni adresine sorar:
#   "şu id'den sonra yeni mesaj var mı?" Sunucu JSON (JavaScript'in okuyabildiği veri) döndürür,
#   betik yeni mesajları listeye ekler. Buna "polling" (yoklama) denir. Daha gelişmiş yolu
#   WebSocket (sunucunun kendisinin haber vermesi) ama bu ölçekte yoklama yeterli ve basit.

EN_UZUN_MESAJ = 1000
EN_FAZLA_MESAJ_DAKIKA = 20       # Bir dakikada en fazla kaç mesaj (sohbeti boğmayı önler)
EN_UZUN_HAKKIMDA = 300
YOKLAMA_SANIYESI = 5             # Sohbet sayfası kaç saniyede bir yeni mesaj sorar


# Kötü kelime süzgeci. Kelimenin TAMAMI listedeyse ya da "kök" ile başlıyorsa yıldızlanır.
# Kökler bilerek uzun ve belirgin seçildi: "göt" gibi kısa bir kök "götür"ü de yakalardı.
KOTU_KELIMELER = {
    "amk", "aq", "amq", "amına", "aminakoyim", "oç", "piç", "sik", "sikerim", "sikeyim",
    "siktir", "yarrak", "yarak", "göt", "ibne", "kahpe", "gavat", "pezevenk", "orospu",
    "salak", "aptal", "gerizekalı", "gerizekali", "dangalak", "şerefsiz", "serefsiz",
}
# Bilerek listede OLMAYANLAR: "mal" (mal varlığı), "got"/"pic" (İngilizce "I got", "pic") gibi
# başka anlamı da olan kelimeler. Süzgeç tam değildir; asıl koruma bildir/engelle ve öğretmen.
KOTU_KOKLER = ("siktir", "orospu", "yarrak", "pezevenk", "şerefsiz", "serefsiz", "gerizekal", "aminakoy")


def turkce_kucuk(metin):
    """Türkçe küçük harf: Python'un lower()'ı 'I'yı 'i' yapar, Türkçede 'ı' olmalı."""
    return metin.replace("I", "ı").replace("İ", "i").lower()


def kufur_suz(metin):
    """Mesajdaki kötü kelimeleri ilk harfi kalacak şekilde yıldızlar: 'salak' -> 's****'."""
    def degistir_(eslesme):
        kelime = eslesme.group(0)
        kucuk = turkce_kucuk(kelime)
        if kucuk in KOTU_KELIMELER or kucuk.startswith(KOTU_KOKLER):
            return kelime[0] + "*" * (len(kelime) - 1)
        return kelime
    return re.sub(r"\w+", degistir_, metin)


SIKAYET_SEBEPLERI = {"kufur": "Küfür / hakaret", "zorbalik": "Zorbalık / tehdit",
                     "spam": "Spam / rahatsız edici", "diger": "Diğer"}


def mesaj_atabilir_mi(gonderen_id, alici_id):
    return any(k["id"] == alici_id for k in veritabani.mesaj_atabilecegi_kisiler(gonderen_id))


def mesaj_metnini_oku():
    """Formdaki mesajı kontrol eder; uygunsa metni, değilse (mesaj gösterip) None döndürür."""
    metin = request.form.get("metin", "").strip()
    if not metin:
        return None
    if len(metin) > EN_UZUN_MESAJ:
        flash(f"Mesaj en fazla {EN_UZUN_MESAJ} karakter olabilir.", "hata")
        return None
    if veritabani.son_dakika_mesaj_sayisi(aktif_id()) >= EN_FAZLA_MESAJ_DAKIKA:
        flash("Çok hızlı mesaj gönderiyorsun; biraz bekleyip tekrar dene.", "hata")
        return None
    return kufur_suz(metin)


def mesaj_sozlugu(m, sinif=None):
    """Bir mesaj satırını şablonun ve JSON'un kullanacağı sözlüğe çevirir."""
    silebilir = (m["gonderen_id"] == aktif_id()
                 or (sinif is not None and sinif["ogretmen_id"] == aktif_id()))
    return {
        "id": m["id"],
        "gonderen": m["gonderen_adi"],
        "ogretmen": m["gonderen_rol"] == "ogretmen",
        "profil": url_for("profil_goster", kullanici_id=m["gonderen_id"]),
        "metin": "" if m["silindi"] else m["metin"],
        "silindi": bool(m["silindi"]),
        "zaman": tarih_bicimle(m["zaman"]),
        "benim": m["gonderen_id"] == aktif_id(),
        "silebilir": silebilir and not m["silindi"],
        # Öğrenci, başka bir öğrencinin mesajını öğretmene bildirebilir
        "bildirebilir": (g.kullanici["rol"] == "ogrenci" and m["gonderen_id"] != aktif_id()
                         and m["gonderen_rol"] == "ogrenci" and not m["silindi"]),
    }


@app.route("/mesajlar", methods=["GET"])
@giris_gerekli
def mesajlar():
    """GET: Sınıf sohbetleri, özel sohbetler ve yeni sohbet başlatılabilecek kişiler."""
    siniflar, kisiler = veritabani.sohbet_listesi(aktif_id())
    konusulanlar = {k["diger_id"] for k in kisiler}
    yeni_kisiler = [k for k in veritabani.mesaj_atabilecegi_kisiler(aktif_id()) if k["id"] not in konusulanlar]
    return render_template("mesajlar.html", siniflar=siniflar, kisiler=kisiler, yeni_kisiler=yeni_kisiler)


@app.route("/sinif/<int:sinif_id>/sohbet", methods=["GET", "POST"])
@giris_gerekli
def sinif_sohbeti(sinif_id):
    """GET: Sınıfın grup sohbeti. POST: Sohbete mesaj yazar. Sadece sınıfın öğretmeni ve üyeleri."""
    sinif = veritabani.sinifta_mi(aktif_id(), sinif_id)
    if sinif is None:
        abort(404)
    ogretmen_mi = sinif["ogretmen_id"] == aktif_id()
    yazabilir = ogretmen_mi or not sinif["sohbet_kilitli"]

    if request.method == "POST":
        if not yazabilir:
            flash("Bu sohbete şu an sadece öğretmen yazabiliyor.", "hata")
        else:
            metin = mesaj_metnini_oku()
            if metin:
                veritabani.mesaj_ekle(aktif_id(), metin, sinif_id=sinif_id)
        return redirect(url_for("sinif_sohbeti", sinif_id=sinif_id) + "#yaz")

    mesaj_listesi = [mesaj_sozlugu(m, sinif) for m in veritabani.sinif_mesajlari(sinif_id, izleyen_id=aktif_id())]
    son_id = mesaj_listesi[-1]["id"] if mesaj_listesi else 0
    if son_id:
        veritabani.okundu_yap(aktif_id(), son_id, sinif_id=sinif_id)
    return render_template("sohbet.html", baslik=sinif["ad"], sinif=sinif, mesaj_listesi=mesaj_listesi,
                           son_id=son_id, yazabilir=yazabilir, ogretmen_mi=ogretmen_mi,
                           uyeler=veritabani.sinif_uyeleri_listesi(sinif_id),
                           gonder_adresi=url_for("sinif_sohbeti", sinif_id=sinif_id),
                           yoklama_adresi=url_for("sohbet_yeni", sinif=sinif_id),
                           en_uzun=EN_UZUN_MESAJ, yoklama=YOKLAMA_SANIYESI, sebepler=SIKAYET_SEBEPLERI)


@app.route("/mesaj/<int:kisi_id>", methods=["GET", "POST"])
@giris_gerekli
def ozel_sohbet(kisi_id):
    """
    GET: Bir kişiyle özel sohbet. POST: O kişiye mesaj gönderir.
    Yazmak için ortak bir sınıf gerekir (mesaj_atabilir_mi). Artık ortak sınıf yoksa
    (ör. öğrenci sınıftan ayrıldı) eski mesajlar okunabilir ama yenisi yazılamaz.
    """
    if kisi_id == aktif_id():
        abort(404)
    kisi = veritabani.kullanici_getir(kisi_id)
    if kisi is None:
        abort(404)
    yazabilir = mesaj_atabilir_mi(aktif_id(), kisi_id)
    mesaj_satirlari = veritabani.ozel_mesajlar(aktif_id(), kisi_id)
    if not yazabilir and not mesaj_satirlari:
        abort(404)                         # Tanımadığı birine sohbet açamaz (var olup olmadığı da sızmaz)

    if request.method == "POST":
        if not yazabilir:
            flash("Bu kişiyle artık ortak bir sınıfın yok ya da öğretmen özel mesajı kapattı.", "hata")
        else:
            metin = mesaj_metnini_oku()
            if metin:
                veritabani.mesaj_ekle(aktif_id(), metin, alici_id=kisi_id)
        return redirect(url_for("ozel_sohbet", kisi_id=kisi_id) + "#yaz")

    mesaj_listesi = [mesaj_sozlugu(m) for m in mesaj_satirlari]
    son_id = mesaj_listesi[-1]["id"] if mesaj_listesi else 0
    if son_id:
        veritabani.okundu_yap(aktif_id(), son_id, diger_id=kisi_id)
    return render_template("sohbet.html", baslik=kisi["kullanici_adi"], kisi=kisi, mesaj_listesi=mesaj_listesi,
                           son_id=son_id, yazabilir=yazabilir,
                           engelli=(veritabani.engelledi_mi(aktif_id(), kisi_id)
                                    or veritabani.engelledi_mi(kisi_id, aktif_id())),
                           gonder_adresi=url_for("ozel_sohbet", kisi_id=kisi_id),
                           yoklama_adresi=url_for("sohbet_yeni", kisi=kisi_id),
                           en_uzun=EN_UZUN_MESAJ, yoklama=YOKLAMA_SANIYESI, sebepler=SIKAYET_SEBEPLERI)


@app.route("/sohbet/yeni", methods=["GET"])
@giris_gerekli
def sohbet_yeni():
    """
    GET (JSON): Sohbet sayfasındaki betiğin yoklaması. ?sinif=3&sonra=120 ya da ?kisi=7&sonra=120
    "sonra" id'sinden sonraki mesajları döndürür ve onları okundu sayar.
    """
    sonra = request.args.get("sonra", 0, type=int)
    sinif_id = request.args.get("sinif", type=int)
    kisi_id = request.args.get("kisi", type=int)
    if sinif_id:
        sinif = veritabani.sinifta_mi(aktif_id(), sinif_id)
        if sinif is None:
            abort(404)
        yeniler = [mesaj_sozlugu(m, sinif)
                   for m in veritabani.sinif_mesajlari(sinif_id, sonra, izleyen_id=aktif_id())]
        if yeniler:
            veritabani.okundu_yap(aktif_id(), yeniler[-1]["id"], sinif_id=sinif_id)
    elif kisi_id:
        yeniler = [mesaj_sozlugu(m) for m in veritabani.ozel_mesajlar(aktif_id(), kisi_id, sonra)]
        if yeniler:
            veritabani.okundu_yap(aktif_id(), yeniler[-1]["id"], diger_id=kisi_id)
    else:
        abort(404)
    # Silebileceği mesajlar için sil düğmesi betikte yok (sayfa yenilenince görünür)
    return jsonify({"mesajlar": yeniler})


@app.route("/mesaj/<int:mesaj_id>/sil", methods=["POST"])
@giris_gerekli
def mesaj_sil(mesaj_id):
    """POST: Mesajı siler. Kendi mesajını herkes; sınıf sohbetindeki her mesajı o sınıfın öğretmeni."""
    m = veritabani.mesaj_getir(mesaj_id)
    if m is None or not (m["gonderen_id"] == aktif_id()
                         or (m["sinif_id"] and m["ogretmen_id"] == aktif_id())):
        abort(404)
    veritabani.mesaj_sil(mesaj_id)
    flash("Mesaj silindi.", "bilgi")
    if m["sinif_id"]:
        return redirect(url_for("sinif_sohbeti", sinif_id=m["sinif_id"]))
    diger = m["alici_id"] if m["gonderen_id"] == aktif_id() else m["gonderen_id"]
    return redirect(url_for("ozel_sohbet", kisi_id=diger))


@app.route("/ogretmen/sinif/<int:sinif_id>/sohbet-ayar", methods=["POST"])
@ogretmen_gerekli
def sohbet_ayari(sinif_id):
    """POST: Öğretmen sınıf sohbetini kilitler/açar ve öğrenciler arası özel mesajı açar/kapatır."""
    if veritabani.sinif_getir(sinif_id, aktif_id()) is None:
        abort(404)
    veritabani.sohbet_ayarla(sinif_id, request.form.get("kilitli") == "1",
                             request.form.get("ozel_mesaj") == "1")
    flash("Sohbet ayarları kaydedildi.", "bilgi")
    return redirect(url_for("sinif_sohbeti", sinif_id=sinif_id))


@app.route("/mesaj/<int:mesaj_id>/bildir", methods=["POST"])
@giris_gerekli
def mesaj_bildir(mesaj_id):
    """
    POST: Öğrenci, rahatsız edici bir mesajı öğretmenine bildirir.
    Sadece görebildiği mesajı bildirebilir: sınıfındaki sohbetten ya da kendisine gelen özel mesaj.
    """
    m = veritabani.mesaj_getir(mesaj_id)
    if m is None or g.kullanici["rol"] != "ogrenci" or m["gonderen_id"] == aktif_id():
        abort(404)
    gorebilir = (veritabani.sinifta_mi(aktif_id(), m["sinif_id"]) is not None if m["sinif_id"]
                 else m["alici_id"] == aktif_id())
    if not gorebilir:
        abort(404)
    sebep = request.form.get("sebep", "diger")
    if sebep not in SIKAYET_SEBEPLERI:
        sebep = "diger"
    veritabani.sikayet_ekle(mesaj_id, aktif_id(), sebep)
    flash("Mesaj öğretmenine bildirildi. Teşekkürler; istersen kişiyi profilinden engelleyebilirsin.", "bilgi")
    if m["sinif_id"]:
        return redirect(url_for("sinif_sohbeti", sinif_id=m["sinif_id"]))
    return redirect(url_for("ozel_sohbet", kisi_id=m["gonderen_id"]))


def sikayet_bul(sikayet_id):
    """Öğretmenin görebileceği açık bir bildirim mi? Değilse 404."""
    for s in veritabani.ogretmenin_sikayetleri(aktif_id()):
        if s["id"] == sikayet_id:
            return s
    abort(404)


@app.route("/ogretmen/sikayet/<int:sikayet_id>/sil", methods=["POST"])
@ogretmen_gerekli
def sikayet_mesaji_sil(sikayet_id):
    """POST: Öğretmen bildirilen mesajı siler ve bildirimi kapatır."""
    s = sikayet_bul(sikayet_id)
    veritabani.mesaj_sil(s["mesaj_id"])
    veritabani.sikayetleri_kapat(s["mesaj_id"])
    flash("Mesaj silindi ve bildirim kapatıldı.", "bilgi")
    return redirect(url_for("ogretmen_paneli") + "#bildirimler")


@app.route("/ogretmen/sikayet/<int:sikayet_id>/kapat", methods=["POST"])
@ogretmen_gerekli
def sikayet_kapat(sikayet_id):
    """POST: Öğretmen baktı, sorun görmedi: mesaj kalır, bildirim kapanır."""
    s = sikayet_bul(sikayet_id)
    veritabani.sikayetleri_kapat(s["mesaj_id"])
    flash("Bildirim kapatıldı.", "bilgi")
    return redirect(url_for("ogretmen_paneli") + "#bildirimler")


@app.route("/kullanici/<int:kullanici_id>/engelle", methods=["POST"])
@giris_gerekli
def engelle(kullanici_id):
    """
    POST: Öğrenci başka bir öğrenciyi engeller ya da engeli kaldırır (formdaki 'islem').
    Öğretmen engellenemez (öğrenci öğretmenine her zaman ulaşabilmeli, öğretmen de ona);
    öğretmen istemediği öğrenciyi zaten sınıftan çıkarabilir.
    """
    kisi = veritabani.kullanici_getir(kullanici_id)
    if (kisi is None or kullanici_id == aktif_id() or kisi["rol"] != "ogrenci"
            or g.kullanici["rol"] != "ogrenci"):
        abort(404)
    if request.form.get("islem") == "kaldir":
        veritabani.engeli_kaldir(aktif_id(), kullanici_id)
        flash(f"{kisi['kullanici_adi']} için engel kaldırıldı.", "bilgi")
    else:
        if not veritabani.ortak_siniflar(aktif_id(), kullanici_id) and not veritabani.ozel_mesajlar(aktif_id(), kullanici_id):
            abort(404)
        veritabani.engelle(aktif_id(), kullanici_id)
        flash(f"{kisi['kullanici_adi']} engellendi: mesajlarını görmeyeceksin, sana özel mesaj atamaz.", "bilgi")
    # "geri" formdan geliyor; sadece site içi bir adrese ("/..." ama "//başka-site" değil) dönülür.
    # Yoksa biri, kullanıcıyı KodKoç'tan başka bir siteye yönlendiren bir form hazırlayabilirdi.
    geri = request.form.get("geri", "")
    if not geri.startswith("/") or geri.startswith("//") or "\\" in geri:
        geri = url_for("mesajlar")
    return redirect(geri)


@app.route("/kod-dene", methods=["GET"])
@giris_gerekli
def kod_dene():
    """
    GET: Python'u tarayıcıda çalıştırma sayfası. ?adim=12 ile açılırsa o adımın başlığı görünür,
    kod o adım için ayrı saklanır ve tek tıkla "Kodumu incelet"e gönderilebilir.
    Kod sunucuda ÇALIŞMAZ; sayfa sadece arayüzü verir (bkz. static/python_isci.js).
    """
    adim = None
    adim_id = request.args.get("adim", type=int)
    if adim_id:
        adim = veritabani.adim_getir(adim_id, aktif_id())      # Sadece kendi adımı
        if adim is None:
            abort(404)
    hak = EN_FAZLA_INCELEME - veritabani.adimin_inceleme_sayisi(adim_id) if adim else 0
    return render_template("kod_dene.html", adim=adim, inceleme_hakki=hak, en_uzun_kod=EN_UZUN_KOD)


@app.route("/gizlilik", methods=["GET"])
def gizlilik():
    """GET: Hangi verileri neden sakladığımızı anlatan sayfa (giriş gerekmez)."""
    return render_template("gizlilik.html")


@app.route("/kullanici/<int:kullanici_id>", methods=["GET"])
@giris_gerekli
def profil_goster(kullanici_id):
    """
    GET: Bir kullanıcının profili: kendini tanıttığı yazı, rozetleri, ortak sınıflar.
    Sadece aynı sınıfta olanlar görebilir (sınıf dışındaki biri öğrencinin profilini göremez).
    """
    kisi = veritabani.hesap_bilgileri(kullanici_id)
    ortak = veritabani.ortak_siniflar(aktif_id(), kullanici_id)
    engelledi = veritabani.engelledi_mi(aktif_id(), kullanici_id)
    if kisi is None or (kullanici_id != aktif_id() and not ortak and not engelledi):
        abort(404)
    rozetler = [r for r in rozetleri_hesapla(kullanici_id) if r["kazanildi"]] if kisi["rol"] == "ogrenci" else []
    return render_template("kullanici.html", kisi=kisi, kisi_id=kullanici_id, ortak=ortak, rozetler=rozetler,
                           kendisi=kullanici_id == aktif_id(), engelledi=engelledi,
                           engelleyebilir=(kullanici_id != aktif_id() and kisi["rol"] == "ogrenci"
                                           and g.kullanici["rol"] == "ogrenci"),
                           mesaj_atabilir=kullanici_id != aktif_id() and mesaj_atabilir_mi(aktif_id(), kullanici_id),
                           ogrencim=(g.kullanici["rol"] == "ogretmen"
                                     and veritabani.ogretmen_gorebilir_mi(aktif_id(), kullanici_id)))


@app.route("/profil/hakkimda", methods=["POST"])
@giris_gerekli
def hakkimda_kaydet():
    """POST: Profildeki "Hakkımda" yazısını kaydeder (boş bırakılırsa silinir)."""
    metin = request.form.get("hakkimda", "").strip()
    if len(metin) > EN_UZUN_HAKKIMDA:
        flash(f"Hakkımda yazısı en fazla {EN_UZUN_HAKKIMDA} karakter olabilir.", "hata")
    else:
        veritabani.hakkimda_kaydet(aktif_id(), kufur_suz(metin))
        flash("Profilin güncellendi.", "bilgi")
    return redirect(url_for("profil") + "#hakkimda")


# ---------------------------------------------------------------------------
# Programı başlat
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    adres = "http://127.0.0.1:5000"
    print("KodKoç çalışıyor. Tarayıcıda açılmazsa şu adrese git:", adres)
    print("Kapatmak için bu pencereyi kapat ya da Ctrl + C'ye bas.")
    threading.Timer(1.5, lambda: webbrowser.open(adres)).start()   # Tarayıcıyı otomatik aç
    app.run(host="127.0.0.1", port=5000, debug=False)
