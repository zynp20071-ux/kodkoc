"""
Canlıya geçiş testleri: KodKoç tek bir sunucuda herkesin ortak kullandığı
bir site olunca ortaya çıkan güvenlik sorunlarının kapatıldığını kontrol eder.

monkeypatch.setattr(uygulama, "CANLI", True): Test süresince canlı modu açar,
test bitince eski haline (yerel) döner.
"""

import pytest

import app as uygulama
import kodkoc
import veritabani
from conftest import yol_haritasi_cikar


@pytest.fixture
def canli(monkeypatch):
    """Canlı modu açar (öğretmen davet kodu tanımlı değil)."""
    monkeypatch.setattr(uygulama, "CANLI", True)
    monkeypatch.setattr(uygulama, "OGRETMEN_KODU", "")


# ---------------------------------------------------------------------------
# Gemini anahtarı
# ---------------------------------------------------------------------------

def test_canlida_anahtar_siteden_degistirilemez(canli, kayit_ol, monkeypatch):
    yazilanlar = []
    monkeypatch.setattr(uygulama, "set_key", lambda *a: yazilanlar.append(a))
    ali = kayit_ol("ali")
    assert ali.post("/anahtar", data={"anahtar": "saldirganin-anahtari"}).status_code == 404
    assert yazilanlar == []              # .env dosyasına hiçbir şey yazılmadı


def test_yerelde_anahtar_kaydedilebilir(kayit_ol, monkeypatch):
    yazilanlar = []
    monkeypatch.setattr(uygulama, "set_key", lambda *a: yazilanlar.append(a))
    ali = kayit_ol("ali")
    assert ali.post("/anahtar", data={"anahtar": "AIza-benim"}).status_code == 302
    assert yazilanlar[0][1:] == ("GEMINI_API_KEY", "AIza-benim")


def test_canlida_anahtar_yoksa_form_yerine_uyari_cikar(canli, kayit_ol, monkeypatch):
    monkeypatch.setattr(uygulama, "api_anahtari", lambda: None)
    sayfa = kayit_ol("ali").get("/").text
    assert "öğretmenine haber ver" in sayfa
    assert 'name="anahtar"' not in sayfa


def test_canlida_gizli_anahtar_ayarlanmamissa_program_baslamaz(monkeypatch):
    monkeypatch.setattr(uygulama, "CANLI", True)
    monkeypatch.delenv("FLASK_SECRET_KEY")
    with pytest.raises(RuntimeError):
        uygulama.gizli_anahtari_hazirla()


def test_canlida_hata_ayrintisi_gosterilmez(canli, kayit_ol, monkeypatch):
    def bozuk(istemci, proje, bilgi):
        raise Exception("gizli-sunucu-ayrintisi")
    monkeypatch.setattr(kodkoc, "yol_haritasi_iste", bozuk)
    sayfa = kayit_ol("ali").post("/yol-haritasi", data={"proje": "Hesap makinesi"}).text
    assert "gizli-sunucu-ayrintisi" not in sayfa
    assert "bağlanılamadı" in sayfa


@pytest.mark.parametrize("kod, beklenen", [(403, "ayarında bir sorun var (hata kodu 403)"),
                                           (400, "hata kodu 400"), (404, "bağlanılamadı")])
def test_canlida_anahtar_hatasi_kodu_gosterilir(canli, kayit_ol, monkeypatch, kod, beklenen):
    class SahteHata(Exception):
        pass

    def bozuk(istemci, proje, bilgi):
        hata = SahteHata("API key not valid: gizli-ayrinti")
        hata.code = kod
        raise hata
    monkeypatch.setattr(kodkoc, "yol_haritasi_iste", bozuk)
    sayfa = kayit_ol("ali").post("/yol-haritasi", data={"proje": "Hesap makinesi"}).text
    assert beklenen in sayfa and "gizli-ayrinti" not in sayfa


def test_canlida_md_dosyasi_yazilmaz(canli, kayit_ol, monkeypatch):
    yazilanlar = []
    monkeypatch.setattr(kodkoc, "kaydet", lambda proje, cevap: yazilanlar.append(proje))
    yol_haritasi_cikar(kayit_ol("ali"))
    assert yazilanlar == []


def test_canlida_cerez_sadece_https(monkeypatch):
    # Ayar program açılırken okunuyor; yerelde (testlerde) kapalı olmalı ki http'de giriş çalışsın
    assert uygulama.app.config["SESSION_COOKIE_SECURE"] is False


def test_guvenlik_basliklari_her_cevapta_var(istemci):
    cevap = istemci.get("/giris")
    assert cevap.headers["X-Content-Type-Options"] == "nosniff"
    csp = cevap.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in csp and "form-action 'self'" in csp
    assert "Strict-Transport-Security" not in cevap.headers      # Yerelde (http) HSTS olmamalı


