"""GitHub takibi testleri. Gerçek GitHub'a gidilmez; urllib'in cevabı taklit edilir."""

import io
import json
import re
import urllib.error

import pytest

import github_takip
import veritabani
from conftest import adim_bolumu, yol_haritasi_cikar


@pytest.mark.parametrize("girdi, beklenen", [
    ("ali/proje", "ali/proje"),
    ("https://github.com/ali/proje", "ali/proje"),
    ("github.com/Ali-Veli/my.repo_1/", "Ali-Veli/my.repo_1"),
    ("https://github.com/ali/proje.git", "ali/proje"),
    ("ali", None),
    ("ali/proje/tree/main", None),
    ("https://gitlab.com/ali/proje", None),
    ("../../etc/passwd", None),
    ("", None),
])
def test_depo_adini_cozme(girdi, beklenen):
    assert github_takip.depo_adini_coz(girdi) == beklenen


@pytest.mark.parametrize("mesaj, beklenen", [
    ("Adım 3: menü eklendi", 3), ("adim 2 bitti", 2), ("ADIM-4 test", 4),
    ("adım:5", 5), ("İlk commit", None), ("adımlar düzenlendi", None), ("fix #3", None),
])
def test_adim_numarasi_bulma(mesaj, beklenen):
    assert github_takip.adim_numarasi_bul(mesaj) == beklenen


# --- Sahte GitHub ---

def sahte_commit(sha, mesaj, tarih="2026-11-10T09:00:00Z"):
    """GitHub API'sinin döndürdüğü bir commit'in sadeleştirilmiş hali."""
    return {"sha": sha, "html_url": f"https://github.com/ali/proje/commit/{sha}",
            "author": {"login": "ali"},
            "commit": {"message": mesaj, "author": {"name": "Ali", "date": tarih}}}


class _SahteCevap(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


@pytest.fixture
def github(monkeypatch):
    """
    urllib.request.urlopen'ı taklit eder. Testler durum["liste"]'yi doldurarak
    GitHub'ın ne döndüreceğini, durum["hata"]'yı vererek hata kodunu seçer.
    """
    durum = {"liste": [], "hata": None, "istekler": []}

    def sahte_urlopen(istek, timeout=None):
        durum["istekler"].append(istek)
        if durum["hata"] == "ag":
            raise urllib.error.URLError("bağlantı yok")
        if durum["hata"]:
            raise urllib.error.HTTPError(istek.full_url, durum["hata"], "hata", {}, None)
        return _SahteCevap(json.dumps(durum["liste"]).encode())

    monkeypatch.setattr(github_takip.urllib.request, "urlopen", sahte_urlopen)
    return durum


def test_commitler_okunuyor(github):
    github["liste"] = [sahte_commit("a1", "Adım 1: başlangıç\n\nuzun açıklama"),
                       {"sha": "kotu", "html_url": "javascript:alert(1)", "author": None,
                        "commit": {"message": "x", "author": {"name": "y", "date": "2026-11-10T09:00:00Z"}}}]
    commitler = github_takip.commitleri_getir("ali/proje")
    assert len(commitler) == 1                                  # GitHub dışı bağlantı atlandı
    assert commitler[0]["mesaj"] == "Adım 1: başlangıç"         # Sadece ilk satır
    assert re.match(r"2026-11-10 \d\d:00:00", commitler[0]["tarih"])
    assert github["istekler"][0].get_header("User-agent") == "KodKoc-ders-projesi"


@pytest.mark.parametrize("kod, mesaj", [
    (404, "bulunamadı"), (403, "çok fazla istek"), (500, "kod 500"), ("ag", "bağlanılamadı")])
def test_github_hatalari_turkce(github, kod, mesaj):
    github["hata"] = kod
    with pytest.raises(github_takip.GithubHatasi, match=mesaj):
        github_takip.commitleri_getir("ali/proje")


def test_bos_depo(github):
    github["hata"] = 409
    assert github_takip.commitleri_getir("ali/proje") == []


def test_depo_baglama_ve_adimlara_esleme(kayit_ol, github):
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali)
    assert "anlayamadım" in ali.post(f"/yol-haritasi/{harita_id}/github",
                                     data={"depo": "sadece-ad"}, follow_redirects=True).text

    github["liste"] = [sahte_commit("c3", "Adım 2: görev ekleme"),
                       sahte_commit("c2", "adim 1 menü"),
                       sahte_commit("c1", "İlk commit"),
                       sahte_commit("c0", "Adım 9: olmayan adım")]
    sayfa = ali.post(f"/yol-haritasi/{harita_id}/github", data={"depo": "https://github.com/ali/proje"},
                     follow_redirects=True).text
    assert "4 yeni commit bulundu" in sayfa
    assert "adim 1 menü" in adim_bolumu(sayfa, adimlar[0])
    assert "Adım 2: görev ekleme" in adim_bolumu(sayfa, adimlar[1])
    assert "adim-commitleri" not in adim_bolumu(sayfa, adimlar[2])
    assert "basmayı unutma" in adim_bolumu(sayfa, adimlar[0])
    assert sayfa.count("adıma bağlı değil") == 2

    ali.post(f"/adim/{adimlar[0]}", data={"tamamlandi": "1"})
    assert "basmayı unutma" not in adim_bolumu(ali.get(f"/yol-haritasi/{harita_id}").text, adimlar[0])


