"""'Koça soru sor' testleri: soru-cevap kaydı, sınırlar, güvenlik ve yapay zekâya giden mesaj."""

import re

import app as uygulama
import kodkoc
import veritabani
from conftest import adim_bolumu, yol_haritasi_cikar

# Gerçek fonksiyonu, conftest'teki sahte_yapay_zeka onu değiştirmeden ÖNCE sakla
# (bu satır test dosyası içe aktarılırken, yani fixture'lardan önce çalışır)
GERCEK_SORU_SOR = kodkoc.soru_sor


def test_soru_sorulur_ve_cevap_gorunur(kayit_ol, sahte_yapay_zeka):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    cevap = ali.post(f"/adim/{adimlar[1]}/soru", data={"soru": "Liste nedir?"})
    assert cevap.status_code == 302 and cevap.headers["Location"].endswith(f"#adim-{adimlar[1]}")

    bolum = adim_bolumu(ali.get(f"/yol-haritasi/{harita_id}").text, adimlar[1])
    assert "Liste nedir?" in bolum
    assert "<strong>Liste</strong>" in bolum                 # Markdown HTML'e çevrildi
    assert "Koça sorular (1)" in bolum and "Kalan hak: 9 / 10" in bolum
    assert sahte_yapay_zeka["soru"][0]["baslik"] == "Adım 2: Görev Ekleme"


def test_bos_ve_uzun_soru_reddedilir(kayit_ol, sahte_yapay_zeka):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/soru", data={"soru": "   "})
    ali.post(f"/adim/{adimlar[0]}/soru", data={"soru": "a" * (uygulama.EN_UZUN_SORU + 1)})
    assert sahte_yapay_zeka["soru"] == []                     # Yapay zekâya hiç gidilmedi
    assert veritabani.adimin_sorulari(adimlar[0]) == []


def test_soru_hakki_sinirli(kayit_ol, sahte_yapay_zeka):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    for i in range(uygulama.EN_FAZLA_SORU + 2):
        ali.post(f"/adim/{adimlar[0]}/soru", data={"soru": f"Soru {i}"})
    assert len(sahte_yapay_zeka["soru"]) == uygulama.EN_FAZLA_SORU
    bolum = adim_bolumu(ali.get(f"/yol-haritasi/{harita_id}").text, adimlar[0])
    assert "bütün soru haklarını kullandın" in bolum
    assert f'/adim/{adimlar[0]}/soru"' not in bolum           # Form artık yok


def test_son_uc_soru_hafiza_olarak_gider(kayit_ol, sahte_yapay_zeka):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    for i in range(5):
        ali.post(f"/adim/{adimlar[0]}/soru", data={"soru": f"Soru {i}"})
    son = sahte_yapay_zeka["soru"][-1]
    assert [s for s, _ in son["konusma"]] == ["Soru 1", "Soru 2", "Soru 3"]
    # Sorular her adımın kendi konuşması: başka adımda hafıza boş başlar
    ali.post(f"/adim/{adimlar[1]}/soru", data={"soru": "Yeni adım"})
    assert sahte_yapay_zeka["soru"][-1]["konusma"] == []


def test_baskasinin_adimina_soru_sorulamaz(kayit_ol, sahte_yapay_zeka):
    ayse = kayit_ol("ayse")
    _, adimlar = yol_haritasi_cikar(ayse)
    ali = kayit_ol("ali")
    assert ali.post(f"/adim/{adimlar[0]}/soru", data={"soru": "Merhaba"}).status_code == 404
    assert sahte_yapay_zeka["soru"] == []


def test_soru_html_olarak_calismaz(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/soru", data={"soru": "<script>alert(1)</script>"})
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert "<script>alert(1)</script>" not in sayfa
    assert "&lt;script&gt;" in sayfa


def test_adim_ve_harita_silinince_sorular_da_silinir(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/soru", data={"soru": "S1"})
    ali.post(f"/adim/{adimlar[1]}/soru", data={"soru": "S2"})

    ali.post(f"/adim/{adimlar[0]}/sil")                       # Yabancı anahtar hatası vermemeli
    assert veritabani.adimin_sorulari(adimlar[0]) == []
    assert len(veritabani.adimin_sorulari(adimlar[1])) == 1

    assert ali.post(f"/yol-haritasi/{harita_id}/sil").status_code == 302
    assert veritabani.adimin_sorulari(adimlar[1]) == []


def test_ogretmen_sorulari_gorur_ama_soramaz(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/soru", data={"soru": "Döngü nedir?"})

    sayfa = hoca.get(f"/ogretmen/ogrenci/{ali.kullanici['id']}/yol-haritasi/{harita_id}").text
    bolum = adim_bolumu(sayfa, adimlar[0])
    assert "Döngü nedir?" in bolum and "Öğrenci" in bolum
    assert "/soru" not in bolum                               # Soru formu öğretmene gösterilmez
    # Öğretmen, öğrencinin adımına kendisi soru gönderemez (adım ona ait değil)
    assert hoca.post(f"/adim/{adimlar[0]}/soru", data={"soru": "x"}).status_code == 404


def test_merakli_rozeti(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    for i in range(3):
        ali.post(f"/adim/{adimlar[i]}/soru", data={"soru": f"Soru {i}"})
    kazanilan = {r["anahtar"] for r in uygulama.rozetleri_hesapla(ali.kullanici["id"]) if r["kazanildi"]}
    assert "merakli" in kazanilan


def test_gercek_soru_sor_mesaji(monkeypatch):
    """kodkoc.soru_sor yapay zekâya doğru talimatı ve önceki konuşmayı gönderiyor mu?"""
    giden = {}

    def sahte_sor(istemci, mesaj, talimat, sicaklik=0.4, **kw):
        giden.update(mesaj=mesaj, talimat=talimat)
        return "cevap"

    monkeypatch.setattr(kodkoc, "yapay_zekaya_sor", sahte_sor)
    sonuc = GERCEK_SORU_SOR(None, "Not defteri", "Adım 1: Menü", "while döngüsü",
                            [("Döngü ne?", "Tekrar eden iş.")], "Sonsuz döngü kötü mü?")
    assert sonuc == "cevap"
    assert giden["talimat"] is kodkoc.SORU_TALIMATI and "ASLA hazır kod" in giden["talimat"]
    assert "Öğrenci: Döngü ne?\nKodKoç: Tekrar eden iş." in giden["mesaj"]
    assert "Sonsuz döngü kötü mü?" in giden["mesaj"] and "Adım 1: Menü" in giden["mesaj"]

    GERCEK_SORU_SOR(None, "p", "b", "i", [], "ilk soru")
    assert "Yok, bu ilk soru." in giden["mesaj"]
