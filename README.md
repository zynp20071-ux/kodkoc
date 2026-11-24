# KodKoç

Yazılıma yeni başlayanlara **kodu yazmadan** yol gösteren yapay zekâ koçu.

## Sürümler

### 8. hafta – Veritabanı ve ilerleme takibi
- Yol haritaları SQLite veritabanına (`kodkoc.db`) kaydediliyor: `yol_haritalari` ve `adimlar` tabloları.
- Her adım "Tamamladım" düğmesiyle işaretlenebiliyor (geri de alınabiliyor), üstte ilerleme çubuğu görünüyor.
- "Geçmiş" sayfası eski yol haritalarını, ilerleme durumlarıyla birlikte listeliyor.
- Terminal sürümünde çıkarılan yol haritaları da veritabanına ekleniyor.
- **Takıldım, ipucu ver:** Her adım için 3 kademeli ipucu (soruyla yönlendirme → kavramın adı → kodsuz çözüm planı). İpuçları `ipuclari` tablosunda saklanıyor.
- **Kod filtresi:** Yapay zekâ kurala rağmen kod bloğu yazarsa öğrenciye gösterilmeden siliniyor.
- **Otomatik tekrar deneme:** Yapay zekâ yoğunsa (429/500/503) program bekleyip yeniden deniyor; olmazsa anlaşılır bir mesaj gösteriyor.
- **Adıma not ekleme:** Öğrenci her adıma "ne öğrendim, nasıl çözdüm" notu bırakabiliyor.
- **Yol haritası silme** (adımları ve ipuçlarıyla birlikte).
- **Geçmişte arama ve filtre** (devam edenler / bitenler) ve özet sayılar.
- Eski veritabanı dosyaları otomatik olarak yeni yapıya yükseltiliyor (göç / migration).
- **Kullanıcı girişi:** Kayıt / giriş / çıkış. Şifreler hash'lenerek saklanıyor. Herkes sadece kendi yol haritalarını görüyor; başkasınınkini adresten açmaya çalışan "bulunamadı" sayfası görüyor.
- Giriş özelliğinden önce kaydedilmiş yol haritaları, ilk kayıt olan kullanıcının hesabına aktarılıyor.
- Terminal sürümü, istenirse yol haritasını kullanıcı adı ve şifreyle hesaba ekliyor.
- Oturum için gereken gizli anahtar ilk açılışta rastgele üretilip `.env` dosyasına yazılıyor (koda yazılmıyor).
- **Öğretmen paneli:** Kayıtta "Öğrenciyim / Öğretmenim" seçiliyor. Öğretmen sınıf açıp 6 karakterlik katılım kodu alıyor; öğrenci "Sınıfım" sayfasından bu kodla katılıyor.
  - Sınıf sayfasında her öğrencinin yol haritası sayısı, ilerlemesi, ipucu sayısı ve son etkinliği tablo halinde görünüyor.
  - "Yardıma ihtiyacı olabilir" listesi: bitmemiş ve en az 2 ipucu alınmış adımlar.
  - Öğretmen öğrencinin yol haritasını, ipuçlarını ve notlarını **salt okunur** görebiliyor; hiçbir şeyi değiştiremiyor.
  - Gizlilik: Öğretmen sadece kendi sınıfına kendi isteğiyle katılmış öğrencileri görebiliyor. Öğrenci sınıftan ayrılınca erişim kapanıyor.
- **GitHub commit takibi:** Her yol haritasına herkese açık bir GitHub deposu bağlanabiliyor.
  - KodKoç son commit'leri GitHub API'sinden çekip veritabanına kaydediyor ("Yenile" ile güncelleniyor, iki yenileme arası en az 30 sn).
  - Commit mesajında **"Adım 3"** gibi bir ifade varsa commit o adımın altında görünüyor. Commit atılmış ama işaretlenmemiş adımda hatırlatma çıkıyor.
  - Öğretmen commit'leri salt okunur görüyor; sınıf tablosunda "Commit" sütunu var.
  - Anahtar gerekmez (saatte 60 istek). İstenirse `.env` dosyasına `GITHUB_TOKEN=...` eklenerek sınır 5000'e çıkarılabilir.
