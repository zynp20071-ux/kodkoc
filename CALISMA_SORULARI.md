# KodKoç – Sunuma Hazırlık Soruları

**Nasıl kullanılır:**
1. Soruyu oku, bağlantıdaki kodu aç.
2. Cevabı önce **kendi cümlelerinle** sesli söyle ya da bir kâğıda yaz.
3. Sonra "Cevap"a tıklayıp karşılaştır.

Cevabı açmadan önce en az bir dakika düşün; hocan da sana o kadar süre verecek.

> VS Code'da **Ctrl+Shift+V** ile önizleme açınca "Cevap" kutuları tıklanabilir olur.

---

## A. Veritabanı

### 1. Veritabanı neden her açılışta silinmiyor?
[veritabani.py:100](veritabani.py#L100) `hazirla()` her açılışta `CREATE TABLE` çalıştırıyor. Eski kayıtlar neden kaybolmuyor? [Satır 206-215](veritabani.py#L231-L242)'teki `sutun_yoksa_ekle` satırlarına neden ihtiyaç duyduk?

<details><summary>Cevap</summary>

- `CREATE TABLE **IF NOT EXISTS**`: Tablo zaten varsa hiçbir şey yapmaz, içindeki verilere dokunmaz.
- Ama tablo **varsa**, yeni eklediğimiz sütunlar (ör. `not_metni`, `kullanici_id`) da eklenmez. `IF NOT EXISTS` tabloyu atlar, sütunlara bakmaz.
- Bu yüzden `sutun_yoksa_ekle()` önce `PRAGMA table_info` ile tablonun sütunlarını okuyor; sütun yoksa `ALTER TABLE ... ADD COLUMN` ile ekliyor. Buna **göç (migration)** denir: eski veritabanı, veri kaybetmeden yeni yapıya geçer.
</details>

### 2. Neden `?` kullanıyoruz?
[veritabani.py:355](veritabani.py#L355) `yol_haritasi_getir()`: `WHERE id = ? AND kullanici_id = ?`
a) `AND kullanici_id = ?` silinseydi ne olurdu?
b) Neden `f"WHERE id = {harita_id}"` yazmıyoruz?

<details><summary>Cevap</summary>

a) Ayşe adres çubuğuna `/yol-haritasi/5` gibi rastgele sayılar yazarak **başkalarının** yol haritalarını açabilirdi. Sadece giriş yapmış olmak yetmez; her sorguda "bu kayıt bu kişinin mi?" diye sormak gerekir (yetkilendirme).

b) **SQL enjeksiyonu.** Değer metnin içine yapıştırılırsa, kullanıcı değer yerine SQL kodu yazabilir (ör. `' OR 1=1 --`) ve sorgunun anlamını değiştirir. `?` kullanınca `sqlite3` değeri her zaman **veri** olarak ele alır, asla kod olarak çalıştırmaz.
</details>