def test_beklenmedik_hatada_ayrinti_gosterilmez(kayit_ol, monkeypatch):
    ali = kayit_ol("ali")

    def bozuk(*args, **kwargs):
        raise RuntimeError("veritabani-sifresi-burada")
    monkeypatch.setattr(veritabani, "devam_edilecek_adim", bozuk)
    monkeypatch.setitem(uygulama.app.config, "PROPAGATE_EXCEPTIONS", False)   # Testte hatayı fırlatma, sayfayı göster
    cevap = ali.get("/")
    assert cevap.status_code == 500
    assert "Bir aksilik oldu" in cevap.text and "veritabani-sifresi-burada" not in cevap.text


def test_saglik_kontrolu_giris_istemez(istemci):
    cevap = istemci.get("/saglik")
    assert cevap.status_code == 200 and cevap.text == "tamam"


def test_saglik_kontrolu_calisan_surumu_soyler(istemci, monkeypatch):
    assert istemci.get("/saglik").headers["X-KodKoc-Surum"] == "yerel"
    monkeypatch.setenv("RENDER_GIT_COMMIT", "f7ed997b75f45646dee6b362fdec8d91ee070e23")
    assert istemci.get("/saglik").headers["X-KodKoc-Surum"] == "f7ed997"


def test_saglik_kontrolu_veritabani_yoksa_503_ve_log(istemci, monkeypatch, caplog):
    def bozuk():
        raise RuntimeError("baglanamadi")
    monkeypatch.setattr(veritabani, "kullanici_sayisi", bozuk)
    monkeypatch.setattr(veritabani, "baglanti_teshisi", lambda: "OperationalError: password authentication failed")
    cevap = istemci.get("/saglik")
    assert cevap.status_code == 503 and "password" not in cevap.text      # Ayrıntı ziyaretçiye gitmez
    assert "password authentication failed" in caplog.text                 # Ama loglarda var


# ---------------------------------------------------------------------------
# Öğretmen kaydı
# ---------------------------------------------------------------------------

def ogretmen_kaydi(istemci, kod=None):
    veri = {"kullanici_adi": "hoca", "sifre": "sifre123", "sifre_tekrar": "sifre123", "rol": "ogretmen"}
    if kod is not None:
        veri["ogretmen_kodu"] = kod
    return istemci.post("/kayit", data=veri)


def test_canlida_kod_yoksa_ogretmen_kaydi_kapali(canli, istemci):
    assert 'value="ogretmen"' not in istemci.get("/kayit").text      # Seçenek hiç görünmüyor
    cevap = ogretmen_kaydi(istemci)                                   # Form elle gönderilse bile
    assert cevap.status_code == 200 and "kapalı" in cevap.text
    assert veritabani.kullanici_dogrula("hoca", "sifre123") is None


def test_yanlis_davet_koduyla_ogretmen_olunamaz(istemci, monkeypatch):
    monkeypatch.setattr(uygulama, "OGRETMEN_KODU", "gizli-kod-42")
    assert 'name="ogretmen_kodu"' in istemci.get("/kayit").text
    cevap = ogretmen_kaydi(istemci, "tahmin")
    assert "davet kodu yanlış" in cevap.text
    assert veritabani.kullanici_dogrula("hoca", "sifre123") is None


def test_dogru_davet_koduyla_ogretmen_olunur(istemci, monkeypatch):
    monkeypatch.setattr(uygulama, "OGRETMEN_KODU", "gizli-kod-42")
    assert ogretmen_kaydi(istemci, "gizli-kod-42").status_code == 302
    assert veritabani.kullanici_dogrula("hoca", "sifre123")["rol"] == "ogretmen"


def test_ogrenci_kaydi_davet_kodu_istemez(kayit_ol, monkeypatch):
    monkeypatch.setattr(uygulama, "CANLI", True)
    monkeypatch.setattr(uygulama, "OGRETMEN_KODU", "gizli-kod-42")
    ali = kayit_ol("ali")                                     # kayit_ol 302 bekliyor
    assert ali.kullanici["rol"] == "ogrenci"


# ---------------------------------------------------------------------------
# Günlük yapay zekâ sınırı
# ---------------------------------------------------------------------------

