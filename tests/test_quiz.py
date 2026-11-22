"""Mini quiz testleri: hazırlama, cevaplama, gizli doğru cevaplar, sınırlar, öğretmen görünümü."""

import re

import pytest

import app as uygulama
import kodkoc
from conftest import yol_haritasi_cikar


def test_quiz_akisi(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    adim = adimlar[1]
    assert "Kendini sına: mini quiz" in ali.get(f"/yol-haritasi/{harita_id}").text

    ali.post(f"/adim/{adim}/quiz")
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert "append ne yapar?" in sayfa and 'name="s0"' in sayfa
    assert "append listenin sonuna" not in sayfa                     # Açıklama/doğru cevap henüz yok
    assert "Cevaplarımı kontrol et" in sayfa

    cevap = ali.post(f"/adim/{adim}/quiz/cevap", data={"s0": "1", "s1": "0", "s2": "0"}, follow_redirects=True)
    assert "3 sorudan 2 tanesini bildin" in cevap.text
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert "2 / 3 doğru" in sayfa and "append listenin sonuna" in sayfa and "(senin cevabın)" in sayfa


def test_cevap_degistirilemez_ve_eksik_cevap(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/quiz")
    cevap = ali.post(f"/adim/{adimlar[0]}/quiz/cevap", data={"s0": "1"}, follow_redirects=True)
    assert "Bütün soruları cevapla" in cevap.text
    ali.post(f"/adim/{adimlar[0]}/quiz/cevap", data={"s0": "0", "s1": "0", "s2": "1"})     # 0 doğru
    ali.post(f"/adim/{adimlar[0]}/quiz/cevap", data={"s0": "1", "s1": "2", "s2": "0"})     # Tekrar: sayılmaz
    assert "0 / 3 doğru" in ali.get(f"/yol-haritasi/{harita_id}").text


def test_yeni_sorular_ve_sinir(kayit_ol, sahte_yapay_zeka):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    for _ in range(uygulama.EN_FAZLA_QUIZ + 1):
        ali.post(f"/adim/{adimlar[0]}/quiz")
    assert len(sahte_yapay_zeka["quiz"]) == uygulama.EN_FAZLA_QUIZ
    ali.post(f"/adim/{adimlar[0]}/quiz/cevap", data={"s0": "1", "s1": "2", "s2": "0"})
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert "3 / 3 doğru" in sayfa and "Yeni sorularla tekrar dene" not in sayfa


def test_baskasi_ve_yetkisiz(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    ayse = kayit_ol("ayse")
    assert ayse.post(f"/adim/{adimlar[0]}/quiz").status_code == 404
    ali.post(f"/adim/{adimlar[0]}/quiz")
    assert ayse.post(f"/adim/{adimlar[0]}/quiz/cevap", data={"s0": "1"}).status_code == 404
    assert ali.post(f"/adim/{adimlar[1]}/quiz/cevap", data={"s0": "1"}).status_code == 404   # Quiz yok


def test_ogretmen_sonucu_gorur(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    harita_id, adimlar = yol_haritasi_cikar(ali)
    adres = f"/ogretmen/ogrenci/{ali.kullanici['id']}/yol-haritasi/{harita_id}"
    ali.post(f"/adim/{adimlar[0]}/quiz")
    sayfa = hoca.get(adres).text
    assert "öğrenci henüz cevaplamadı" in sayfa and 'name="s0"' not in sayfa
    ali.post(f"/adim/{adimlar[0]}/quiz/cevap", data={"s0": "1", "s1": "2", "s2": "3"})
    sayfa = hoca.get(adres).text
    assert "2 / 3 doğru" in sayfa and "(öğrencinin cevabı)" in sayfa and "Yeni sorularla" not in sayfa


def test_adim_ve_harita_silinince_quiz_gider(kayit_ol):
    import veritabani
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/quiz")
    ali.post(f"/adim/{adimlar[1]}/quiz")
    ali.post(f"/adim/{adimlar[0]}/sil")
    assert veritabani.quiz_getir(adimlar[0]) is None and veritabani.quiz_getir(adimlar[1]) is not None
    ali.post(f"/yol-haritasi/{harita_id}/sil")
    assert veritabani.quiz_getir(adimlar[1]) is None


# --- Yapay zekâdan gelen verinin kontrolü (kodkoc.quiz_kontrol) ---

IYI = {"soru": "S?", "secenekler": ["a", "b", "c", "d"], "dogru": 2, "aciklama": "çünkü"}


def test_quiz_kontrol_iyi():
    sonuc = kodkoc.quiz_kontrol([IYI, IYI, IYI, IYI])
    assert len(sonuc) == 3 and sonuc[0]["dogru"] == 2


@pytest.mark.parametrize("bozuk", [
    {"soru": "S?"},                                              # Liste değil
    [IYI],                                                       # Tek soru yetmez
    [IYI, {**IYI, "dogru": 4}],                                  # Geçersiz doğru cevap
    [IYI, {**IYI, "dogru": True}],                               # bool, int sayılmasın
    [IYI, {**IYI, "secenekler": ["a", "b", "c"]}],               # 3 seçenek
    [IYI, {**IYI, "secenekler": ["a", "", "c", "d"]}],           # Boş seçenek
])
def test_quiz_kontrol_bozuk(bozuk):
    with pytest.raises(ValueError):
        kodkoc.quiz_kontrol(bozuk)
