"""
KodKoç - 1. sürüm (6. hafta)

Ne yapar?
  1. Öğrenciden yapmak istediği projeyi anlatmasını ister.
  2. Bu anlatımı, özel bir talimatla birlikte yapay zekâya (Google Gemini) gönderir.
  3. Yapay zekânın çıkardığı adım adım yol haritasını ekrana yazar.
  4. Yol haritasını "yol_haritalari" klasörüne bir dosya olarak kaydeder.

Önemli kural: KodKoç öğrenciye HAZIR KOD VERMEZ, sadece yol gösterir.
"""

import json
import os
import re
import time
from datetime import datetime

from dotenv import load_dotenv, set_key   # .env dosyasını okumak / tek bir satırını yazmak için
from google import genai          # Google Gemini kütüphanesi
from google.genai import types


# ---------------------------------------------------------------------------
# 1) AYARLAR
# ---------------------------------------------------------------------------

# .env dosyasını okur. API anahtarı kodun içine yazılmaz, güvenlik için orada durur.
load_dotenv()
API_ANAHTARI = os.getenv("GEMINI_API_KEY")

# Denenecek modeller (sırayla). "-latest" ile biten adlar Google'ın o anki
# en güncel modelini gösterir, böylece eski bir model kapanınca kod bozulmaz.
# İstenirse .env dosyasına GEMINI_MODEL=... yazılarak model değiştirilebilir.
MODELLER = [m for m in [os.getenv("GEMINI_MODEL"),
                        "gemini-flash-latest",
                        "gemini-flash-lite-latest"] if m]

# Yol haritalarının kaydedileceği klasör
KAYIT_KLASORU = "yol_haritalari"


# ---------------------------------------------------------------------------
# 2) YAPAY ZEKÂYA VERİLEN TALİMAT (KodKoç'u sıradan bir sohbet botundan
#    ayıran kısım burası)
# ---------------------------------------------------------------------------

TALIMAT = """
Sen "KodKoç" adında, yazılıma yeni başlayan öğrencilere yardım eden bir koçsun.

Görevin: Öğrencinin anlattığı projeyi, onun seviyesine uygun, 5 ile 8 arasında
adımdan oluşan bir yol haritasına bölmek.

Her adım için şunları yaz:
- Adımın kısa başlığı
- Bu adımda ne yapılacağı (1-2 cümle)
- Bu adım için öğrenilmesi gereken konular (anahtar kelimeler halinde)
- Adımın bittiğini nasıl anlayacağı (küçük bir kontrol)

En sonda:
- "Dikkat et" başlığı altında, yeni başlayanların bu projede en sık unuttuğu
  2-3 şeyi yaz (örneğin hata kontrolü, veri doğrulama, yedek alma).
- Öğrenciyi ilk adıma başlamaya teşvik eden tek cümlelik bir motivasyon yaz.

KESİN KURALLAR:
- ASLA hazır kod, kod parçası ya da kod bloğu verme. Tek satır bile olmasın.
- Bunun yerine neyin, neden yapılacağını açıkla ve hangi konuyu araştırması
  gerektiğini söyle.
- Öğrenci tecrübesiz olabilir: sade ve anlaşılır Türkçe kullan, teknik terimleri
  kısaca açıkla.
- Öğrencinin anlatımı çok kısa ya da belirsizse, yine de makul bir yol haritası
  çıkar ve en başta hangi varsayımları yaptığını bir cümleyle belirt.

CEVAP BİÇİMİ (web sayfası bu düzene göre gösteriyor, bu yüzden aynen uy):
- En başta 1-2 cümlelik kısa bir giriş paragrafı yaz. Başlık koyma.
- Her adım şu şekilde başlasın:  ### Adım 1: Kısa başlık
- Adım başlığının altına tam olarak şu üç maddeyi yaz:
  - **Ne yapılacak:** ...
  - **Öğrenilecek konular:** ...
  - **Nasıl anlarsın:** ...
- Adımlardan sonra şu başlığı koy:  ## Dikkat et
  ve altına 2-3 madde yaz.
- En son satıra tek cümlelik motivasyonu yaz.
- Başka başlık, çizgi (---) ya da tablo kullanma.
"""


