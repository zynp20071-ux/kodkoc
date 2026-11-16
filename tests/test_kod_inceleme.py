"""'Kodumu incelet' testleri: geri bildirim, hak sınırı, güvenlik ve öğretmen görünümü."""

import re

import kodkoc
import veritabani
from conftest import adim_bolumu, yol_haritasi_cikar

ORNEK_KOD = "gorevler = []\nfor g in gorevler:\n    print(g)"


def test_satir_numaralama():
    assert kodkoc.satir_numarala("a = 1\n\nb = 2") == "1: a = 1\n2: \n3: b = 2"


def test_kod_incelemesi(kayit_ol, sahte_yapay_zeka):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert "Kodumu incelet" in sayfa and "Kalan hak: 5 / 5" in sayfa

    ali.post(f"/adim/{adimlar[1]}/incele", data={"kod": ORNEK_KOD + "\n\n", "aciklama": "Liste boş kalıyor"})
    cagri = sahte_yapay_zeka["inceleme"][0]
    assert cagri["kod"] == ORNEK_KOD                       # Sondaki boş satırlar atıldı
    assert cagri["kod"].endswith("    print(g)")           # Girinti korundu
    assert cagri["baslik"] == "Adım 2: Görev Ekleme"       # Doğru adım gönderildi

    bolum = adim_bolumu(ali.get(f"/yol-haritasi/{harita_id}").text, adimlar[1])
    assert "<strong>İyi gidenler:</strong>" in bolum and "Satır 2" in bolum
    assert "Sen: Liste boş kalıyor" in bolum
    assert "for g in gorevler:" in bolum                   # Gönderilen kod görünüyor
    assert "Kalan hak: 4 / 5" in bolum


def test_bos_ve_cok_uzun_kod_reddedilir(kayit_ol, sahte_yapay_zeka):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)
    assert "yapıştırmayı unuttun" in ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": "  \n "},
                                              follow_redirects=True).text
    assert "çok uzun" in ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": "x" * 5001},
                                  follow_redirects=True).text
    assert sahte_yapay_zeka["inceleme"] == []              # Yapay zekâya hiç gitmedi


def test_bes_hak_sonra_biter(kayit_ol, sahte_yapay_zeka):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    for _ in range(5):
        ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": ORNEK_KOD})
    cevap = ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": ORNEK_KOD}, follow_redirects=True)
    assert "inceleme hakkını kullandın" in cevap.text
    assert len(sahte_yapay_zeka["inceleme"]) == 5          # 6. istek yapay zekâya gitmedi
    bolum = adim_bolumu(ali.get(f"/yol-haritasi/{harita_id}").text, adimlar[0])
    assert "Kodumu incelet</summary>" not in bolum
    # Hak sınırı adım başına: diğer adımda hâlâ 5 hak var
    assert "Kalan hak: 5 / 5" in adim_bolumu(ali.get(f"/yol-haritasi/{harita_id}").text, adimlar[1])


def test_koddaki_html_calismaz(kayit_ol):
    """Öğrencinin kodunda HTML/JavaScript olsa bile sayfada düz metin olarak görünmeli (XSS)."""
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": 'print("<script>alert(1)</script>")'})
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert "<script>alert(1)</script>" not in sayfa
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in sayfa


def test_baskasinin_adimina_inceleme_istenemez(kayit_ol, sahte_yapay_zeka):
    ali, ayse = kayit_ol("ali"), kayit_ol("ayse")
    _, adimlar = yol_haritasi_cikar(ali)
    assert ayse.post(f"/adim/{adimlar[0]}/incele", data={"kod": ORNEK_KOD}).status_code == 404
    assert sahte_yapay_zeka["inceleme"] == []


def test_ogretmen_incelemeleri_gorur_ama_isteyemez(kayit_ol):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": ORNEK_KOD})

    sayfa = hoca.get(f"/ogretmen/ogrenci/{ali.kullanici['id']}/yol-haritasi/{harita_id}").text
    assert "Öğrencinin gönderdiği kod" in sayfa and "for g in gorevler:" in sayfa
    assert "Kodumu incelet</summary>" not in sayfa         # Öğretmende form yok
    assert hoca.post(f"/adim/{adimlar[0]}/incele", data={"kod": "x"}).status_code == 404


def test_yol_haritasi_silinince_incelemeler_silinir(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    ali.post(f"/adim/{adimlar[0]}/incele", data={"kod": ORNEK_KOD})
    ali.post(f"/yol-haritasi/{harita_id}/sil")
    assert veritabani.yol_haritasinin_incelemeleri(harita_id) == {}


def test_inceleme_talimati_kod_vermeyi_yasakliyor():
    """Talimattan biri yanlışlıkla bu kuralları silerse test uyarsın."""
    talimat = kodkoc.KOD_INCELEME_TALIMATI
    assert "ASLA düzeltilmiş kod" in talimat
    assert "satır numarasını" in talimat
