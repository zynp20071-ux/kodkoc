"""Profil sayfası testleri: şifre değiştirme, çalışma serisi ve etkinlik takvimi."""

from datetime import date, timedelta

import pytest

import app as uygulama
import veritabani
from conftest import yol_haritasi_cikar

BUGUN = date(2026, 11, 10)          # Salı. Testler sabit bir günle çalışır, tarihe göre değişmez.


def gun(fark):
    """BUGUN'den 'fark' gün önceki tarih."""
    return BUGUN - timedelta(days=fark)


# --- Sayfa ve menü -----------------------------------------------------------

def test_profil_sayfasi(kayit_ol):
    ali = kayit_ol("ali")
    sayfa = ali.get("/profil").text
    assert "Merhaba, ali" in sayfa and "Öğrenci hesabı" in sayfa
    assert "Şifremi değiştir" in sayfa and "Son 4 hafta" in sayfa
    assert sayfa.count('class="takvim-kare') == 28                # 4 hafta x 7 gün
    # Menüde kullanıcı adı profile bağlantı
    assert 'class="kullanici-adi" href="/profil"' in ali.get("/gecmis").text


def test_profil_giris_ister(istemci):
    assert istemci.get("/profil").headers["Location"].endswith("/giris")


def test_ogretmen_profili(kayit_ol):
    assert "Öğretmen hesabı" in kayit_ol("hoca", "ogretmen").get("/profil").text


# --- Şifre değiştirme ----------------------------------------------------------

def sifre_formu(eski="sifre123", yeni="yeniSifre9", tekrar=None):
    return {"eski_sifre": eski, "yeni_sifre": yeni, "yeni_sifre_tekrar": yeni if tekrar is None else tekrar}


def test_sifre_degisir(kayit_ol, istemci):
    ali = kayit_ol("ali")
    cevap = ali.post("/profil/sifre", data=sifre_formu(), follow_redirects=True)
    assert "Şifren değiştirildi." in cevap.text
    assert veritabani.kullanici_dogrula("ali", "sifre123") is None    # Eski şifre artık geçmiyor
    assert veritabani.kullanici_dogrula("ali", "yeniSifre9") is not None
    # Yeni şifreyle gerçekten giriş yapılabiliyor
    giris = istemci.post("/giris", data={"kullanici_adi": "ali", "sifre": "yeniSifre9"})
    assert giris.status_code == 302 and giris.headers["Location"] == "/"


@pytest.mark.parametrize("form, mesaj", [
    (sifre_formu(eski="yanlis99"), "Şu anki şifreni yanlış girdin."),
    (sifre_formu(yeni="kisa"), "en az 6 karakter"),
    (sifre_formu(tekrar="baskaSifre1"), "birbirinin aynısı değil"),
    (sifre_formu(yeni="sifre123"), "eskisiyle aynı olamaz"),
])
def test_sifre_degismez(kayit_ol, form, mesaj):
    ali = kayit_ol("ali")
    cevap = ali.post("/profil/sifre", data=form, follow_redirects=True)
    assert mesaj in cevap.text
    assert veritabani.kullanici_dogrula("ali", "sifre123") is not None  # Şifre aynı kaldı


def test_sifre_degistirme_csrf_ister(kayit_ol):
    ali = kayit_ol("ali")
    assert ali.post("/profil/sifre", data={**sifre_formu(), "csrf": "sahte"}).status_code == 400
    assert veritabani.kullanici_dogrula("ali", "sifre123") is not None


# --- Çalışma serisi -----------------------------------------------------------------

@pytest.mark.parametrize("gunler, beklenen", [
    (set(), (0, 0)),
    ({gun(0)}, (1, 1)),
    ({gun(0), gun(1), gun(2)}, (3, 3)),
    ({gun(1), gun(2)}, (2, 2)),                       # Bugün henüz çalışmadı: seri dünden sayılır
    ({gun(2), gun(3)}, (0, 2)),                       # Dün boş: seri koptu, ama en uzun 2
    ({gun(0), gun(5), gun(6), gun(7), gun(8)}, (1, 4)),
])
def test_seri_hesapla(gunler, beklenen):
    assert uygulama.seri_hesapla(gunler, BUGUN) == beklenen


def test_takvim_olustur():
    takvim = uygulama.takvim_olustur({gun(0).isoformat(): 5, gun(1).isoformat(): 1}, BUGUN)
    assert len(takvim) == 4 and all(len(hafta) == 7 for hafta in takvim)
    son_hafta = takvim[-1]
    # BUGUN Salı: son haftanın Pazartesi'si dün (seviye 1), Salı bugün (5 etkinlik -> seviye 3)
    assert son_hafta[0]["tarih"] == "09.11.2026" and son_hafta[0]["seviye"] == 1
    assert son_hafta[1]["sayi"] == 5 and son_hafta[1]["seviye"] == 3
    assert not son_hafta[1]["gelecek"] and son_hafta[2]["gelecek"]   # Çarşamba henüz gelmedi
    assert takvim[0][0]["tarih"] == "19.10.2026"                     # 3 hafta önceki Pazartesi


def test_calisma_gunleri_etkinlikleri_sayar(kayit_ol):
    ali = kayit_ol("ali")
    _, adimlar = yol_haritasi_cikar(ali)                              # 1: yol haritası
    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})          # 2: adım bitirme
    ali.post(f"/adim/{adimlar[1]}/ipucu", data={})                     # 3: ipucu
    ali.post(f"/adim/{adimlar[1]}/soru", data={"soru": "?"})            # 4: soru
    ali.post(f"/adim/{adimlar[1]}/incele", data={"kod": "print(1)"})   # 5: kod inceleme
    bugun = date.today().isoformat()
    assert veritabani.calisma_gunleri(ali.kullanici["id"]) == {bugun: 5}

    # Başkasının etkinliği sayılmaz
    assert veritabani.calisma_gunleri(kayit_ol("ayse").kullanici["id"]) == {}

    sayfa = ali.get("/profil").text
    assert "bugün de çalıştın" in sayfa and "1 gün" in sayfa