# 8. hafta: Öğrenci bir adımda takılınca kullanılan talimat.
# İpucu 3 seviyelidir: her seviyede biraz daha açık konuşulur ama ASLA kod verilmez.
IPUCU_TALIMATI = """
Sen "KodKoç" adında, yazılıma yeni başlayan öğrencilere yardım eden bir koçsun.
Öğrenci, yol haritasındaki bir adımda takıldı ve senden ipucu istiyor.

KESİN KURALLAR:
- ASLA hazır kod, kod parçası ya da kod bloğu verme. Tek satır bile olmasın.
- Öğrenci kendi kodunu yapıştırsa bile düzeltilmiş kodu geri verme; hatanın
  nerede olabileceğini ve neye bakması gerektiğini sözle anlat.
- Sade, sıcak ve cesaret verici bir Türkçe kullan.
- Daha önce verilen ipuçlarını tekrar etme, bir adım ileri götür.

İPUCU SEVİYELERİ (mesajda hangi seviye istendiği yazar):
- Seviye 1: Çözümü söyleme. Doğru yöne bakmasını sağlayacak 1-2 soru sor
  ya da problemi nasıl düşünebileceğine dair genel bir fikir ver.
- Seviye 2: Daha somut ol. Kullanması gereken kavramın, yapının ya da
  fonksiyonun adını söyle ve neden işine yarayacağını açıkla.
- Seviye 3: Sözlü bir çözüm planı ver (madde madde, kodsuz), araştırması
  gereken anahtar kelimeleri ve internette aratabileceği bir arama cümlesi öner.

CEVAP BİÇİMİ:
- En fazla 120 kelime. Başlık kullanma. Gerekirse kısa maddeler kullan.
"""


# 8. hafta: Öğrenci kendi kodunu gönderip geri bildirim isteyince kullanılan talimat.
KOD_INCELEME_TALIMATI = """
Sen "KodKoç" adında, yazılıma yeni başlayan öğrencilere yardım eden bir koçsun.
Öğrenci, yol haritasındaki bir adım için KENDİ yazdığı kodu gönderdi ve geri bildirim istiyor.
Kodun her satırının başında satır numarası var (ör. "3: ...").

KESİN KURALLAR:
- ASLA düzeltilmiş kod, kod parçası ya da kod bloğu yazma. Öğrencinin satırlarını
  düzeltilmiş haliyle tekrar yazma. Tek satır bile olmasın.
- Bir sorun görürsen satır numarasını söyle, ne olduğunu sözle anlat ve öğrencinin
  kendisinin bulması için bir soru sor.
- En fazla 3 noktaya dikkat çek; en önemlisinden başla. Küçük stil konularını,
  önemli hatalar varken söyleme.
- Önce gerçekten iyi olan bir şeyi söyle. Sade, sıcak ve cesaret verici Türkçe kullan.
- Kod bu adımla ilgisizse bunu nazikçe söyle.

CEVAP BİÇİMİ (aynen uy):
**İyi gidenler:** 1-2 cümle.

**Bakman gerekenler:**
- **Satır N:** ne fark ettiğin + öğrencinin kendine sorması gereken soru
(en fazla 3 madde; sorun yoksa "Belirgin bir sorun görmedim." yaz)

**Sıradaki adım:** Tek cümle.
"""


# 8. hafta: "Ne yapacağımı bilmiyorum" diyen öğrenciye proje fikri önerirken kullanılan talimat.
FIKIR_TALIMATI = """
Sen "KodKoç" adında, yazılıma yeni başlayan öğrencilere yardım eden bir koçsun.
Öğrenci ne tür bir proje yapacağını bilmiyor. Ona tam olarak 3 proje fikri öner.

KURALLAR:
- Fikirler öğrencinin bildiklerine uygun, küçük ve 1-2 haftada bitirilebilir olsun.
- Öğrencinin ilgi alanıyla bağlantılı olsun; ilgi alanı yoksa günlük hayattan seç.
- Üç fikir birbirinden farklı olsun ve zorluk olarak kolaydan zora sıralansın.
- Kod yazma, teknik detaya girme. Sade Türkçe kullan.

CEVAP BİÇİMİ: Sadece JSON. Başka hiçbir şey yazma.
[{"baslik": "en fazla 6 kelime", "aciklama": "Programın ne yapacağını anlatan 1-2 cümle"}, ...]
"""


