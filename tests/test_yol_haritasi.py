"""Yol haritası testleri: çıkarma, adım işaretleme, ilerleme, ipucu, not, silme, geçmiş."""

import kodkoc
from conftest import adim_bolumu, yol_haritasi_cikar


def test_bos_proje_uyarisi(kayit_ol):
    assert "Lütfen önce projeni anlat" in kayit_ol("ali").post("/yol-haritasi", data={"proje": ""}).text


def test_yol_haritasi_adimlara_bolunup_gosteriliyor(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert len(adimlar) == 4
    assert "0 / 4 adım · %0" in sayfa
    assert 'class="giris"' in sayfa and 'class="dikkat"' in sayfa


def test_isaretleme_ve_ilerleme(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)

    cevap = ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    assert cevap.headers["Location"].endswith(f"#adim-{adimlar[0]}")    # Aynı adıma geri döner
    ali.post(f"/adim/{adimlar[1]}", data={"tamamlandi": "1"})
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert "2 / 4 adım · %50" in sayfa and "width: 50%" in sayfa

    ali.post(f"/adim/{adimlar[1]}", data={"tamamlandi": "0"})            # Geri alma
    assert "1 / 4 adım" in ali.get(f"/yol-haritasi/{harita_id}").text

    for adim_id in adimlar:
        ali.post(f"/adim/{adim_id}", data={"tamamlandi": "1"})
    assert "Tebrikler" in ali.get(f"/yol-haritasi/{harita_id}").text


def test_bicimsiz_cevap_yine_gosteriliyor(kayit_ol, monkeypatch):
    monkeypatch.setattr(kodkoc, "yol_haritasi_iste", lambda *a: "Başlıksız düz bir cevap.")
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert adimlar == [] and "Başlıksız düz bir cevap." in sayfa and "İlerlemen" not in sayfa


def test_uc_kademeli_ipucu(kayit_ol, sahte_yapay_zeka):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali, "Hesap makinesi")
    for n in (1, 2, 3):
        ali.post(f"/adim/{adimlar[0]}/ipucu", data={"soru": f"soru {n}"})

    cagrilar = sahte_yapay_zeka["ipucu"]
    assert [c["seviye"] for c in cagrilar] == [1, 2, 3]
    assert len(cagrilar[2]["onceki"]) == 2                 # Önceki ipuçları da gönderildi
    assert cagrilar[0]["proje"] == "Hesap makinesi"

    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert sayfa.count('class="ipucu"') == 3 and "Sen: soru 2" in sayfa
    assert "bütün ipuçlarını kullandın" in sayfa

    ali.post(f"/adim/{adimlar[0]}/ipucu", data={})          # 4. istek
    assert len(cagrilar) == 3                               # Yapay zekâya gitmedi


def test_yapay_zeka_yogunken_anlasilir_mesaj(kayit_ol, monkeypatch):
    class Yogun(Exception):
        code = 503

    def hata_ver(*a, **kw):          # **kw: "bilgi=" gibi anahtar argümanları da kabul et
        raise Yogun("503 UNAVAILABLE")

    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    monkeypatch.setattr(kodkoc, "ipucu_iste", hata_ver)
    cevap = ali.post(f"/adim/{adimlar[0]}/ipucu", data={}, follow_redirects=True)
    assert "çok yoğun" in cevap.text


def test_not_kaydetme_ve_silme(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    cevap = ali.post(f"/adim/{adimlar[0]}/not", data={"not_metni": "enumerate'i öğrendim"},
                     follow_redirects=True)
    assert "Notun kaydedildi" in cevap.text and "enumerate&#39;i öğrendim" in cevap.text
    ali.post(f"/adim/{adimlar[0]}/not", data={"not_metni": ""})
    assert "enumerate" not in adim_bolumu(ali.get(f"/yol-haritasi/{harita_id}").text, adimlar[0])


def test_yol_haritasi_silme(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali, "Silinecek proje")
    ali.post(f"/adim/{adimlar[0]}/ipucu", data={})
    cevap = ali.post(f"/yol-haritasi/{harita_id}/sil", follow_redirects=True)
    assert "silindi" in cevap.text and "Silinecek proje" not in cevap.text
    assert ali.get(f"/yol-haritasi/{harita_id}").status_code == 404


def test_gecmis_arama_filtre_ve_ozet(kayit_ol):
    ali = kayit_ol("ali")
    h1, adimlar = yol_haritasi_cikar(ali, "Yapılacaklar listesi")
    yol_haritasi_cikar(ali, "Hesap makinesi")
    for adim_id in adimlar:
        ali.post(f"/adim/{adim_id}", data={"tamamlandi": "1"})

    sayfa = ali.get("/gecmis").text
    assert sayfa.index("Hesap makinesi") < sayfa.index("Yapılacaklar")    # En yeni üstte
    assert "<strong>2</strong><span>yol haritası" in sayfa

    sayfa = ali.get("/gecmis?ara=hesap").text
    assert "Hesap makinesi" in sayfa and "Yapılacaklar" not in sayfa
    sayfa = ali.get("/gecmis?durum=bitti").text
    assert "Yapılacaklar" in sayfa and "Hesap makinesi" not in sayfa
    sayfa = ali.get("/gecmis?durum=devam").text
    assert "Hesap makinesi" in sayfa and "Yapılacaklar" not in sayfa
    assert "Aramana uyan" in ali.get("/gecmis?ara=zzzz").text