### 3. WHERE mi, HAVING mi?
[veritabani.py:381](veritabani.py#L381) `tum_yol_haritalari()`: Arama `WHERE` ile, "bitenler" filtresi `HAVING` ile yazılmış. Neden?

<details><summary>Cevap</summary>

- `WHERE` satırları **gruplamadan önce**, tek tek süzer. "Proje adında 'hesap' geçsin" tek bir satıra bakılarak anlaşılır.
- "Bitti" demek için bir yol haritasının **bütün adımlarını** saymak gerekir: `SUM(tamamlandi) = COUNT(id)`. Bu sayılar ancak `GROUP BY` ile gruplandıktan sonra oluşur.
- Grup sonuçlarına (`COUNT`, `SUM`) göre süzmek için `HAVING` kullanılır.
</details>

### 4. JOIN mi, LEFT JOIN mi?
Aynı sorguda `LEFT JOIN adimlar` var. Düz `JOIN` yazsaydık ne değişirdi?

<details><summary>Cevap</summary>

Düz `JOIN` sadece **iki tabloda da eşleşen** satırları getirir. Yapay zekâ biçimsiz cevap verdiyse yol haritasının hiç adımı olmayabilir; o yol haritası geçmiş listesinden **kaybolurdu**. `LEFT JOIN` soldaki tablonun (yol haritaları) her satırını, eşleşen adım olmasa bile getirir.
</details>

### 5. `commit()` ve `finally` ne işe yarıyor?
Hemen her fonksiyonda `baglanti.commit()` ve `try: ... finally: baglanti.close()` var.

<details><summary>Cevap</summary>

- `commit()`: Yapılan değişiklikleri **kalıcı** hale getirir. Commit edilmeyen değişiklik bağlantı kapanınca kaybolur.
- Birden çok değişiklik (ör. silmede ipuçları, adımlar, yol haritası) tek bir commit'le yapılırsa bir **işlem (transaction)** olur: Ya hepsi olur ya hiçbiri. Veritabanı yarım kalmaz.
- `finally`: İçindeki kod, `try` bloğunda hata olsa bile **her zaman** çalışır. Bağlantı açık unutulmaz.
</details>

### 6. Silmede sıra neden önemli?
[veritabani.py:454](veritabani.py#L454) `yol_haritasi_sil()`: Önce ipuçları, commit'ler ve yorumlar, sonra adımlar, en son yol haritası siliniyor. Neden?

<details><summary>Cevap</summary>

**Yabancı anahtar** kuralı: Bir adım bir yol haritasına bağlıysa (`REFERENCES yol_haritalari(id)`), önce yol haritasını silmek adımı "sahipsiz" bırakır; SQLite buna izin vermez. Bu yüzden önce "çocuk" kayıtlar, en son "ebeveyn" silinir. SQLite bu kuralı varsayılan olarak denetlemez; `baglan()` içindeki `PRAGMA foreign_keys = ON` denetimi açıyor.
</details>

### 7. Neden ayrı bir `sinif_uyeleri` tablosu?
[veritabani.py:164-167](veritabani.py#L164-L167). Öğrencinin sınıfını `kullanicilar` tablosuna bir `sinif_id` sütunu ekleyerek tutamaz mıydık?

<details><summary>Cevap</summary>

Bir öğrenci **birden çok** sınıfta olabilir. Tek bir `sinif_id` sütunu sadece bir sınıf tutabilir. Bir sınıfta çok öğrenci, bir öğrencinin çok sınıfı olunca buna **çoka-çok ilişki** denir ve **ara tablo** ile kurulur. `PRIMARY KEY (sinif_id, ogrenci_id)`, yani **bileşik birincil anahtar**, aynı öğrencinin aynı sınıfa iki kez eklenmesini engeller. Denenirse `IntegrityError` oluşur, biz de "Zaten bu sınıftasın" deriz.
</details>

### 8. İlişkili alt sorgu
[veritabani.py:826](veritabani.py#L826) `sinif_ozeti()` içinde parantez içinde bir sürü `SELECT COUNT(*) ... WHERE y.kullanici_id = k.id` var. `k.id` nereden geliyor?

<details><summary>Cevap</summary>

`k`, dıştaki sorgunun `kullanicilar AS k` tablosu. Parantez içindeki her `SELECT`, dış sorgunun **o anki satırındaki öğrenci için** ayrı ayrı çalışır. Buna **ilişkili alt sorgu (correlated subquery)** denir. Böylece tek bir sorguyla her öğrencinin yol haritası, adım, ipucu ve commit sayısı ayrı ayrı hesaplanır.
</details>

---

## B. Flask ve web

### 9. Neden `redirect`?
[app.py:454](app.py#L454) `yol_haritasi()`: Yapay zekânın cevabından sonra `render_template` yerine `redirect` yapıyoruz. Öğrenci sonuç sayfasında F5'e bassa ne olurdu?

<details><summary>Cevap</summary>

Sayfa bir POST isteğinin cevabı olsaydı, tarayıcı F5'te **formu tekrar gönderirdi**. Yapay zekâya ikinci kez gidilirdi: süre ve kota harcanır, aynı yol haritası iki kez kaydedilirdi. `redirect` ile tarayıcı yeni bir **GET** isteği yapar; F5 sadece o sayfayı yeniler. Buna **Post/Redirect/Get** kalıbı denir. Ayrıca her yol haritasının `/yol-haritasi/5` gibi kalıcı bir adresi olur.
</details>

### 10. Dekoratör ne yapıyor?
[app.py:169](app.py#L169) `giris_gerekli`. Bir route'un üstüne `@giris_gerekli` yazınca ne oluyor? İçindeki `@wraps` neden var?

<details><summary>Cevap</summary>

- Dekoratör, bir fonksiyonu **saran** başka bir fonksiyondur. `@giris_gerekli` yazınca Flask, sayfa fonksiyonunu çağırmadan önce `kontrol()` çalışır: Giriş yoksa giriş sayfasına yönlendirir, varsa asıl fonksiyonu çağırır. Aynı kontrolü 20 route'a tek tek yazmak yerine tek satırla ekleriz.
- `@wraps`: Sarılan fonksiyonun adını (ör. `gecmis`) korur. Olmasaydı bütün sarılan route'ların adı `kontrol` olurdu. Flask her route'u adıyla tanıdığı için aynı adı ikinci kez görünce hata verir ve program hiç açılmaz. `url_for("gecmis")` da bu adlara dayanır.
</details>

### 11. `before_request` ve `g`
[app.py:110](app.py#L110) `kullaniciyi_yukle()`. Bu fonksiyonu kim, ne zaman çağırıyor? `g` nedir?

<details><summary>Cevap</summary>

`@app.before_request` sayesinde Flask bu fonksiyonu **her istekten önce** kendiliğinden çağırır. Fonksiyon oturumdaki `kullanici_id`'ye bakıp kullanıcıyı veritabanından okur ve `g.kullanici`'ye koyar. `g`, **tek bir isteğin** süresince bilgi taşıyan bir kutudur. İstek bitince silinir. Hem route'larda hem şablonlarda (ör. menüde kullanıcı adı) kullanılabilir.
</details>

### 12. Çerezdeki id değiştirilebilir mi?
Giriş yapınca `session["kullanici_id"] = 5` yazıyoruz ve bu bilgi tarayıcıdaki çerezde duruyor. Biri çerezi açıp 5'i 6 yaparak başkası olabilir mi?

<details><summary>Cevap</summary>

Hayır. Flask oturum çerezini `secret_key` ile **imzalar**. Çerezin içeriği değiştirilirse imza tutmaz ve Flask çerezi geçersiz sayar. İmzayı yeniden atmak için `secret_key` gerekir; o da sadece `.env` dosyasında duruyor. **Dikkat:** İmza değiştirilmeyi engeller ama okunmayı engellemez. Bu yüzden oturuma şifre gibi gizli bilgiler konmaz, sadece id konur.
</details>

---

## C. Güvenlik

### 13. Şifre ve giriş
[veritabani.py:609](veritabani.py#L609). Şifre nasıl saklanıyor? Girişte kullanıcı adı yanlış da olsa şifre yanlış da olsa neden **aynı** mesaj gösteriliyor?

<details><summary>Cevap</summary>

- `generate_password_hash` ile şifrenin **hash**'i saklanıyor. Hash tek yönlüdür, geri çevrilemez. Veritabanı çalınsa bile şifreler okunamaz. Girişte `check_password_hash` girilen şifrenin hash'ini kayıtlı hash'le karşılaştırır.
- Farklı mesaj verseydik ("böyle bir kullanıcı yok" ve "şifre yanlış"), kötü niyetli biri hangi kullanıcı adlarının **var olduğunu** öğrenebilirdi.
</details>

### 14. CSRF
[app.py:140](app.py#L140) ve [app.py:152](app.py#L152). Her formda gizli bir `csrf` alanı var. Hangi saldırıyı engelliyor? Çıkış neden bir bağlantı değil de form (POST)?

<details><summary>Cevap</summary>

- **CSRF:** Sen KodKoç'a giriş yapmışken kötü niyetli bir site, tarayıcın üzerinden KodKoç'a gizlice form gönderebilir. Tarayıcı oturum çerezini de eklediği için istek senden gelmiş gibi görünür. Formdaki jeton oturuma özel ve rastgele; başka site bunu bilemez. Jeton tutmazsa istek 400 ile reddedilir.
- Çıkış bir bağlantı (GET) olsaydı, başka bir sitedeki "Tıkla" yazılı bir bağlantı seni KodKoç'tan habersizce çıkarabilirdi. GET isteklerinde jeton kontrolü yapmıyoruz ve tarayıcı böyle bir bağlantıda çerezi gönderir. Genel kural: **durumu değiştiren her işlem POST olmalı**, GET sadece okumak içindir.
</details>

### 15. `| safe` tehlikeli değil mi?
[templates/yol_haritasi.html](templates/yol_haritasi.html) içinde `{{ adim.icerik_html | safe }}` var. Jinja normalde HTML'i kaçırır; burada neden kapatıyoruz, bu güvenli mi?

<details><summary>Cevap</summary>

Yapay zekânın markdown cevabını (kalın yazı, maddeler) gerçek HTML'e çevirdik; `safe` olmasa `<strong>` etiketleri ekranda yazı olarak görünürdü. Güvenli, çünkü çevirmeden **önce** [app.py:243](app.py#L243) `guvenli_markdown()` içinde `html.escape` ile metindeki bütün `<`, `>` karakterlerini etkisiz hale getiriyoruz. Kullanıcının yazdığı not ve proje gibi metinlerde ise `safe` yok; Jinja onları otomatik kaçırıyor. Buna **XSS** koruması denir.
</details>

### 16. Öğretmen herkesi görebilir mi?
Biri kayıtta "Öğretmenim" seçerse bütün öğrencilerin verisini görebilir mi?

<details><summary>Cevap</summary>

Hayır. Öğretmen sadece kendi sınıfına **kodla katılmış** öğrencileri görür: [veritabani.py:1122](veritabani.py#L1122) `ogretmen_gorebilir_mi()`. Erişimi öğrenci verir, öğretmen alamaz. Bu yüzden rol seçimi serbest olsa da bu bir güvenlik açığı değil. Öğrenci sınıftan ayrılınca erişim hemen kapanır.
</details>

---

## D. Yapay zekâ ve GitHub

### 17. Yapay zekâ yine de kod verirse?
[kodkoc.py:48](kodkoc.py#L48) ve [kodkoc.py:197](kodkoc.py#L197).

<details><summary>Cevap</summary>

İki katman var. Birincisi `TALIMAT` içindeki "ASLA kod verme" kuralı. Yapay zekâ bazen kurala uymayabilir; bu yüzden ikinci katman olarak `kod_bloklarini_temizle()` ```` ``` ```` ile başlayıp biten her bloğu düzenli ifadeyle (`re.sub`) bulup siliyor. `re.DOTALL` sayesinde `.` satır sonlarını da kapsıyor, böylece çok satırlı bloklar da yakalanıyor.

Ardından `satir_ici_kodu_temizle()` cümle içindeki `` `...` `` parçalarına bakıyor. `input()` gibi bir isim, `"3"` gibi kısa bir değer ya da `==` gibi bir operatör ise bırakıyor. Boşluk, `=` ya da içi dolu parantez içeriyorsa (yani bir kod satırına benziyorsa) siliyor.
</details>

### 17b. Koyu tema için neden bütün renkleri değişkene çevirdik?
[static/style.css](static/style.css) dosyasının başında `--zemin`, `--vurgu` gibi değişkenler var; dosyanın geri kalanında `#93391C` gibi renk kodu hiç yok. Neden?

<details><summary>Cevap</summary>

Koyu tema sadece değişkenlerin **değerlerini** değiştiriyor (`:root[data-tema="koyu"] { --zemin: #1B1714; ... }`). Bir yerde renk doğrudan yazılmış olsaydı, o yer koyu temada da açık renkte kalır ve göze batardı. Renkleri tek yerde tanımlamak, değiştirmeyi de kolaylaştırır: turuncunun tonunu değiştirmek için tek satırı değiştirmek yeter. `tests/test_tema.py` dosyada değişken dışında renk kodu kalmadığını kontrol ediyor.
</details>

### 18. Her hata için tekrar denenir mi?
[kodkoc.py:242](kodkoc.py#L242) `yapay_zekaya_sor()`. Yapay zekâ hata verince program her zaman bekleyip tekrar mı deniyor?

<details><summary>Cevap</summary>

Hayır. Sadece **geçici** hatalarda tekrar deniyor: 429 (çok fazla istek), 500 ve 503 (sunucu yoğun). Bunlar biraz sonra düzelebilir. 400 gibi **kalıcı** hatalarda (ör. yanlış API anahtarı) beklemek işe yaramaz, hemen hata gösterilir. Bekleme süresi her denemede artıyor (2 sn, 4 sn).
</details>

### 19. Commit'ler neden veritabanında saklanıyor?
[veritabani.py:973](veritabani.py#L973). Sayfa her açıldığında GitHub'dan çekmek daha kolay olmaz mıydı?

<details><summary>Cevap</summary>

- GitHub anahtarsız kullanımda **saatte 60 isteğe** izin veriyor. Her sayfa açılışında istek atsak sınır hızla dolar. Ayrıca sayfa yavaşlar ve GitHub erişilemezse sayfa bozulur.
- Bu yüzden commit'ler sadece "Yenile"ye basınca çekiliyor ve iki yenileme arasında 30 saniye kuralı var.
- `UNIQUE (yol_haritasi_id, sha)` ile `INSERT OR IGNORE` birlikte, zaten kayıtlı commit'i hata vermeden atlıyor. Sadece yeniler ekleniyor.
</details>

### 19b. Kodumu incelet neden satır numarası ekliyor?
[kodkoc.py:327](kodkoc.py#L327) `kod_incele()` yapay zekâya göndermeden önce koda `satir_numarala()` uyguluyor. Neden? Ayrıca [app.py:698](app.py#L698) içinde kod neden `strip()` değil de `rstrip()` ile temizleniyor?

<details><summary>Cevap</summary>

- Yapay zekâ "Satır 8'e bak" diyebilsin diye. Talimat ona düzeltilmiş kodu yazmasını yasaklıyor; bunun yerine yeri **satır numarasıyla** gösteriyor. Numaralar olmasa yapay zekâ satırları sayarken yanılabilirdi.
- `strip()` metnin hem başındaki hem sonundaki boşlukları siler. Python'da **girinti** (baştaki boşluk) kodun anlamını değiştirir; ilk satır girintiliyse silinirse kod bozulur. `rstrip()` sadece sondaki boş satırları ve boşlukları siler.
</details>

### 19c. Yapay zekâ önceki soruyu nasıl hatırlıyor?
[kodkoc.py:338](kodkoc.py#L338) `soru_sor()` ve [app.py:737](app.py#L737) `koca_soru_sor()`. Öğrenci "peki bunu neden kullanıyoruz?" diye sorunca koç önceki soruyu nereden biliyor? Neden bütün konuşma değil de son 3 soru gönderiliyor (`onceki[-3:]`)?

<details><summary>Cevap</summary>

- Yapay zekânın **kendi hafızası yok**; her istek bağımsız. Önceki soru-cevapları veritabanından (`koc_sorulari` tablosu) okuyup yeni mesajın içine "daha önceki konuşmanız" diye biz ekliyoruz.
- `onceki[-3:]` listenin **son 3 elemanını** alır (negatif indeks sondan sayar). Bütün konuşmayı göndermek mesajı uzatır: hem yavaşlar hem kotayı harcar. Son 3 soru, konuyu takip etmeye yetiyor.
</details>

### 19d. Çalışma serisi
[app.py:875](app.py#L875) `seri_hesapla()`. Öğrenci dün ve önceki gün çalıştı, bugün henüz bir şey yapmadı. Şu anki serisi kaç görünür, neden? Günler neden liste değil de **küme** (`set`)?

<details><summary>Cevap</summary>

- **2 gün.** Bugün çalışılmadıysa sayım dünden başlıyor. Gün daha bitmedi; sabah sayfayı açan öğrenci serisini "0" görüp moral bozmasın diye.
- `gun in gunler` sorusu kümede çok hızlıdır: Python her elemana tek tek bakmaz, doğrudan "var mı?" diye kontrol eder. Listede ise baştan sona aranır. Ayrıca aynı gün iki kez olamaz; küme tekrarları zaten kabul etmez.
</details>

### 19e. Sınıf grafiği
[veritabani.py:903](veritabani.py#L903) `sinif_etkinlikleri()` ve [app.py:1088](app.py#L1088) `sinif_istatistigi()`. Ali bugün 3 ipucu aldı ve 1 adım bitirdi, Ayşe bugün 1 soru sordu. Günlük grafikte bugünün sütununda hangi sayı yazar? SQL'deki `DISTINCT` silinseydi ne olurdu? Grafikte en kalabalık gün neden her zaman tam boy çiziliyor?

<details><summary>Cevap</summary>

- **2.** Grafik "kaç iş yapıldı" değil, "kaç **farklı öğrenci** çalıştı" sorusunu soruyor. `DISTINCT`, aynı (öğrenci, gün) çiftinden tek satır bırakıyor.
- `DISTINCT` silinirse Ali'nin 4 etkinliği 4 satır olarak gelirdi. Ama fonksiyon sonucu bir **kümeye** koyuyor; küme de tekrarları kabul etmediği için sonuç yine 2 olurdu. Yani iki koruma var: biri SQL'de, biri Python'da.
- Çubuk boyu `100 * sayi / en_cok` ile hesaplanıyor. En kalabalık günde `sayi == en_cok`, yani %100. Böylece 3 kişilik sınıfta da 30 kişilik sınıfta da grafik kutuyu dolduruyor. Hiç etkinlik yoksa `en_cok` 0 olur; sıfıra bölmemek için o durumda oran doğrudan 0 yazılıyor.
</details>

---

## E. Testler

### 20. Testler neden gerçek yapay zekâyı çağırmıyor?
[tests/conftest.py](tests/conftest.py) `sahte_yapay_zeka` fixture'ı.

<details><summary>Cevap</summary>

`monkeypatch` test süresince `kodkoc.yol_haritasi_iste` fonksiyonunu sabit cevap veren sahte bir fonksiyonla değiştiriyor. Bunun faydaları:
1. **Hızlı:** İnternete çıkılmıyor.
2. **Ücretsiz:** API kotası harcanmıyor.
3. **Güvenilir:** Yapay zekâ her seferinde farklı cevap verir; sabit cevapla test hep aynı sonucu verir.
4. **Yoğunluktan etkilenmez:** Gemini çökse bile testler çalışır.

Gerçek bağlantıyı ayrıca elle denedik.
</details>

### 21. Her teste neden ayrı veritabanı?
`bos_veritabani` fixture'ında `autouse=True` ne demek, neden her teste boş bir veritabanı veriliyor?

<details><summary>Cevap</summary>

`autouse=True`: Fixture, test istemese bile **her testten önce** kendiliğinden çalışır. Her test temiz bir veritabanıyla başlar; böylece testler birbirini etkilemez (**test yalıtımı**). Bir testin eklediği kullanıcı başka bir testi bozamaz, testler hangi sırayla çalışırsa çalışsın sonuç aynı olur. Ayrıca senin gerçek `kodkoc.db` dosyana hiç dokunulmaz.
</details>

---

## F. Kendin dene (cevap yok, sadece ipucu)

> Başlamadan önce proje klasörünün bir kopyasını al. Her denemeden sonra `test_calistir.bat` ile testleri çalıştır.

**Alıştırma 1: Testler değişikliği yakalıyor mu?**
[app.py](app.py) içindeki `EN_FAZLA_IPUCU = 3` değerini 5 yap, testleri çalıştır.
- Hangi test bozuldu, neden?
- Değeri geri 3 yap.

<details><summary>İpucu</summary>

`tests/test_yol_haritasi.py` içinde "3 ipucundan sonra hak biter" diye bir beklenti var. Testler sadece hataları değil, **istemeden** yapılan değişiklikleri de yakalar.
</details>

**Alıştırma 2: Kendi SQL sorgun**
Python'u aç ve şu sorunun cevabını veren bir SQL sorgusu yaz: "Hangi gün kaç adım tamamlanmış?"

```
python
>>> import sqlite3
>>> b = sqlite3.connect("kodkoc.db")
>>> b.execute("...senin sorgun...").fetchall()
```

<details><summary>İpucu</summary>

- Hangi tabloda, hangi sütunda tamamlanma zamanı var?
- SQLite'ta `DATE(...)` fonksiyonu bir tarih-saatten sadece tarihi alır.
- Günlere göre saymak için hangi iki kelime gerekiyor? (Soru 3'e bak.)
- Tamamlanmamış adımlarda zaman boş (NULL) olur; onları dışarıda bırakmayı unutma.
</details>

**Alıştırma 3: Excel'e yeni sütun**
Öğretmenin indirdiği CSV dosyasına "Not sayısı" sütununu ekle (öğrencinin not yazdığı adım sayısı).

<details><summary>İpucu</summary>

1. Sayıyı nerede hesaplayacaksın? [veritabani.py:826](veritabani.py#L826) `sinif_ozeti()` içindeki ilişkili alt sorgulardan birine bak, benzerini yaz. Not hangi tabloda, hangi sütunda? "Not yazılmış" demek o sütunun nasıl olması demek?
2. [app.py:1198](app.py#L1198) `sinif_indir()` içinde başlık satırına ve her öğrencinin satırına yeni değeri ekle.
3. [tests/test_bildirim_ve_disa_aktarma.py](tests/test_bildirim_ve_disa_aktarma.py) içindeki CSV testi artık bozulacak, neden? Testi yeni sütuna göre güncelle.
</details>