def test_yenileme_sadece_yenileri_ekler_ve_beklemeli(kayit_ol, github):
    ali = kayit_ol("ali")
    harita_id, _ = yol_haritasi_cikar(ali)
    github["liste"] = [sahte_commit("c1", "ilk")]
    ali.post(f"/yol-haritasi/{harita_id}/github", data={"depo": "ali/proje"})

    assert "saniye sonra" in ali.post(f"/yol-haritasi/{harita_id}/github/yenile", follow_redirects=True).text

    b = veritabani.baglan()                                      # 30 saniye geçmiş gibi yap
    b.execute("UPDATE yol_haritalari SET github_son_kontrol = '2026-01-01 00:00:00'")
    b.commit()
    github["liste"].insert(0, sahte_commit("c2", "ikinci"))
    sayfa = ali.post(f"/yol-haritasi/{harita_id}/github/yenile", follow_redirects=True).text
    assert "1 yeni commit" in sayfa and "2 commit" in sayfa


def test_depo_degisince_eski_commitler_silinir(kayit_ol, github):
    ali = kayit_ol("ali")
    harita_id, _ = yol_haritasi_cikar(ali)
    github["liste"] = [sahte_commit("c1", "eski depodan")]
    ali.post(f"/yol-haritasi/{harita_id}/github", data={"depo": "ali/eski"})
    github["liste"] = [sahte_commit("z1", "yeni depodan")]
    sayfa = ali.post(f"/yol-haritasi/{harita_id}/github", data={"depo": "ali/yeni"}, follow_redirects=True).text
    assert "yeni depodan" in sayfa and "eski depodan" not in sayfa

    sayfa = ali.post(f"/yol-haritasi/{harita_id}/github/kaldir", follow_redirects=True).text
    assert "GitHub deponu bağla" in sayfa


def test_ogretmen_commitleri_gorur(kayit_ol, github):
    hoca = kayit_ol("hoca", "ogretmen")
    sinif_id = int(hoca.post("/ogretmen/sinif", data={"ad": "A"}).headers["Location"].rsplit("/", 1)[1])
    kod = re.search(r"<strong>([A-Z0-9]{6})</strong>", hoca.get(f"/ogretmen/sinif/{sinif_id}").text).group(1)
    ali = kayit_ol("ali")
    ali.post("/sinifim/katil", data={"kod": kod})
    harita_id, _ = yol_haritasi_cikar(ali)
    github["liste"] = [sahte_commit("c1", "Adım 1 bitti"), sahte_commit("c2", "Adım 2 bitti")]
    ali.post(f"/yol-haritasi/{harita_id}/github", data={"depo": "ali/proje"})

    sayfa = hoca.get(f"/ogretmen/ogrenci/{ali.kullanici['id']}/yol-haritasi/{harita_id}").text
    assert "Adım 1 bitti" in sayfa
    assert "Yenile</button>" not in sayfa and "Kaldır</button>" not in sayfa
    tablo = hoca.get(f"/ogretmen/sinif/{sinif_id}").text
    assert re.search(r"<td>\s*2\s*</td>", tablo)               # Commit sütunu


def test_yol_haritasi_silinince_commitler_silinir(kayit_ol, github):
    ali = kayit_ol("ali")
    harita_id, _ = yol_haritasi_cikar(ali)
    github["liste"] = [sahte_commit("c1", "x")]
    ali.post(f"/yol-haritasi/{harita_id}/github", data={"depo": "ali/proje"})
    ali.post(f"/yol-haritasi/{harita_id}/sil")
    assert veritabani.yol_haritasinin_commitleri(harita_id) == []