# 8. hafta: "Koça soru sor" - öğrencinin bir adımla ilgili serbest sorularına cevap.
# İpucundan farkı: ipucu "takıldım, çözüme yaklaştır" demektir; soru ise
# "bu kavram ne, neden böyle?" gibi bir anlama sorusudur.
SORU_TALIMATI = """
Sen "KodKoç" adında, yazılıma yeni başlayan öğrencilere yardım eden bir koçsun.
Öğrenci, yol haritasındaki bir adımla ilgili sana bir soru soruyor.

KESİN KURALLAR:
- ASLA hazır kod, kod parçası ya da kod bloğu verme. Tek satır bile olmasın.
- Öğrenci açıkça kod isterse ("kodunu yazar mısın", "çözümü ver") nazikçe reddet,
  nedenini tek cümleyle söyle ve onun yerine nasıl düşünmesi gerektiğini anlat.
- Kavramları günlük hayattan bir benzetmeyle anlat (ör. liste = alışveriş listesi).
- Bir kavramın adını söyleyebilirsin (ör. `append`, `for`), ama nasıl yazılacağını gösterme.
- Soru bu adımla ya da yazılımla ilgisizse kısaca söyle ve adıma geri döndür.
- Önceki konuşmayı dikkate al, aynı şeyi tekrar etme.
- Sade, sıcak ve cesaret verici Türkçe kullan.

CEVAP BİÇİMİ:
- En fazla 150 kelime. Başlık kullanma. Gerekirse kısa maddeler kullan.
- Sonunda öğrencinin kendini sınaması için tek bir küçük soru sor.
"""


# ---------------------------------------------------------------------------
# 3) YARDIMCI FONKSİYONLAR
# ---------------------------------------------------------------------------

def cok_satirli_girdi_al(soru):
    """Kullanıcıdan birden fazla satır metin alır. Boş satır girilince biter."""
    print(soru)
    print("(Bitirmek için boş bir satırda Enter'a basın.)")
    satirlar = []
    while True:
        satir = input("> ")
        if satir.strip() == "":
            break
        satirlar.append(satir)
    return "\n".join(satirlar)


def kod_bloklarini_temizle(metin):
    """
    Çift güvence (8. hafta): Talimata rağmen yapay zekâ ``` ile başlayan bir kod
    bloğu yazarsa, o bloğu öğrenciye göstermeden önce siler.
    re.DOTALL: "." işaretinin satır sonlarını da kapsamasını sağlar.
    """
    return re.sub(r"```.*?```",
                  "*(Burada bir kod parçası vardı, KodKoç kod vermez. Bunu sen yazmayı dene!)*",
                  metin, flags=re.DOTALL)


# Satır içi kodda (`...`) izin verilenler: kavram adları, kod satırı değil.
#   input   input()   gorevler.append   (isim, nokta, sonunda boş parantez)
IZINLI_ISIM = re.compile(r"[\w.]+(\(\))?")
#   ==   +=   !=   (1-3 karakterlik operatörler)
IZINLI_OPERATOR = re.compile(r"[^\w\s]{1,3}")


def satir_ici_kodu_temizle(metin):
    """
    Çift güvencenin ikinci parçası: Yapay zekâ cümle içine `...` ile tek satırlık
    bir çözüm yazarsa (ör. `gorevler.pop(int(no) - 1)`) onu siler.

    Kavramdan bahsetmek serbest: `input()`, `while`, `"3"`, `==` kalır.
    Kod satırı gibi görünen her şey (boşluk, = ya da içi dolu parantez içeren) silinir.
    """
    def kontrol(eslesme):
        icerik = eslesme.group(1).strip()
        kisa_deger = len(icerik) <= 12 and not any(k in icerik for k in " =()")
        if IZINLI_ISIM.fullmatch(icerik) or IZINLI_OPERATOR.fullmatch(icerik) or kisa_deger:
            return eslesme.group(0)                 # Olduğu gibi bırak
        return "*(kod parçası çıkarıldı)*"

    # `[^`\n]+` : ters tırnaklar arasındaki, satır sonu içermeyen metin
    return re.sub(r"`([^`\n]+)`", kontrol, metin)


