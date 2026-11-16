"""Öğretmenin sınıf istatistikleri: sayı kutuları, ilerleme dağılımı ve 14 günlük grafik."""

import re
from datetime import date

import veritabani
from app import sinif_istatistigi
from conftest import yol_haritasi_cikar

BUGUN = date(2026, 11, 10)        # Salı. Sabit gün: test hangi gün çalışırsa çalışsın aynı sonuç


def ogrenci(toplam, yuzde):
    """sinif_detay'daki öğrenci sözlüğünün sadece gereken kısmı."""
    return {"toplam": toplam, "yuzde": yuzde}


# --- Hesaplama fonksiyonu (veritabanı yok, sadece Python) ----------------------

def test_bos_sinif():
    s = sinif_istatistigi([], set(), BUGUN)
    assert s["ortalama"] == 0 and s["aktif_hafta"] == 0 and s["baslamayan"] == 0
    assert [g["sayi"] for g in s["dagilim"]] == [0, 0, 0, 0]
    assert len(s["gunler"]) == 14 and all(g["oran"] == 0 for g in s["gunler"])   # Sıfıra bölme yok


def test_ortalama_ve_dagilim():
    ogrenciler = [ogrenci(4, 0), ogrenci(4, 25), ogrenci(4, 50), ogrenci(4, 100), ogrenci(0, 0)]
    s = sinif_istatistigi(ogrenciler, set(), BUGUN)
    assert s["ortalama"] == 44                    # (0+25+50+100)/4 = 43.75 -> 44; başlamayan sayılmaz
    assert s["baslamayan"] == 1
    assert [g["sayi"] for g in s["dagilim"]] == [2, 1, 0, 1]   # 0 ve 25 ilk grupta, sınırlar dahil
    assert s["dagilim"][0]["oran"] == 40          # 5 kişilik sınıfta 2 kişi = %40 çubuk


def test_gunluk_grafik_farkli_ogrenci_sayar():
    etkinlikler = {(1, "2026-11-10"), (2, "2026-11-10"), (1, "2026-11-09"),
                   (3, "2026-11-01"),               # 9 gün önce: grafikte var, "son 7 gün"de yok
                   (4, "2026-10-01")}               # Çok eski: hiçbir yerde sayılmaz
    s = sinif_istatistigi([ogrenci(1, 0)] * 4, etkinlikler, BUGUN)
    gunler = s["gunler"]
    assert gunler[-1]["tarih"] == "10.11" and gunler[-1]["bugun"] and gunler[-1]["etiket"] == "Sal"
    assert gunler[0]["tarih"] == "28.10"            # 14 gün: en eski solda
    assert gunler[-1]["sayi"] == 2 and gunler[-1]["oran"] == 100     # En yüksek gün tam boy
    assert gunler[-2]["sayi"] == 1 and gunler[-2]["oran"] == 50
    assert sum(g["sayi"] for g in gunler) == 4
    assert s["aktif_hafta"] == 2                    # Öğrenci 1 iki gün çalıştı ama bir kez sayılır


# --- Sayfa ve veritabanı -------------------------------------------------------

def sinif_ac(hoca):
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "9-A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    return sinif_id, kod


def test_sinif_sayfasinda_istatistikler(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id, kod = sinif_ac(hoca)
    assert "Sınıf istatistikleri" not in hoca.get(f"/ogretmen/sinif/{sinif_id}").text   # Öğrenci yokken gizli

    ali, ayse, can = kayit_ol("ali"), kayit_ol("ayse"), kayit_ol("can")
    for k in (ali, ayse, can):
        k.post("/sinifim/katil", data={"kod": kod})
    _, adimlar = yol_haritasi_cikar(ali)
    for adim_id in adimlar:                                   # Ali hepsini bitirir: %100
        ali.post(f"/adim/{adim_id}", data={"tamamlandi": "1"})
    yol_haritasi_cikar(ayse)                                  # Ayşe başladı ama %0
    # Can hiç başlamadı

    sayfa = hoca.get(f"/ogretmen/sinif/{sinif_id}").text
    assert "Sınıf istatistikleri" in sayfa
    assert "<strong>%50</strong>" in sayfa                    # (100 + 0) / 2
    assert "<strong>2 / 3</strong>" in sayfa                  # Bugün Ali ve Ayşe çalıştı
    assert "1 öğrencinin henüz yol haritası yok" in sayfa
    assert len(re.findall(r'class="sutun( bugun)?"', sayfa)) == 14     # 14 günlük sütun
    assert sayfa.count('class="sutun bugun"') == 1
    assert 'title="%76-100: 1 öğrenci"' in sayfa and 'title="%0-25: 1 öğrenci"' in sayfa


def test_sinif_etkinlikleri_sadece_bu_sinif(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id, kod = sinif_ac(hoca)
    ali, disari = kayit_ol("ali"), kayit_ol("disari")
    ali.post("/sinifim/katil", data={"kod": kod})
    yol_haritasi_cikar(ali)
    yol_haritasi_cikar(disari)                                # Sınıfta değil: sayılmamalı

    bugun = date.today().isoformat()
    ali_id = veritabani.sinif_ozeti(sinif_id)[0]["id"]
    assert veritabani.sinif_etkinlikleri(sinif_id, bugun) == {(ali_id, bugun)}
    assert veritabani.sinif_etkinlikleri(sinif_id, "2999-01-01") == set()   # Başlangıçtan önceki alınmaz