- **Öğretmen yorumu:** Öğretmen, öğrencinin bir adımına yorum bırakabiliyor; öğrenci yorumu adımın altında, geçmiş listesinde de "N öğretmen yorumu" olarak görüyor. Öğretmen sadece kendi yorumunu silebiliyor.
- **CSRF koruması:** Her formda gizli bir güvenlik jetonu var; jetonsuz ya da yanlış jetonlu istekler reddediliyor. Oturum çerezi `HttpOnly` ve `SameSite=Lax`.
- **Yeni yorum bildirimi:** Öğretmen yorum yazınca öğrencinin menüsünde "Geçmiş" yanında sayı rozeti çıkıyor; yeni yorumlar "Yeni" etiketiyle görünüyor, sayfa açılınca okundu sayılıyor.
- **Excel'e aktarma:** Öğretmen sınıfın ilerleme tablosunu CSV olarak indirebiliyor (Türkçe karakterler Excel'de bozulmadan açılır).
- **Kodumu incelet:** Öğrenci bir adım için yazdığı kodu gönderiyor; KodKoç düzeltilmiş kod **vermeden** iyi giden yanları, satır numarasıyla en fazla 3 dikkat noktasını (her biri bir soruyla) ve sıradaki adımı yazıyor. Her adımda 5 hak var; öğretmen gönderilen kodu ve geri bildirimi görebiliyor.
- **Satır içi kod filtresi:** Yapay zekâ cümle içine `` `...` `` ile kod satırı yazarsa siliniyor; `input()`, `"3"`, `==` gibi kavram adları kalıyor.
- **Koyu tema:** Bilgisayar koyu moddaysa otomatik; üstteki düğmeyle elle de seçilebiliyor ve tarayıcıda hatırlanıyor. Bütün renkler CSS değişkenlerinde; kontrastlar erişilebilirlik standardını (WCAG 4,5) geçiyor.
- **Kaldığın yerden devam et:** Ana sayfada bitmemiş en son yol haritasının sıradaki adımı gösteriliyor; tek tıkla o adıma gidiliyor.
- **Proje fikri al:** "Ne yapacağımı bilmiyorum" diyen öğrenci ilgi alanını ve bildiklerini yazıyor, KodKoç seviyesine uygun, kolaydan zora 3 küçük proje fikri öneriyor; seçilen fikir proje formunu dolduruyor.
- **Adımları düzenleme:** Öğrenci adımın başlığını ve açıklamasını değiştirebiliyor, adım silebiliyor (numaralar yeniden sıralanıyor, son adım silinemiyor), sona kendi adımını ekleyebiliyor ("Senin eklediğin" etiketiyle; öğretmen de görüyor).
- **Rozetler:** 8 rozet (İlk Adım, Kendi Başına, Pes Etmeyen, Kod Okuyucu, Meraklı, Not Defteri, İlk Commit, Bitiş Çizgisi). Geçmiş sayfasında görünüyor, kazanılmamışlar ilerlemeyle birlikte gri. Öğretmen öğrencinin rozetlerini görüyor. Rozetler saklanmıyor, her seferinde verilerden hesaplanıyor.
- **Koça soru sor:** Öğrenci her adımda anlamadığı bir kavramı serbestçe sorabiliyor (adım başına 10 soru). KodKoç benzetmelerle anlatıyor, kod yazmıyor, kod istenirse nazikçe reddediyor. Sorular sohbet balonu olarak görünüyor; son 3 soru-cevap yapay zekâya "hafıza" olarak gönderiliyor. Öğretmen de konuşmayı görüyor.
- **Profil sayfası:** Menüdeki kullanıcı adına tıklanınca açılıyor. Şifre değiştirme (eski şifre sorulur), çalışma serisi (üst üste kaç gün çalışıldı, en uzun seri) ve son 4 haftanın etkinlik takvimi.
- **Sınıf duyuruları:** Öğretmen sınıf sayfasından duyuru yazıyor (ör. "Cuma'ya kadar 3. adımı bitirin"). Öğrenciler yeni duyuruları ana sayfanın en üstünde görüyor, menüde "Sınıfım" yanında sayı çıkıyor; "Sınıfım" sayfası açılınca okundu sayılıyor. Sınıftan ayrılan öğrenci duyuruları görmüyor.
- **Sınıf istatistikleri:** Öğretmenin sınıf sayfasında ortalama ilerleme, son 7 günde çalışan öğrenci sayısı ve henüz başlamayanlar; ayrıca iki grafik: ilerleme dağılımı (kaç öğrenci %0-25, %26-50...) ve son 14 günde her gün kaç farklı öğrencinin çalıştığı. Grafikler kütüphanesiz, sadece HTML + CSS ile çiziliyor.
- **Yazdır / PDF:** Yol haritası sayfasındaki düğme tarayıcının yazdırma penceresini açıyor ("PDF olarak kaydet" de oradan). Kâğıtta menü ve düğmeler gizleniyor, öğrencinin notları ve biten adımlar görünüyor; koyu temada bile beyaz kâğıda basılıyor.
- **Otomatik testler:** `tests/` klasöründe 183 test (pytest). `test_calistir.bat` ile çalışır. Testler geçici bir veritabanı kullanır, internete çıkmaz.