def gecici_hata_mi(hata):
    """
    Hata, "biraz sonra tekrar dene" türünden mi?
    429 = çok fazla istek, 500/503 = Google tarafında yoğunluk ya da geçici sorun.
    """
    return getattr(hata, "code", None) in (429, 500, 503)


def yapay_zekaya_sor(istemci, mesaj, talimat, sicaklik=0.4, deneme_sayisi=3, json_cevap=False):
    """
    Mesajı yapay zekâya gönderir ve cevap metnini döndürür.
    - Bir model çalışmazsa listedeki sıradaki modeli dener.
    - Bütün modeller geçici olarak meşgulse biraz bekleyip baştan dener
      (2 sn, sonra 4 sn bekler). Kalıcı hatada (ör. yanlış API anahtarı) beklemez.
    - json_cevap=True: Yapay zekâdan cevabı düz metin değil JSON olarak ister.
    """
    son_hata = None
    for deneme in range(deneme_sayisi):
        for model in MODELLER:            # Bir model çalışmazsa sıradakini dener
            try:
                cevap = istemci.models.generate_content(
                    model=model,
                    contents=mesaj,
                    config=types.GenerateContentConfig(
                        system_instruction=talimat,
                        temperature=sicaklik,   # Düşük değer = daha tutarlı cevaplar
                        # JSON istendiyse modelin cevabı geçerli JSON olmak zorunda olur
                        response_mime_type="application/json" if json_cevap else None,
                    ),
                )
                # Önce ``` bloklarını, sonra satır içi kod parçalarını temizle
                return satir_ici_kodu_temizle(kod_bloklarini_temizle(cevap.text))
            except Exception as hata:
                son_hata = hata
        # Buraya geldiysek bütün modeller hata verdi
        if not gecici_hata_mi(son_hata) or deneme == deneme_sayisi - 1:
            break
        time.sleep(2 * (deneme + 1))
    raise son_hata


def yol_haritasi_iste(istemci, proje, bilgi):
    """Projeyi yapay zekâya gönderir ve gelen yol haritasını döndürür."""
    mesaj = f"Öğrencinin projesi:\n{proje}\n\nÖğrencinin bildikleri:\n{bilgi or 'Belirtilmedi.'}"
    return yapay_zekaya_sor(istemci, mesaj, TALIMAT)


def bildikleri_satiri(bilgi):
    """
    Öğrencinin yol haritasını çıkarırken yazdığı "bildiği diller/teknolojiler".
    Koç (ipucu, soru, inceleme) bunu bilirse anlatımı öğrencinin seviyesine göre ayarlar:
    Python'a yeni başlayana başka, JavaScript bilene başka benzetme yapar.
    """
    return f"Öğrencinin bildikleri:\n{bilgi or 'Belirtilmedi (yeni başlıyor olabilir).'}\n\n"


def ipucu_iste(istemci, proje, adim_basligi, adim_icerigi, onceki_ipuclari, soru, seviye, bilgi=""):
    """
    Öğrencinin takıldığı adım için istenen seviyede (1, 2 ya da 3) ipucu döndürür.
    onceki_ipuclari: daha önce bu adım için verilmiş ipucu metinlerinin listesi.
    bilgi: öğrencinin bildikleri (anlatımı seviyesine göre ayarlamak için).
    """
    onceki = "\n\n".join(f"{i}. ipucu: {metin}" for i, metin in enumerate(onceki_ipuclari, start=1))
    mesaj = (
        f"Öğrencinin projesi:\n{proje}\n\n"
        + bildikleri_satiri(bilgi) +
        f"Takıldığı adım: {adim_basligi}\n{adim_icerigi}\n\n"
        f"Daha önce verilen ipuçları:\n{onceki or 'Yok.'}\n\n"
        f"Öğrencinin anlattığı sorun:\n{soru or 'Öğrenci bir şey yazmadı, sadece takıldığını söyledi.'}\n\n"
        f"İstenen ipucu seviyesi: {seviye}"
    )
    return yapay_zekaya_sor(istemci, mesaj, IPUCU_TALIMATI, sicaklik=0.5)


