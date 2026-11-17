"""
Notlarım sayfası ve yeni rozetler (Tam Zamanında, Soru Soran, İstikrarlı) testleri.
"""

import re
from datetime import date, timedelta

import app as uygulama
import veritabani
from conftest import yol_haritasi_cikar


def kazanilanlar(k):
    return {r["anahtar"] for r in uygulama.rozetleri_hesapla(k.kullanici["id"]) if r["kazanildi"]}


def gun(fark):
    return (date.today() + timedelta(days=fark)).isoformat()


# ---------------------------------------------------------------------------
# Yeni rozetler
# ---------------------------------------------------------------------------

def test_tam_zamaninda(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/hedef", data={"tarih": gun(2)})
    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    assert "zamaninda" not in kazanilanlar(ali)                  # 1 / 2

    veritabani.hedef_tarih_ayarla(adimlar[1], gun(-1))           # Hedefi dün geçmiş
    ali.post(f"/adim/{adimlar[1]}", data={"tamamlandi": "1"})
    assert "zamaninda" not in kazanilanlar(ali)                  # Geç biten sayılmaz

    ali.post(f"/adim/{adimlar[2]}/hedef", data={"tarih": gun(0)})   # Hedefi bugün: zamanında
    ali.post(f"/adim/{adimlar[2]}", data={"tamamlandi": "1"})
    assert "zamaninda" in kazanilanlar(ali)
    assert "Yeni rozet kazandın: ★ Tam Zamanında" in ali.get("/").text


def test_istikrarli(kayit_ol, monkeypatch):
    ali = kayit_ol("ali")
    gunler = {gun(-i): 1 for i in range(1, 7)}                   # Dünden geriye 6 gün
    monkeypatch.setattr(veritabani, "calisma_gunleri", lambda k: gunler)
    assert "istikrarli" not in kazanilanlar(ali)
    gunler[gun(-7)] = 1                                          # 7. gün
    assert "istikrarli" in kazanilanlar(ali)
    gunler.pop(gun(-4))                                          # Arada boşluk: en uzun seri 3
    assert "istikrarli" not in kazanilanlar(ali)


def test_soru_soran(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    _, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/ogretmene-sor", data={"soru": "Döngü neden bitmiyor?"})
    assert "soru_soran" in kazanilanlar(ali)
    assert "★ Soru Soran" in ali.get("/").text


def test_rozet_bildirimi_bir_kez(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    assert "Yeni rozet kazandın: ★ İlk Adım" in ali.get("/").text
    ali.post(f"/adim/{adimlar[1]}", data={"tamamlandi": "1"})     # Zaten kazanılmış: tekrar kutlanmaz
    assert "Yeni rozet" not in ali.get("/").text
    ali.post(f"/adim/{adimlar[1]}", data={"tamamlandi": "0"})     # Geri almak bildirim vermez
    assert "Yeni rozet" not in ali.get("/").text


def test_not_defteri_bildirimi(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    for adim_id in adimlar[:3]:
        ali.post(f"/adim/{adim_id}/not", data={"not_metni": "öğrendim"})
    assert "★ Not Defteri" in ali.get("/").text


# ---------------------------------------------------------------------------
# Notlarım
# ---------------------------------------------------------------------------

def test_notlarim_bos(kayit_ol):
    ali = kayit_ol("ali")
    sayfa = ali.get("/notlarim").text
    assert "Henüz not yazmadın" in sayfa
    assert "/notlarim" in ali.get("/gecmis").text


def test_notlarim_listesi_ve_arama(kayit_ol):
    ali = kayit_ol("ali")
    h1, a1 = yol_haritasi_cikar(ali, "Hesap makinesi")
    h2, a2 = yol_haritasi_cikar(ali, "Yapılacaklar listesi")
    ali.post(f"/adim/{a1[0]}/not", data={"not_metni": "while döngüsü\nçıkış koşulunu unutma"})
    ali.post(f"/adim/{a2[1]}/not", data={"not_metni": "append listeye ekler"})
    ali.post(f"/adim/{a2[2]}/not", data={"not_metni": ""})          # Boş not kaydedilmez

    sayfa = ali.get("/notlarim").text
    assert "2 not" in sayfa
    assert sayfa.index("Yapılacaklar listesi") < sayfa.index("Hesap makinesi")   # En yeni önce
    assert f"/yol-haritasi/{h1}#adim-{a1[0]}" in sayfa and "çıkış koşulunu unutma" in sayfa

    bulunan = ali.get("/notlarim?ara=APPEND").text                   # Büyük/küçük harf fark etmez
    assert "append listeye ekler" in bulunan and "while döngüsü" not in bulunan and "1 not" in bulunan
    assert "bulunamadı" in ali.get("/notlarim?ara=yokboyle").text
    assert "while döngüsü" in ali.get("/notlarim?ara=hesap").text      # Proje adında da arar


def test_notlar_baskasina_gorunmez(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/not", data={"not_metni": "gizli notum"})
    ayse = kayit_ol("ayse")
    assert "gizli notum" not in ayse.get("/notlarim").text
    assert "gizli notum" not in ayse.get("/notlarim/indir").text
    assert ayse.post(f"/adim/{adimlar[0]}/not", data={"not_metni": "x"}).status_code == 404


def test_notlari_indir(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali, "Hesap makinesi")
    ali.post(f"/adim/{adimlar[1]}/not", data={"not_metni": "liste metotları"})
    cevap = ali.get("/notlarim/indir")
    assert cevap.status_code == 200 and cevap.mimetype == "text/markdown"
    assert "attachment" in cevap.headers["Content-Disposition"]
    metin = cevap.get_data(as_text=True)
    assert metin.startswith("# KodKoç notlarım")
    assert "## Hesap makinesi" in metin and "### Adım 2: Görev Ekleme" in metin and "liste metotları" in metin


def test_notlarim_giris_ister(istemci):
    assert istemci.get("/notlarim").status_code == 302
    assert istemci.get("/notlarim/indir").status_code == 302