## Testler

| Dosya | Neyi test ediyor |
|---|---|
| `tests/conftest.py` | Ortak hazırlık: geçici veritabanı, sahte yapay zekâ, CSRF jetonlu test istemcisi |
| `tests/test_veritabani.py` | Cevabı adımlara bölme, eski veritabanını yükseltme (göç) |
| `tests/test_giris.py` | Kayıt kuralları, giriş/çıkış, herkesin sadece kendi verisini görmesi |
| `tests/test_yol_haritasi.py` | Yol haritası, işaretleme, ilerleme, ipucu, not, silme, geçmiş |
| `tests/test_ogretmen.py` | Sınıflar, katılım kodu, ilerleme tablosu, gizlilik, yorumlar |
| `tests/test_github.py` | Depo adresi, "Adım N", GitHub hataları, commit eşleme |
| `tests/test_guvenlik.py` | CSRF, HTML kaçışı (XSS), SQL enjeksiyonu, `.env` kaydı |
| `tests/test_kodkoc.py` | Kod filtresi, yapay zekâ meşgulken tekrar deneme, terminal sürümü |
| `tests/test_bildirim_ve_disa_aktarma.py` | Yeni yorum bildirimi, CSV dışa aktarma |
| `tests/test_kod_inceleme.py` | Kodumu incelet: geri bildirim, hak sınırı, güvenlik, öğretmen görünümü |
| `tests/test_tema.py` | Koyu tema: renkler değişkende mi, koyu tema her rengi tanımlıyor mu |
| `tests/test_ana_sayfa.py` | Kaldığın yerden devam et, proje fikri (JSON doğrulama) |
| `tests/test_adim_duzenleme.py` | Adım ekleme, düzenleme, silme, numaraların yeniden sıralanması |
| `tests/test_rozetler.py` | Hangi davranış hangi rozeti kazandırıyor |
| `tests/test_koca_soru.py` | Koça soru sor: kayıt, hak sınırı, hafıza, güvenlik, öğretmen görünümü |
| `tests/test_profil.py` | Şifre değiştirme, çalışma serisi, etkinlik takvimi |
| `tests/test_duyurular.py` | Sınıf duyuruları (okundu, gizlilik, yetki) ve yazdırma görünümü |
| `tests/test_sinif_istatistik.py` | Sınıf istatistikleri: ortalama, dağılım, 14 günlük grafik, sadece sınıf üyeleri |

Çalıştırmak için `test_calistir.bat` ya da `python -m pytest -v`.

### 7. hafta – Web arayüzü
- KodKoç artık tarayıcıda çalışıyor (Flask).
- Öğrenci projesini bir form üzerinden anlatıyor.
- Yol haritası düzgün biçimde gösteriliyor: her adım ayrı bir kutuda, "Dikkat et" bölümü ayrı renkte.
- İlk açılışta API anahtarı sayfadan girilip `.env` dosyasına kaydediliyor.

