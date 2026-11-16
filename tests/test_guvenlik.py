"""Güvenlik testleri: CSRF koruması, HTML kaçışı (XSS) ve SQL enjeksiyonu."""

import re

from flask.testing import FlaskClient

import app as uygulama
import veritabani
from conftest import yol_haritasi_cikar


def test_csrf_jetonu_olmayan_form_reddedilir(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, _ = yol_haritasi_cikar(ali)
    # FlaskClient.post: jeton ekleyen yardımcıyı atlayıp "çıplak" istek gönderir
    cevap = FlaskClient.post(ali, f"/yol-haritasi/{harita_id}/sil")
    assert cevap.status_code == 400 and "Form gönderilemedi" in cevap.text
    assert ali.get(f"/yol-haritasi/{harita_id}").status_code == 200          # Silinmedi


def test_yanlis_csrf_jetonu_reddedilir(kayit_ol):
    ali = kayit_ol("ali")
    harita_id, _ = yol_haritasi_cikar(ali)
    cevap = ali.post(f"/yol-haritasi/{harita_id}/sil", data={"csrf": "tahmin-edilen-jeton"})
    assert cevap.status_code == 400


def test_sayfadaki_jetonla_form_calisir(istemci):
    """Gerçek tarayıcı gibi: sayfayı aç, formdaki gizli jetonu al, onunla gönder."""
    sayfa = istemci.get("/kayit").text
    jeton = re.search(r'name="csrf" value="([0-9a-f]+)"', sayfa).group(1)
    cevap = FlaskClient.post(istemci, "/kayit", data={
        "csrf": jeton, "kullanici_adi": "ali", "sifre": "sifre123", "sifre_tekrar": "sifre123"})
    assert cevap.status_code == 302


def test_her_post_formunda_jeton_var(kayit_ol):
    """Şablonlardaki bütün POST formlarında gizli CSRF alanı olmalı."""
    import glob
    import os
    for yol in glob.glob(os.path.join(os.path.dirname(uygulama.__file__), "templates", "*.html")):
        metin = open(yol, encoding="utf-8").read()
        formlar = re.findall(r'<form method="post"[^>]*>\s*(<input[^>]*>)?', metin)
        for ilk_alan in formlar:
            assert 'name="csrf"' in ilk_alan, f"{os.path.basename(yol)}: CSRF alanı eksik"


def test_cerez_ayarlari():
    assert uygulama.app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert uygulama.app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_html_kacisi_xss(kayit_ol, sahte_yapay_zeka):
    """Kullanıcının yazdığı HTML/JavaScript sayfada çalışmamalı, düz metin görünmeli."""
    ali = kayit_ol("ali")
    harita_id, adimlar = yol_haritasi_cikar(ali, "<script>alert(1)</script> projesi")
    ali.post(f"/adim/{adimlar[0]}/not", data={"not_metni": "<img src=x onerror=alert(1)>"})
    sayfa = ali.get(f"/yol-haritasi/{harita_id}").text
    assert "<script>alert(1)</script>" not in sayfa and "&lt;script&gt;" in sayfa
    assert "<img src=x" not in sayfa


def test_sql_enjeksiyonu_ise_yaramaz(kayit_ol):
    ali = kayit_ol("ali")
    yol_haritasi_cikar(ali)
    assert "Aramana uyan" in ali.get("/gecmis?ara=' OR 1=1--").text
    # Giriş formunda da işe yaramaz
    cevap = ali.post("/cikis")
    cevap = ali.post("/giris", data={"kullanici_adi": "ali' --", "sifre": "x"})
    assert "yanlış" in cevap.text
    assert veritabani.kullanici_sayisi() == 1


def test_env_kaydi_diger_ayarlari_korur(kayit_ol, tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("FLASK_SECRET_KEY='abc'\nGEMINI_MODEL=x\n", encoding="utf-8")
    monkeypatch.setattr(uygulama, "ENV_DOSYASI", str(env))
    kayit_ol("ali").post("/anahtar", data={"anahtar": "yeni-anahtar"})
    icerik = env.read_text(encoding="utf-8")
    assert "FLASK_SECRET_KEY" in icerik and "GEMINI_MODEL" in icerik
    assert "GEMINI_API_KEY='yeni-anahtar'" in icerik