def test_gunluk_sinir_dolunca_yapay_zekaya_gidilmez(kayit_ol, sahte_yapay_zeka, monkeypatch):
    monkeypatch.setattr(uygulama, "GUNLUK_YZ_SINIRI", 2)
    ali = kayit_ol("ali")
    yol_haritasi_cikar(ali, "Birinci")
    _, adimlar = yol_haritasi_cikar(ali, "İkinci")

    cevap = ali.post("/yol-haritasi", data={"proje": "Üçüncü"})
    assert "yapay zekâ hakkını" in cevap.text
    ali.post(f"/adim/{adimlar[0]}/ipucu", data={"soru": ""})
    ali.post(f"/adim/{adimlar[0]}/soru", data={"soru": "Liste nedir?"})
    ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": "print(1)"})
    ali.post("/fikir", data={"ilgi": "futbol"})

    assert sahte_yapay_zeka["yol_haritasi"] == ["Birinci", "İkinci"]
    assert sahte_yapay_zeka["ipucu"] == [] and sahte_yapay_zeka["soru"] == []
    assert sahte_yapay_zeka["inceleme"] == []


def test_sinir_kullanici_basinadir(kayit_ol, sahte_yapay_zeka, monkeypatch):
    monkeypatch.setattr(uygulama, "GUNLUK_YZ_SINIRI", 1)
    yol_haritasi_cikar(kayit_ol("ali"), "Ali'nin projesi")
    yol_haritasi_cikar(kayit_ol("ayse"), "Ayşe'nin projesi")   # Ali'nin hakkı bitti diye Ayşe etkilenmez
    assert sahte_yapay_zeka["yol_haritasi"] == ["Ali'nin projesi", "Ayşe'nin projesi"]


def test_site_geneli_sinir_dolunca_yeni_hesap_da_kullanamaz(kayit_ol, sahte_yapay_zeka, monkeypatch):
    # Biri çok hesap açarak kişi başı sınırı aşmaya çalışsa bile ortak sınır durdurur
    monkeypatch.setattr(uygulama, "GUNLUK_TOPLAM_YZ_SINIRI", 2)
    yol_haritasi_cikar(kayit_ol("ali"), "Birinci")
    yol_haritasi_cikar(kayit_ol("ayse"), "İkinci")
    cevap = kayit_ol("yeni_hesap").post("/yol-haritasi", data={"proje": "Üçüncü"})
    assert "günlük yapay zekâ sınırına ulaştı" in cevap.text
    assert sahte_yapay_zeka["yol_haritasi"] == ["Birinci", "İkinci"]


def test_site_geneli_sinir_sifirsa_sinir_yok(kayit_ol, sahte_yapay_zeka, monkeypatch):
    monkeypatch.setattr(uygulama, "GUNLUK_TOPLAM_YZ_SINIRI", 0)
    for i in range(3):
        yol_haritasi_cikar(kayit_ol(f"ogrenci{i}"), f"Proje {i}")
    assert len(sahte_yapay_zeka["yol_haritasi"]) == 3


def test_basarisiz_istek_haktan_dusmez(kayit_ol, monkeypatch):
    def bozuk(istemci, proje, bilgi):
        raise Exception("bağlantı koptu")
    monkeypatch.setattr(kodkoc, "yol_haritasi_iste", bozuk)
    ali = kayit_ol("ali")
    ali.post("/yol-haritasi", data={"proje": "Hesap makinesi"})
    assert veritabani.bugunku_yz_kullanimi(ali.kullanici["id"]) == 0


# ---------------------------------------------------------------------------
# Şifre deneme sınırı
# ---------------------------------------------------------------------------

def giris_yap(istemci, sifre):
    return istemci.post("/giris", data={"kullanici_adi": "ali", "sifre": sifre})


def test_cok_yanlis_denemeden_sonra_dogru_sifre_de_reddedilir(kayit_ol, istemci):
    kayit_ol("ali")
    for _ in range(uygulama.EN_FAZLA_YANLIS_GIRIS):
        assert "yanlış" in giris_yap(istemci, "tahmin").text
    cevap = giris_yap(istemci, "sifre123")
    assert cevap.status_code == 429 and "Çok fazla yanlış deneme" in cevap.text


def test_dogru_giris_yanlis_denemeleri_sifirlar(kayit_ol, istemci):
    kayit_ol("ali")
    for _ in range(uygulama.EN_FAZLA_YANLIS_GIRIS - 1):
        giris_yap(istemci, "tahmin")
    assert giris_yap(istemci, "sifre123").status_code == 302
    assert veritabani.son_yanlis_giris_sayisi("ali", uygulama.DENEME_SURESI) == 0


def test_eski_yanlis_denemeler_sayilmaz(kayit_ol):
    kayit_ol("ali")
    b = veritabani.baglan()
    b.executemany("INSERT INTO giris_denemeleri VALUES ('ali', '2026-01-01 10:00:00')", [()] * 10)
    b.commit()
    b.close()
    assert veritabani.son_yanlis_giris_sayisi("ali", uygulama.DENEME_SURESI) == 0
