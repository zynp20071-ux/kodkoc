"""Rozet testleri: hangi davranış hangi rozeti kazandırıyor?"""

import re

import app as uygulama
import veritabani
from conftest import yol_haritasi_cikar


def kazanilanlar(k):
    return {r["anahtar"] for r in uygulama.rozetleri_hesapla(k.kullanici["id"]) if r["kazanildi"]}


def test_baslangicta_rozet_yok(kayit_ol):
    ali = kayit_ol("ali")
    assert kazanilanlar(ali) == set()
    sayfa = ali.get("/gecmis").text
    assert "Rozetler" in sayfa and "(0 / 11)" in sayfa and "0 / 3" in sayfa     # İlerleme yazıyor


def test_ilk_adim_ve_kendi_basina(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    assert kazanilanlar(ali) == {"ilk_adim"}

    ali.post(f"/adim/{adimlar[1]}/ipucu", data={})              # İpuçlu adım sayılmaz
    for adim_id in adimlar[1:3]:
        ali.post(f"/adim/{adim_id}", data={"tamamlandi": "1"})
    assert "kendi_basina" not in kazanilanlar(ali)               # 2 ipucusuz + 1 ipuçlu
    ali.post(f"/adim/{adimlar[3]}", data={"tamamlandi": "1"})
    assert {"kendi_basina", "bitis"} <= kazanilanlar(ali)       # 3 ipucusuz, harita bitti


def test_pes_etmeyen(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    for _ in range(3):
        ali.post(f"/adim/{adimlar[0]}/ipucu", data={})
    assert "pes_etmeyen" not in kazanilanlar(ali)               # Henüz bitmedi
    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    assert "pes_etmeyen" in kazanilanlar(ali)


def test_not_inceleme_commit(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    for adim_id in adimlar[:3]:
        ali.post(f"/adim/{adim_id}/not", data={"not_metni": "öğrendim"})
    ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": "print(1)"})
    veritabani.commitleri_kaydet(harita_id, [{"sha": "a", "mesaj": "ilk", "yazar": "ali",
                                              "tarih": "2026-11-10 10:00:00", "url": "https://github.com/a/b/commit/a"}],
                                 lambda m: None)
    assert kazanilanlar(ali) == {"not_defteri", "kod_okuyucu", "ilk_commit"}


def test_rozetler_baskasini_saymaz(kayit_ol):
    ayse = kayit_ol("ayse")
    _, adimlar = yol_haritasi_cikar(ayse)
    ayse.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    assert kazanilanlar(kayit_ol("ali")) == set()


def test_ogretmen_ogrencinin_rozetlerini_gorur(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    _, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    sayfa = hoca.get(f"/ogretmen/ogrenci/{ali.kullanici['id']}").text
    assert "(1 / 11)" in sayfa and 'class="rozet kazanildi"' in sayfa
