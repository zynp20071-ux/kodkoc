"""kodkoc.py testleri: kod filtresi, yapay zekâ meşgulken tekrar deneme, terminal sürümü."""

import builtins
import getpass

import pytest

import kodkoc
import veritabani


def test_kod_blogu_filtreleniyor():
    temiz = kodkoc.kod_bloklarini_temizle("Şuna bak:\n```python\nprint('x')\n```\nsonra dene")
    assert "print" not in temiz
    assert "KodKoç kod vermez" in temiz and "sonra dene" in temiz


@pytest.mark.parametrize("parca, kalmali", [
    ("`input()`", True),                   # Kavram adı
    ("`while`", True),
    ("`gorevler.append`", True),
    ('`"3"`', True),                       # Kısa değer
    ("`==`", True),                        # Operatör
    ("`try-except`", True),
    ("`gorevler.pop(int(no) - 1)`", False),  # Çözüm satırı
    ("`int(no)`", False),                  # İçi dolu parantez = çözüm ipucu
    ('`secim == "3"`', False),
    ("`for g in gorevler:`", False),
    ("`x = 5`", False),
])
def test_satir_ici_kod_filtresi(parca, kalmali):
    temiz = kodkoc.satir_ici_kodu_temizle(f"Şuna bak: {parca} tamam mı?")
    assert (parca in temiz) == kalmali
    assert temiz.startswith("Şuna bak:") and temiz.endswith("tamam mı?")


# --- yapay_zekaya_sor: sahte bir Gemini istemcisiyle ---

class Yogun(Exception):
    code = 503


class Kalici(Exception):
    code = 400


class SahteIstemci:
    """Önce verilen hataları sırayla fırlatan, sonra cevap dönen sahte Gemini istemcisi."""
    def __init__(self, hatalar):
        self.hatalar = list(hatalar)
        self.cagri = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.cagri += 1
        if self.hatalar:
            raise self.hatalar.pop(0)

        class Cevap:
            text = "tamam ```gizli kod``` bitti `liste.pop(0)` `input()`"
        return Cevap()


@pytest.fixture(autouse=True)
def beklemesiz(monkeypatch):
    """Testlerde gerçekten 2-4 saniye beklemeyelim."""
    monkeypatch.setattr(kodkoc.time, "sleep", lambda saniye: None)


def test_yogunlukta_tekrar_dener_ve_kodu_filtreler():
    istemci = SahteIstemci([Yogun()] * len(kodkoc.MODELLER))      # İlk turda bütün modeller yoğun
    cevap = kodkoc.yapay_zekaya_sor(istemci, "mesaj", "talimat")
    assert cevap.startswith("tamam") and "```" not in cevap
    assert "liste.pop(0)" not in cevap and "`input()`" in cevap     # İki filtre de çalıştı
    assert istemci.cagri == len(kodkoc.MODELLER) + 1


def test_kalici_hatada_bosuna_beklemez():
    istemci = SahteIstemci([Kalici()] * 10)
    with pytest.raises(Kalici):
        kodkoc.yapay_zekaya_sor(istemci, "mesaj", "talimat")
    assert istemci.cagri == len(kodkoc.MODELLER)                  # Sadece bir tur


# --- Terminal sürümü: yol haritasını hesaba ekleme ---

def terminal_calistir(monkeypatch, girdiler, sifreler):
    """input() ve getpass() yerine sırayla verilen cevapları kullanır."""
    girdi, sifre = iter(girdiler), iter(sifreler)
    monkeypatch.setattr(builtins, "input", lambda *a: next(girdi))
    monkeypatch.setattr(getpass, "getpass", lambda *a: next(sifre))
    kodkoc.hesaba_ekle("Terminal projesi", "", "### Adım 1: A\n- x", None)


def test_terminal_hesaba_ekleme(monkeypatch):
    kid = veritabani.kullanici_ekle("zeynep", "gizli123")

    terminal_calistir(monkeypatch, [""], [])                                    # Boş: eklenmez
    terminal_calistir(monkeypatch, ["zeynep"], ["yanlis", "yanlis", "yanlis"])  # 3 yanlış
    assert veritabani.tum_yol_haritalari(kid) == []

    terminal_calistir(monkeypatch, ["zeynep"], ["yanlis", "gizli123"])         # 2. denemede doğru
    satirlar = veritabani.tum_yol_haritalari(kid)
    assert len(satirlar) == 1 and satirlar[0]["proje"] == "Terminal projesi"
