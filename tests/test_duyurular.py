"""Sınıf duyurusu testleri ve yazdırma görünümü testleri."""

import re

import veritabani
from conftest import yol_haritasi_cikar


def sinif_ac(hoca, ad="9-A"):
    """Öğretmen olarak sınıf açar; (sınıf id'si, katılım kodu) döndürür."""
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": ad}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    return sinif_id, kod


def menu_sayisi(sayfa):
    """Menüde 'Sınıfım' yanındaki duyuru sayısı (yoksa 0)."""
    m = re.search(r'Sınıfım\s*(?:<!--.*?-->)?\s*<span class="menu-rozeti"[^>]*>(\d+)</span>', sayfa, re.S)
    return int(m.group(1)) if m else 0


def test_duyuru_ogrenciye_ulasir_ve_okundu_olur(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id, kod = sinif_ac(hoca)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})

    hoca.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "Cuma'ya kadar 3. adım!"})
    hoca.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "Yarın ders yok."})

    ana = ali.get("/").text
    assert "Öğretmeninden yeni duyuru" in ana
    assert "Cuma&#39;ya kadar 3. adım!" in ana and "Yarın ders yok." in ana
    assert menu_sayisi(ana) == 2

    # Sınıfım sayfası: duyurular "Yeni" etiketli, menü sayısı hemen sıfır
    sinifim = ali.get("/sinifim").text
    assert sinifim.count('<span class="yeni-etiketi">Yeni</span>') == 2
    assert menu_sayisi(sinifim) == 0

    # Bir kez görüldü: artık yeni değil, ana sayfada kart yok
    assert "Öğretmeninden yeni duyuru" not in ali.get("/").text
    assert 'yeni-etiketi' not in ali.get("/sinifim").text
    assert "Yarın ders yok." in ali.get("/sinifim").text        # Ama listede durmaya devam ediyor

    # Sonra gelen duyuru yine yeni sayılır
    hoca.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "Üçüncü"})
    assert menu_sayisi(ali.get("/").text) == 1


def test_ana_sayfa_en_fazla_uc_duyuru(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id, kod = sinif_ac(hoca)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    for i in range(5):
        hoca.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": f"Duyuru no {i}"})
    ana = ali.get("/").text
    assert ana.count('class="duyuru-metni"') == 3
    assert "Duyuru no 4" in ana and "Duyuru no 1" not in ana     # En yeniler
    assert menu_sayisi(ana) == 5


def test_sinifta_olmayan_duyuruyu_gormez(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id, kod = sinif_ac(hoca)
    ali = kayit_ol("ali")
    ayse = kayit_ol("ayse")
    ali.post("/sinifim/katil", data={"kod": kod})
    hoca.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "Sadece 9-A"})
    assert "Sadece 9-A" not in ayse.get("/").text and "Sadece 9-A" not in ayse.get("/sinifim").text

    # Ali sınıftan ayrılınca duyuruları da görmez
    ali.post(f"/sinifim/{sinif_id}/ayril")
    assert "Sadece 9-A" not in ali.get("/sinifim").text
    assert menu_sayisi(ali.get("/").text) == 0


def test_baska_ogretmen_duyuru_yazamaz_silemez(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id, _ = sinif_ac(hoca)
    hoca.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "Benim duyurum"})
    duyuru_id = veritabani.sinifin_duyurulari(sinif_id)[0]["id"]

    baska = kayit_ol("baska", "ogretmen")
    assert baska.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "Sahte"}).status_code == 404
    assert baska.post(f"/ogretmen/duyuru/{duyuru_id}/sil").status_code == 404
    # Öğrenci de duyuru yazamaz (öğretmen sayfası)
    ali = kayit_ol("ali")
    assert ali.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "x"}).status_code == 302
    assert [d["metin"] for d in veritabani.sinifin_duyurulari(sinif_id)] == ["Benim duyurum"]

    assert hoca.post(f"/ogretmen/duyuru/{duyuru_id}/sil").status_code == 302
    assert veritabani.sinifin_duyurulari(sinif_id) == []


def test_bos_ve_uzun_duyuru_reddedilir(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id, _ = sinif_ac(hoca)
    hoca.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "   "})
    cevap = hoca.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "a" * 1001}, follow_redirects=True)
    assert "1-1000 karakter" in cevap.text
    assert veritabani.sinifin_duyurulari(sinif_id) == []


def test_duyuru_html_calismaz(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id, kod = sinif_ac(hoca)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    hoca.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "<script>alert(1)</script>"})
    for sayfa in (ali.get("/").text, hoca.get(f"/ogretmen/sinif/{sinif_id}").text):
        assert "<script>alert(1)</script>" not in sayfa and "&lt;script&gt;" in sayfa


def test_sinif_silinince_duyurular_da_silinir(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id, _ = sinif_ac(hoca)
    hoca.post(f"/ogretmen/sinif/{sinif_id}/duyuru", data={"metin": "x"})
    assert hoca.post(f"/ogretmen/sinif/{sinif_id}/sil").status_code == 302   # Yabancı anahtar hatası yok
    assert veritabani.sinifin_duyurulari(sinif_id) == []


# --- Yazdırma görünümü ---------------------------------------------------------

def test_yazdir_dugmesi_ve_not(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/not", data={"not_metni": "while True öğrendim"})
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert 'id="yazdir-dugmesi"' in sayfa and "window.print()" in sayfa
    assert 'class="yazdir-notu ogrenci-notu"' in sayfa


def test_yazdirma_css_kurallari():
    import os
    css = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "style.css"),
               encoding="utf-8").read()
    yazdir = css[css.index("@media print"):]
    for gizlenen in (".menu", ".adim-araclar", "form", "button"):
        assert gizlenen in yazdir
    assert "--zemin: #FFFFFF" in yazdir                   # Koyu temada bile beyaz kâğıt
