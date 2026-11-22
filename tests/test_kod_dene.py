"""
"Kod dene" (tarayıcıda Python) testleri: sayfa, yetki ve güvenlik başlıkları.
Python'un kendisi tarayıcıda (Pyodide) çalıştığı için burada çalıştırılamaz; sayfanın doğru
kurulduğunu ve işçiye verilen geniş iznin SADECE işçiye verildiğini test ediyoruz.
"""

from conftest import yol_haritasi_cikar

import app as uygulama


def test_kod_dene_sayfasi(kayit_ol):
    ali = kayit_ol("ali")
    sayfa = ali.get("/kod-dene")
    assert sayfa.status_code == 200
    assert "/static/python_isci.js" in sayfa.text and 'data-anahtar="kodkoc-kod-genel"' in sayfa.text
    assert 'id="incelet-formu"' not in sayfa.text                      # Adımsız açılınca inceleme yok
    assert "/kod-dene" in ali.get("/").text                        # Menüde


def test_adimdan_acilinca(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    harita = ali.get(f"/yol-haritasi/{harita_id}").text
    assert f"/kod-dene?adim={adimlar[1]}" in harita
    sayfa = ali.get(f"/kod-dene?adim={adimlar[1]}").text
    assert "Adım 2: Görev Ekleme" in sayfa and f'data-anahtar="kodkoc-kod-{adimlar[1]}"' in sayfa
    assert f"/adim/{adimlar[1]}/incele" in sayfa and f"({uygulama.EN_FAZLA_INCELEME} hak kaldı)" in sayfa


def test_inceleme_formu_ayni_rotayi_kullanir(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": "print(1)", "aciklama": ""})
    assert f"({uygulama.EN_FAZLA_INCELEME - 1} hak kaldı)" in ali.get(f"/kod-dene?adim={adimlar[0]}").text


def test_baskasinin_adimi(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    assert kayit_ol("ayse").get(f"/kod-dene?adim={adimlar[0]}").status_code == 404
    assert ali.get("/kod-dene?adim=99999").status_code == 404


def test_giris_gerekli(istemci):
    assert istemci.get("/kod-dene").status_code == 302


def test_isci_icin_ayri_csp(istemci, kayit_ol):
    isci = istemci.get("/static/python_isci.js")
    assert isci.status_code == 200 and "loadPyodide" in isci.text
    csp = isci.headers["Content-Security-Policy"]
    assert "https://cdn.jsdelivr.net" in csp and "'wasm-unsafe-eval'" in csp
    # Sayfaların kendi CSP'si değişmedi: dışarıdan betik ve eval yok
    for adres in ("/kod-dene", "/static/style.css"):
        csp = kayit_ol("ali" if adres == "/kod-dene" else "ayse").get(adres).headers["Content-Security-Policy"]
        assert "jsdelivr" not in csp and "unsafe-eval" not in csp


def test_ogretmen_gorunumunde_baglanti_yok(kayit_ol):
    import re
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    harita_id, _ = yol_haritasi_cikar(ali)
    sayfa = hoca.get(f"/ogretmen/ogrenci/{ali.kullanici['id']}/yol-haritasi/{harita_id}").text
    assert "Python&#39;da dene" not in sayfa and "Python'da dene" not in sayfa
