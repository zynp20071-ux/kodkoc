"""
KodKoç - GitHub commit takibi (8. hafta)

Bu dosya GitHub'ın herkese açık API'sine bağlanıp bir deponun (repository)
son commit'lerini okur.

API nedir?
  Programların birbirleriyle konuşmasını sağlayan kapı. Biz GitHub'a bir
  adres üzerinden HTTP isteği gönderiyoruz, GitHub da bize cevabı JSON
  biçiminde (Python'daki sözlük/liste yapısına çok benzeyen bir metin) veriyor.

  Örnek istek:  GET https://api.github.com/repos/kullanici/proje/commits

Anahtar (token) gerekmez: GitHub, açık depolar için saatte 60 isteğe izin verir.
İstenirse .env dosyasına GITHUB_TOKEN=... yazılarak bu sınır 5000'e çıkarılabilir.
Token ASLA koda yazılmaz.

Ek kütüphane kurmamak için Python'un kendi urllib modülünü kullanıyoruz.
"""

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime

API_ADRESI = "https://api.github.com"
ZAMAN_ASIMI = 10          # GitHub 10 saniyede cevap vermezse vazgeç


class GithubHatasi(Exception):
    """GitHub'dan veri alınamadığında, öğrenciye gösterilecek Türkçe mesajla fırlatılır."""


# ---------------------------------------------------------------------------
# 1) Öğrencinin yazdığı depo adresini anlamak
# ---------------------------------------------------------------------------

# GitHub kullanıcı adı: harf, rakam, tire (en fazla 39 karakter)
# Depo adı: harf, rakam, nokta, alt çizgi, tire
DEPO_KURALI = re.compile(r"^([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100})$")


def depo_adini_coz(metin):
    """
    Öğrenci depoyu farklı şekillerde yazabilir:
        kullanici/proje
        https://github.com/kullanici/proje
        https://github.com/kullanici/proje.git
        github.com/kullanici/proje/
    Hepsini "kullanici/proje" biçimine çevirir. Anlaşılamazsa None döndürür.
    """
    metin = (metin or "").strip()
    metin = re.sub(r"^(https?://)?(www\.)?github\.com/", "", metin, flags=re.IGNORECASE)
    metin = metin.rstrip("/")
    if metin.endswith(".git"):
        metin = metin[:-4]
    eslesme = DEPO_KURALI.match(metin)
    return f"{eslesme.group(1)}/{eslesme.group(2)}" if eslesme else None


# ---------------------------------------------------------------------------
# 2) Commit mesajından adım numarasını bulmak
# ---------------------------------------------------------------------------

# "Adım 3", "adim 3", "ADIM-3", "Adım:3", "adım #3" gibi yazımları yakalar.
ADIM_KURALI = re.compile(r"ad[ıiIİ]m\s*[-:#]?\s*(\d{1,2})", re.IGNORECASE)


def adim_numarasi_bul(mesaj):
    """Commit mesajında "Adım N" geçiyorsa N'yi (sayı olarak), geçmiyorsa None döndürür."""
    eslesme = ADIM_KURALI.search(mesaj or "")
    return int(eslesme.group(1)) if eslesme else None


# ---------------------------------------------------------------------------
# 3) GitHub'dan commit'leri çekmek
# ---------------------------------------------------------------------------

def _yerel_zaman(iso_metin):
    """
    GitHub tarihleri dünya saatiyle (UTC) verir: "2026-11-10T12:34:56Z".
    Bunu bilgisayarın yerel saatine çevirip veritabanındaki biçime getirir.
    """
    zaman = datetime.fromisoformat(iso_metin.replace("Z", "+00:00"))
    return zaman.astimezone().strftime("%Y-%m-%d %H:%M:%S")


def commitleri_getir(depo, adet=30):
    """
    Deponun son commit'lerini döndürür. Her commit bir sözlüktür:
        {"sha", "mesaj", "yazar", "tarih", "url"}
    Bir sorun olursa GithubHatasi fırlatır (mesajı öğrenciye gösterilebilir).
    """
    adres = f"{API_ADRESI}/repos/{depo}/commits?per_page={adet}"

    # İstek başlıkları (headers): GitHub, kim olduğumuzu söyleyen bir User-Agent ister.
    basliklar = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "KodKoc-ders-projesi",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:                                   # İsteğe bağlı: .env'de varsa kullan
        basliklar["Authorization"] = f"Bearer {token}"

    istek = urllib.request.Request(adres, headers=basliklar)
    try:
        with urllib.request.urlopen(istek, timeout=ZAMAN_ASIMI) as cevap:
            veri = json.loads(cevap.read().decode("utf-8"))   # JSON metni -> Python listesi
    except urllib.error.HTTPError as hata:
        # HTTP durum kodları: 404 = bulunamadı, 403/429 = izin yok / çok fazla istek,
        # 409 = depo boş (hiç commit yok)
        if hata.code == 404:
            raise GithubHatasi("Bu depo bulunamadı. Adı doğru mu ve depo herkese açık (public) mı?")
        if hata.code == 409:
            return []                                          # Boş depo: commit yok
        if hata.code in (403, 429):
            raise GithubHatasi("GitHub şu an çok fazla istek aldığımızı söylüyor. Biraz sonra tekrar dene.")
        raise GithubHatasi(f"GitHub bir hata döndürdü (kod {hata.code}).")
    except (urllib.error.URLError, TimeoutError):
        raise GithubHatasi("GitHub'a bağlanılamadı. İnternet bağlantını kontrol et.")

    commitler = []
    for oge in veri:
        # Dışarıdan gelen veriye körü körüne güvenme: bağlantı GitHub'a gitmiyorsa atla
        if not str(oge.get("html_url", "")).startswith("https://github.com/"):
            continue
        mesaj = oge["commit"]["message"]
        commitler.append({
            "sha": oge["sha"],
            "mesaj": mesaj.split("\n")[0][:200],     # Sadece ilk satır (özet), en fazla 200 harf
            "yazar": (oge.get("author") or {}).get("login") or oge["commit"]["author"]["name"],
            "tarih": _yerel_zaman(oge["commit"]["author"]["date"]),
            "url": oge["html_url"],
        })
    return commitler
