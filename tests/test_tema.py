"""Koyu tema testleri: renkler değişkenlerde mi, koyu tema her rengi tanımlıyor mu?"""

import os
import re

CSS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "style.css")


def css_metni():
    with open(CSS, encoding="utf-8") as dosya:
        return dosya.read()


def blok(metin, secici):
    """CSS'ten bir seçicinin { ... } bloğunu kesip alır."""
    bas = metin.index(secici)
    return metin[metin.index("{", bas) + 1: metin.index("}", bas)]


def degiskenler(blok_metni):
    return set(re.findall(r"(--[\w-]+)\s*:", blok_metni))


def test_renk_kodlari_sadece_degisken_tanimlarinda():
    """
    Bir renk doğrudan yazılırsa (#93391C gibi) koyu temada değişmez ve göze batar.
    Bu yüzden her renk kodu "--ad: #...;" şeklinde bir değişken tanımında olmalı.
    """
    for no, satir in enumerate(css_metni().splitlines(), start=1):
        if re.search(r"#[0-9A-Fa-f]{3,6}\b", satir):
            assert satir.strip().startswith("--"), f"style.css:{no} sabit renk var: {satir.strip()}"


def test_koyu_tema_her_rengi_tanimliyor():
    metin = css_metni()
    acik = degiskenler(blok(metin, ":root {"))
    koyu_secimle = degiskenler(blok(metin, ':root[data-tema="koyu"]'))
    koyu_otomatik = degiskenler(blok(metin, ':root:not([data-tema="acik"])'))
    assert len(acik) >= 15
    assert acik == koyu_secimle == koyu_otomatik


def test_kullanilan_her_degisken_tanimli():
    """var(--yazim-hatasi) gibi tanımsız bir değişken kullanılırsa renk kaybolur."""
    metin = re.sub(r"/\*.*?\*/", "", css_metni(), flags=re.S)     # /* açıklamaları */ çıkar
    tanimli = degiskenler(blok(metin, ":root {"))
    kullanilan = set(re.findall(r"var\((--[\w-]+)\)", metin))
    assert kullanilan <= tanimli, f"Tanımsız: {kullanilan - tanimli}"


def test_sayfada_tema_dugmesi_ve_erken_betik_var(istemci):
    sayfa = istemci.get("/kayit").text
    assert 'id="tema-dugmesi"' in sayfa
    # Tema betiği <head> içinde olmalı ki sayfa çizilmeden uygulansın
    head = sayfa.split("</head>")[0]
    assert 'localStorage.getItem("tema")' in head