def proje_fikirleri_iste(istemci, bilgi, ilgi):
    """
    Öğrenciye 3 proje fikri önerir. [{"baslik": ..., "aciklama": ...}, ...] döndürür.
    Yapay zekâ beklenen biçimde cevap vermezse ValueError fırlatır.
    """
    mesaj = (f"Öğrencinin bildikleri: {bilgi or 'Belirtilmedi (tamamen yeni başlıyor olabilir).'}\n"
             f"Öğrencinin ilgi alanı: {ilgi or 'Belirtilmedi.'}")
    metin = yapay_zekaya_sor(istemci, mesaj, FIKIR_TALIMATI, sicaklik=0.8, json_cevap=True)

    # json.loads: JSON metnini Python listesine/sözlüğüne çevirir. Bozuksa ValueError verir.
    veri = json.loads(metin)

    # Dışarıdan (yapay zekâdan) gelen veriye körü körüne güvenme: biçimini kontrol et
    if not isinstance(veri, list):
        raise ValueError("Yapay zekâ liste döndürmedi.")
    fikirler = []
    for oge in veri[:3]:
        if isinstance(oge, dict) and isinstance(oge.get("baslik"), str) and isinstance(oge.get("aciklama"), str):
            fikirler.append({"baslik": oge["baslik"].strip()[:80],
                             "aciklama": oge["aciklama"].strip()[:400]})
    if not fikirler:
        raise ValueError("Yapay zekâ geçerli bir fikir döndürmedi.")
    return fikirler


def satir_numarala(kod):
    """Kodun her satırının başına numara ekler: "1: ...", "2: ...". Yapay zekâ satır söyleyebilsin diye."""
    return "\n".join(f"{i}: {satir}" for i, satir in enumerate(kod.splitlines(), start=1))


def kod_incele(istemci, proje, adim_basligi, adim_icerigi, kod, aciklama, bilgi=""):
    """Öğrencinin kodu için, düzeltilmiş kod VERMEDEN geri bildirim döndürür."""
    mesaj = (
        f"Öğrencinin projesi:\n{proje}\n\n"
        + bildikleri_satiri(bilgi) +
        f"Üzerinde çalıştığı adım: {adim_basligi}\n{adim_icerigi}\n\n"
        f"Öğrencinin ne yapmaya çalıştığı:\n{aciklama or 'Belirtmedi.'}\n\n"
        f"Öğrencinin kodu (satır numaralı):\n{satir_numarala(kod)}"
    )
    return yapay_zekaya_sor(istemci, mesaj, KOD_INCELEME_TALIMATI, sicaklik=0.3)


def soru_sor(istemci, proje, adim_basligi, adim_icerigi, onceki_konusma, soru, bilgi=""):
    """
    "Koça soru sor": öğrencinin serbest sorusuna kod vermeden cevap döndürür.
    onceki_konusma: bu adımda daha önce sorulan [(soru, cevap), ...] listesi.
    Yapay zekânın "hafızası" yoktur; konuşmayı hatırlaması için eski soru-cevapları
    her seferinde mesajın içine biz koyarız.
    """
    gecmis = "\n\n".join(f"Öğrenci: {s}\nKodKoç: {c}" for s, c in onceki_konusma)
    mesaj = (
        f"Öğrencinin projesi:\n{proje}\n\n"
        + bildikleri_satiri(bilgi) +
        f"Üzerinde çalıştığı adım: {adim_basligi}\n{adim_icerigi}\n\n"
        f"Bu adımda daha önceki konuşmanız:\n{gecmis or 'Yok, bu ilk soru.'}\n\n"
        f"Öğrencinin yeni sorusu:\n{soru}"
    )
    return yapay_zekaya_sor(istemci, mesaj, SORU_TALIMATI, sicaklik=0.5)