### 6. hafta – Terminal sürümü
- Öğrenci projesini anlatır, Gemini yapay zekâsı 5–8 adımlık yol haritası çıkarır.
- Yapay zekâya hazır kod vermemesi talimatı verilmiştir.
- Yol haritası `yol_haritalari` klasörüne kaydedilir.

## Dosyalar

| Dosya | Görevi |
|---|---|
| `kodkoc.py` | Yapay zekâ talimatı, yapay zekâya bağlanma ve kaydetme (6. hafta; terminalden de çalışır) |
| `app.py` | Flask web uygulaması: sayfalar (route'lar) burada |
| `veritabani.py` | SQLite veritabanı: tabloları oluşturma, kaydetme, okuma, güncelleme (8. hafta) |
| `github_takip.py` | GitHub API'sinden commit okuma, depo adresini ve "Adım N" ifadesini anlama |
| `templates/taban.html` | Bütün sayfaların ortak iskeleti (logo, menü) |
| `templates/index.html` | Ana sayfa: proje formu |
| `templates/yol_haritasi.html` | Tek yol haritası: adımlar ve ilerleme çubuğu |
| `templates/gecmis.html` | Geçmiş yol haritalarının listesi |
| `templates/giris.html`, `templates/kayit.html` | Giriş ve kayıt sayfaları |
| `templates/bulunamadi.html` | "Sayfa bulunamadı" (404) sayfası |
| `templates/sinifim.html` | Öğrenci: sınıfa katılma |
| `templates/ogretmen_paneli.html` | Öğretmen: sınıf listesi, sınıf açma |
| `templates/sinif_detay.html` | Öğretmen: sınıfın ilerleme tablosu ve takılan öğrenciler |
| `templates/ogrenci_detay.html` | Öğretmen: bir öğrencinin yol haritaları |
| `templates/gecersiz_istek.html` | Güvenlik jetonu tutmadığında gösterilen sayfa (400) |
| `templates/_rozetler.html` | Rozet listesi (Geçmiş ve öğretmenin öğrenci sayfasına `include` ile eklenir) |
| `templates/profil.html` | Profil: çalışma serisi, etkinlik takvimi, şifre değiştirme |
| `test_calistir.bat`, `pytest.ini` | Testleri tek tıkla çalıştırma |
| `templates/mesajlar.html`, `templates/sohbet.html` | Sohbet listesi ve sohbet ekranı (sınıf sohbeti + özel mesaj) |
| `templates/kullanici.html` | Aynı sınıftakilerin görebildiği kullanıcı profili |
| `templates/kod_dene.html`, `static/python_isci.js` | Tarayıcıda Python çalıştırma (Pyodide, Web Worker) |
| `templates/odevler.html`, `templates/odev.html`, `templates/odev_teslimleri.html` | Ödevler, teslim ve puanlama |
| `templates/grup.html` | Grup sayfası: görev panosu; sohbet grubunda üyeler ve yönetim |
| `templates/grup_yeni.html` | Sohbet grubu kurma (sınıf arkadaşlarıyla) |
| `static/mesaj_paneli.js` | Her sayfanın sağ altındaki mesaj paneli (sayfadan çıkmadan yazışma) |
| `static/anket.js` | Sohbetteki anket kartı: seçenekler, oy verme, sonuç çubukları |
| `templates/takvim.html`, `templates/sablonlar.html`, `templates/sablon.html` | Takvim ve öğretmenin proje şablonları |
| `static/manifest.webmanifest`, `static/sw.js`, `static/ikon-*.png` | Telefona yüklenebilir uygulama (PWA) |
| `yedek_al.py` | Veritabanı yedeği alma ve geri yükleme |
| `templates/gizlilik.html` | Hangi verilerin saklandığı, kimin neyi gördüğü |
| `templates/notlarim.html` | Öğrenci: bütün adım notları, arama ve .md olarak indirme |
| `demo_veri.py` | Sunum için örnek öğretmen, sınıf ve öğrenciler (`olustur` / `sil`) |
| `SUNUM_NOTLARI.md` | Sunum için demo akışı, özelliklerin kodda yeri, olası sorular |
| `CALISMA_SORULARI.md` | Kendi kendine çalışma: 25 soru (cevaplar gizli) ve 3 alıştırma |
| `static/style.css` | Sayfanın tasarımı |

## Kullanılan teknolojiler

- Python 3, Flask
- SQLite (`sqlite3`, Python ile birlikte gelir)
- Google Gemini API (`google-genai`)
- `markdown` (yapay zekâ cevabını HTML'e çevirmek için)
- `python-dotenv` (API anahtarını koddan ayrı tutmak için)

## Çalıştırma

Windows'ta `baslat.bat` dosyasına çift tıklayın. Tarayıcıda http://127.0.0.1:5000 açılır.
Eski terminal sürümü için `terminal_surumu.bat`.

## Canlıya alma (sunucuda çalıştırma)

KodKoç tek bir sunucuda, herkesin ortak kullandığı bir site olarak da çalışabilir.
Sunucunun ayarlarına (Environment Variables) şunları girin. Tam liste ve açıklamalar `.env.example` dosyasında.

| Ayar | Ne işe yarar |
|---|---|
| `KODKOC_CANLI=1` | Canlı modu açar |
| `GEMINI_API_KEY` | Herkesin ortak kullandığı Gemini anahtarı (siteden değiştirilemez) |
| `FLASK_SECRET_KEY` | Oturum anahtarı. **Zorunlu**, yoksa program başlamaz |
| `OGRETMEN_KODU` | Öğretmen kaydı için davet kodu. Boşsa kimse öğretmen hesabı açamaz |
| `GUNLUK_YZ_SINIRI` | Kişi başı günlük yapay zekâ isteği (varsayılan 40) |
| `DATABASE_URL` | PostgreSQL adresi. Verilirse SQLite yerine PostgreSQL kullanılır |
| `VERITABANI_YOLU` | SQLite kullanılıyorsa dosyanın yeri (sunucunun kalıcı diski) |
| `TZ=Europe/Istanbul` | Tarihler Türkiye saatiyle yazılsın |

Başlatma komutu: `gunicorn app:app --workers 2 --timeout 120` (`Procfile` içinde hazır).

Canlı modda ayrıca: oturum çerezi sadece HTTPS'te gönderilir, yapay zekâ hatalarının ayrıntısı
ziyaretçiye gösterilmez, yol haritaları `.md` dosyasına yazılmaz. Her modda: 10 dakikada
5 yanlış şifre denemesinden sonra o kullanıcı adı 10 dakika kilitlenir.

**Veritabanı:** Yerelde SQLite (`kodkoc.db` dosyası). `DATABASE_URL` verilince aynı kod PostgreSQL ile
çalışır; tablolar ilk açılışta kendiliğinden oluşur. Sorgular SQLite yazımıyla yazılır,
`veritabani.py` içindeki `Baglanti` sınıfı yer tutucuları (`?` → `%s`) ve farklı yazımları çevirir.
Bilgisayardaki verileri sunucuya aktarmak için: `DATABASE_URL` ayarlıyken `python tasima.py kodkoc.db`
(hedef veritabanı boşsa çalışır, id'ler ve şifreler aynen taşınır).
Sunum için örnek veri: `python demo_veri.py olustur <şifre>` (silmek için `sil <şifre>`).
Yedek: `python yedek_al.py` (bütün tablolar `yedekler/` klasörüne JSON olarak; kişisel veri içerir, paylaşma).
Boş bir veritabanına geri yüklemek: `python yedek_al.py geri yedekler/dosya.json`.
"Şifremi unuttum" e-postası için `SMTP_SUNUCU`, `SMTP_KULLANICI`, `SMTP_SIFRE`, `SMTP_GONDEREN` ayarlanır (`.env.example`).

**Render + Neon ile kurulum:** Veritabanı Neon'da (neon.tech, ücretsiz PostgreSQL), uygulama Render'da.
Depodaki `render.yaml` uygulamayı tanımlar: Render'da *New → Blueprint* seçip GitHub deposunu bağlamak
yeterli. `GEMINI_API_KEY`, `OGRETMEN_KODU` ve `DATABASE_URL` (Neon'daki bağlantı adresi) kurulumda
sorulur, `FLASK_SECRET_KEY` otomatik üretilir. Sunucu `/saglik` adresiyle
uygulamanın ayakta olup olmadığını kontrol eder.

Testleri PostgreSQL ile çalıştırmak için BOŞ bir test veritabanının adresini `TEST_DATABASE_URL`
olarak verin (testler her seferinde tabloları boşaltır, gerçek veritabanını asla vermeyin).

## Yol haritası

- [x] 6. hafta: Proje anlatımından yol haritası çıkarma (terminal)
- [x] 7. hafta: Web arayüzü (Flask)
- [x] 8. hafta: Veritabanı, adımları "tamamlandı" olarak işaretleme, geçmiş sayfası
- [x] 8. hafta: Takılınca "ipucu iste" özelliği, notlar, silme, arama
- [x] 8. hafta: Kullanıcı girişi (her öğrencinin kendi yol haritaları)
- [x] 8. hafta: GitHub commit takibi
- [x] 8. hafta: Formlara CSRF koruması
- [x] 8. hafta: Öğretmen yorumları
- [x] 8. hafta: Otomatik testler (pytest)
- [x] 8. hafta: Öğretmen paneli (sınıflar, katılım kodu, ilerleme tablosu)
- [x] 9. hafta: Canlıya hazırlık (canlı mod, öğretmen davet kodu, günlük yapay zekâ sınırı, şifre deneme sınırı)
- [x] 9. hafta: Sunucuya yükleme (Render) ve veritabanı bağlantısı (Neon PostgreSQL): https://kodkoc.onrender.com
- [x] 9. hafta: Kalan yapay zekâ hakkı, öğretmenin şifre sıfırlaması, sınıfın yapay zekâ kullanımı, hesap silme
- [x] 9. hafta: Adımlara hedef tarih, öğrenciyi sınıftan çıkarma, haftalık özet
- [x] 9. hafta: Sınıf projesi, sınıfın son etkinlikler akışı
- [x] 9. hafta: Öğretmen değerlendirmesi (1-5 puan), öğrencinin kendi hedefleri, öğretmen paneli özeti
- [x] 9. hafta: Değerlendirme bildirimi, sınıf projesinde toplu hedef
- [x] 9. hafta: Öğretmenime sor, sınıf projesinin adım adım dağılımı
- [x] 9. hafta: Öğrencinin bildiklerine göre koç, sınıfla paylaşılan sorular
- [x] 9. hafta: "Bugün ne yapayım?" önerisi, yazdırılabilir sınıf raporu
- [x] 9. hafta: Üç yeni rozet ve rozet bildirimi, Notlarım sayfası, sunum için demo verisi
- [x] 9. hafta: Kullanıcı profilleri, sınıf sohbeti (grup) ve özel mesajlaşma
- [x] 9. hafta: Mesaj bildirme ve engelleme, kötü kelime süzgeci, gizlilik sayfası
- [x] 9. hafta: Tarayıcıda Python çalıştırma (Pyodide)
- [x] 9. hafta: Mini quiz, ödev teslimi ve puanlama, grup projeleri (görev panosu + grup sohbeti)
- [x] 9. hafta: Proje şablonları, takvim, katılım takibi
- [x] 9. hafta: Telefona yüklenebilir uygulama (PWA), tarayıcı bildirimleri, e-postayla şifre sıfırlama, yedek
- [x] 10. hafta: Her sayfadan açılan mesaj paneli, kullanıcıların kendi kurduğu sohbet grupları
- [x] 10. hafta: Grup davetleri (kabul/ret) ve yönetici devri, sohbette anket, resim paylaşma
- [ ] Sesli-görüntülü görüşme
