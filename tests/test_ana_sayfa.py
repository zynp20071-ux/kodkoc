"""Ana sayfa testleri: 'Kaldığın yerden devam et' kartı ve proje fikri önerisi."""

import json
import urllib.parse

import pytest

import kodkoc
from conftest import yol_haritasi_cikar

# conftest'teki otomatik fixture her testte bu fonksiyonu sahtesiyle değiştiriyor.
# Gerçeğini, dosya yüklenirken (fixture çalışmadan önce) saklıyoruz ki aşağıda test edebilelim.
GERCEK_FIKIR_ISTE = kodkoc.proje_fikirleri_iste


# --- Kaldığın yerden devam et ---

def test_yol_haritasi_yoksa_kart_yok(kayit_ol):
    assert "Kaldığın yerden devam et" not in kayit_ol("ali").get("/").text


def test_kart_siradaki_adimi_gosterir(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali, "Yapılacaklar listesi")
    sayfa = ali.get("/").text
    assert "Kaldığın yerden devam et" in sayfa
    assert "Sıradaki: <strong>Adım 1: Menüyü Planlama</strong>" in sayfa
    assert f'href="/yol-haritasi/{harita_id}#adim-{adimlar[0]}"' in sayfa

    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    sayfa = ali.get("/").text
    assert "Adım 2: Görev Ekleme" in sayfa and "1 / 4 adım · %25" in sayfa


def test_bitmis_yol_haritasi_atlanir(kayit_ol):
    ali = kayit_ol("ali")
    yol_haritasi_cikar(ali, "Eski proje")
    _, yeni_adimlar = yol_haritasi_cikar(ali, "Yeni proje")
    assert "Yeni proje" in ali.get("/").text                    # En yenisi gösterilir

    for adim_id in yeni_adimlar:                                  # Yeniyi bitir
        ali.post(f"/adim/{adim_id}", data={"tamamlandi": "1"})
    sayfa = ali.get("/").text
    assert "Eski proje" in sayfa and "Yeni proje" not in sayfa   # Bitmemiş eskisine geçer


def test_hepsi_bitince_kart_kaybolur(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    for adim_id in adimlar:
        ali.post(f"/adim/{adim_id}", data={"tamamlandi": "1"})
    assert "Kaldığın yerden devam et" not in ali.get("/").text


def test_baskasinin_yol_haritasi_kartta_gorunmez(kayit_ol):
    yol_haritasi_cikar(kayit_ol("ayse"), "Ayşe'nin projesi")
    assert "Kaldığın yerden devam et" not in kayit_ol("ali").get("/").text


# --- Proje fikri ---

def test_proje_fikri_ve_secme(kayit_ol):
    ali = kayit_ol("ali")
    sayfa = ali.post("/fikir", data={"ilgi": "futbol", "bilgi": "Python temel"}).text
    assert sayfa.count("Bu fikri seç") == 3
    assert "futbol skorlarını kaydeden" in sayfa
    assert 'value="Python temel"' in sayfa                       # Bilgi kaybolmadı

    # "Bu fikri seç" bir GET formu: adres /?proje=...&bilgi=... olur, form dolar
    adres = "/?" + urllib.parse.urlencode({"proje": "Not Defteri: Not ekleyip silebileceğin bir program.",
                                           "bilgi": "Python temel"})
    sayfa = ali.get(adres).text
    assert ">Not Defteri: Not ekleyip silebileceğin bir program.</textarea>" in sayfa


def test_fikir_hatasi_anlasilir(kayit_ol, monkeypatch):
    def bozuk(*a):
        raise ValueError("bozuk json")
    monkeypatch.setattr(kodkoc, "proje_fikirleri_iste", bozuk)
    sayfa = kayit_ol("ali").post("/fikir", data={"ilgi": "x"}).text
    assert "bir kez daha dener misin" in sayfa


def test_cok_uzun_on_doldurma_kirpilir(kayit_ol):
    sayfa = kayit_ol("ali").get("/?proje=" + "a" * 5000).text
    assert "a" * 1000 in sayfa and "a" * 1001 not in sayfa


# --- proje_fikirleri_iste: yapay zekâ cevabını doğrulama ---

class SahteIstemci:
    """generate_content'e gelen ayarları saklayan, verilen metni döndüren sahte Gemini."""
    def __init__(self, metin):
        self.metin = metin
        self.ayar = None
        self.models = self

    def generate_content(self, **kwargs):
        self.ayar = kwargs["config"]
        metin = self.metin

        class Cevap:
            text = metin
        return Cevap()


def test_fikirler_json_olarak_isteniyor_ve_kirpiliyor():
    veri = [{"baslik": "  A  ", "aciklama": "x" * 1000}, {"baslik": "B", "aciklama": "b"},
            {"baslik": "C", "aciklama": "c"}, {"baslik": "D", "aciklama": "d"}]
    istemci = SahteIstemci(json.dumps(veri))
    fikirler = GERCEK_FIKIR_ISTE(istemci, "", "")
    assert istemci.ayar.response_mime_type == "application/json"
    assert len(fikirler) == 3                                     # En fazla 3
    assert fikirler[0]["baslik"] == "A" and len(fikirler[0]["aciklama"]) == 400


@pytest.mark.parametrize("bozuk_cevap", [
    "bu json değil",
    '{"baslik": "liste değil"}',
    '[{"baslik": 5}]',
    "[]",
])
def test_bozuk_fikir_cevabi_valueerror(bozuk_cevap):
    with pytest.raises(ValueError):
        GERCEK_FIKIR_ISTE(SahteIstemci(bozuk_cevap), "", "")