def kaydet(proje, yol_haritasi):
    """Yol haritasını tarihli bir dosyaya kaydeder ve dosya yolunu döndürür."""
    os.makedirs(KAYIT_KLASORU, exist_ok=True)
    zaman = datetime.now().strftime("%Y-%m-%d_%H-%M")
    dosya_yolu = os.path.join(KAYIT_KLASORU, f"yol_haritasi_{zaman}.md")
    with open(dosya_yolu, "w", encoding="utf-8") as dosya:
        dosya.write("# KodKoç Yol Haritası\n\n")
        dosya.write(f"## Proje\n\n{proje}\n\n")
        dosya.write(f"## Yol Haritası\n\n{yol_haritasi}\n")
    return dosya_yolu


# ---------------------------------------------------------------------------
# 4) ANA PROGRAM
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  KodKoç - Kodu yazan değil, yazmayı öğreten koç")
    print("=" * 60)

    # API anahtarı yoksa (ilk açılış) kullanıcıdan iste ve .env dosyasına kaydet
    anahtar = API_ANAHTARI
    if not anahtar:
        print("\nİlk kurulum: Google AI Studio'dan aldığın API anahtarını yapıştır.")
        anahtar = input("API anahtarı: ").strip()
        if not anahtar:
            print("Anahtar girilmedi. Program kapatılıyor.")
            return
        # set_key: .env'deki diğer ayarları silmeden sadece bu satırı ekler (8. hafta düzeltmesi)
        set_key(".env", "GEMINI_API_KEY", anahtar)
        print("Anahtar '.env' dosyasına kaydedildi, bir dahaki sefere sorulmayacak.")

    istemci = genai.Client(api_key=anahtar)

    proje = cok_satirli_girdi_al("\nNe yapmak istiyorsun? Projeni anlat:")
    if not proje:
        print("Proje anlatımı boş olamaz. Program kapatılıyor.")
        return

    bilgi = input("\nHangi dilleri/teknolojileri biliyorsun? (boş bırakabilirsin)\n> ")

    print("\nKodKoç yol haritanı hazırlıyor, lütfen bekle...\n")
    try:
        yol_haritasi = yol_haritasi_iste(istemci, proje, bilgi)
    except Exception as hata:
        print("Yapay zekâya bağlanırken bir sorun oluştu:")
        print(hata)
        print("İnternet bağlantını ve API anahtarını kontrol et.")
        return

    print("-" * 60)
    print(yol_haritasi)
    print("-" * 60)

    dosya_yolu = kaydet(proje, yol_haritasi)
    print(f"\nYol haritan kaydedildi: {dosya_yolu}")

    # 8. hafta: İstenirse terminalde çıkarılan yol haritası da web sürümündeki
    # hesaba eklenir; böylece "Geçmiş" sayfasında görünür ve adımları işaretlenebilir.
    hesaba_ekle(proje, bilgi, yol_haritasi, dosya_yolu)
    print("İlk adımdan başla, kolay gelsin!")


def hesaba_ekle(proje, bilgi, yol_haritasi, dosya_yolu):
    """Kullanıcı adı ve şifre sorar; doğruysa yol haritasını o hesaba kaydeder."""
    import veritabani
    from getpass import getpass          # Şifreyi yazarken ekranda göstermez

    veritabani.hazirla()
    print("\nBu yol haritasını web sürümündeki hesabına eklemek ister misin?")
    kullanici_adi = input("Kullanıcı adın (eklemek istemiyorsan boş bırak): ").strip()
    if not kullanici_adi:
        return

    for kalan_hak in (2, 1, 0):              # 3 deneme hakkı
        sifre = getpass("Şifren (yazarken görünmez): ")
        kullanici = veritabani.kullanici_dogrula(kullanici_adi, sifre)
        if kullanici:
            veritabani.yol_haritasi_ekle(proje, bilgi, yol_haritasi, dosya_yolu,
                                         kullanici_id=kullanici["id"])
            print("Eklendi! Web sürümündeki 'Geçmiş' sayfasından adımlarını işaretleyebilirsin.")
            return
        if kalan_hak:
            print(f"Kullanıcı adı ya da şifre yanlış. {kalan_hak} hakkın kaldı.")
    print("Hesaba eklenemedi; yol haritan yine de dosya olarak kaydedildi.")


if __name__ == "__main__":
    main()
