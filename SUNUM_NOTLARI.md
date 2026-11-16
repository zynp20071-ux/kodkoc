# KodKoç – Sunum Notları (8. ve 9. hafta)

> **9. hafta (canlıya geçiş) için en alttaki 10. bölüme bak.**

> Bu not senin için. Ezberlemek yerine her maddedeki bağlantıya tıklayıp kodu kendin oku. Hocan büyük ihtimalle "şunu aç, anlat" diyecek. Kodu kendi cümlelerinle anlatabiliyorsan hazırsın.

---

## 1. Tek cümlede bu hafta

Yol haritalarını **veritabanına** kaydettik. Öğrenci adımlarını **işaretleyip ilerlemesini** görebiliyor, takılınca **kod almadan ipucu** alabiliyor, kendi kodunu gönderip **düzeltilmiş kod almadan geri bildirim** alabiliyor. **Öğretmen**, sınıfının nerede takıldığını görüp yorum bırakabiliyor ve tabloyu Excel'e aktarabiliyor. **GitHub** commit'leri adımlara bağlanıyor. Hepsi **giriş, güvenlik ve 183 otomatik testle** korunuyor.

---

## 2. Sunumdan önce hazırlık (bir gün önce yap)

- [ ] `baslat.bat` ile programı aç, API anahtarının çalıştığını gör.
- [ ] İki tarayıcı penceresi hazırla: **normal pencere = öğretmen**, **gizli pencere = öğrenci**. İkisi ayrı oturum açabilsin diye böyle.
- [ ] GitHub'da **herkese açık (public)** boş bir depo aç. Web sayfasından bir dosya ekle, commit mesajına `Adım 1: başlangıç` yaz.
- [ ] `test_calistir.bat`'ı bir kez çalıştır, `183 passed` gör (yaklaşık 4,5 dakika sürüyor).
- [ ] **Yedek plan:** Gemini bazen "çok yoğun" (503) hatası veriyor. Sunumdan önce öğrenci hesabıyla bir yol haritasını önceden çıkar. Canlıda hata gelirse "bakın, hata mesajı da Türkçe ve anlaşılır" deyip hazır olanla devam et.

---

## 3. Demo akışı (~10 dakika)

| Süre | Ne göster | Ne söyle |
|---|---|---|
| 1 dk | Ana sayfa | "Yeni başlayanlar ya yapay zekâdan kodu kopyalıyor ya da nereden başlayacağını bilmiyor. KodKoç kod vermez, yol gösterir." |
| 1 dk | **Öğretmen** penceresi: *Öğretmenim* seçerek kayıt ol → *Sınıf aç* → kod çıkar | "Öğretmen sınıf açıyor, 6 karakterlik bir kod alıyor. Kodda 0/O, 1/I gibi karışan harfler yok." |
| 2 dk | **Öğrenci** penceresi: kayıt ol → *Sınıfım* → kodla katıl → ana sayfada *Proje fikri al* (ilgi: "futbol") → bir fikri seç → *Yol haritamı çıkar* | Beklerken: "Yapay zekâya özel bir talimat veriyoruz: asla kod verme, sadece adım, konu ve kontrol yaz." |
| 1 dk | 1. adımda *Tamamladım* → ilerleme çubuğu. Bir adımı *Adımı düzenle* → sil → numaralar kayıyor; *+ Kendi adımını ekle* | "Her adım veritabanında ayrı bir satır; `tamamlandi` sütunu 0 ya da 1." |
| 2 dk | 2. adımda *Takıldım* → 1, 2, 3. ipucu | "İpucu üç seviyeli: önce soru soruyor, sonra kavramın adını söylüyor, en son kodsuz bir plan veriyor. Dördüncüyü vermiyor." |
| 1 dk | Bir adımda *Koça soru sor* → "Liste ile sözlük farkı ne?", sonra "Kodunu yazar mısın?" | "Kavram sorusunu benzetmeyle anlatıyor; kod isteyince nazikçe reddedip düşündürüyor. Sohbet gibi devam ediyor, son 3 soruyu hatırlıyor." |
| 1 dk | Bir adımda *Kodumu incelet* → hatalı küçük bir kod yapıştır (aşağıdaki örnek) | "Öğrenci kendi kodunu gönderiyor. KodKoç hatanın satırını söylüyor ama düzeltilmiş kodu vermiyor, soru soruyor." |
| 1 dk | *GitHub deponu bağla* → commit 1. adımın altında | "Commit mesajında 'Adım 1' yazınca o adıma bağlanıyor. Öğretmen öğrencinin gerçekten kod yazdığını görüyor." |
| 1 dk | **Öğretmen** penceresinde sınıf sayfası → tablo → *Yardıma ihtiyacı olabilir* → öğrenciye tıkla → *Yorum yaz*. Sonra *Excel'e aktar*. *Sınıf istatistikleri* grafiklerini göster. *Duyurular* kutusuna bir duyuru yaz | "Bitmemiş ve 2+ ipucu alınmış adımlar burada çıkıyor. Öğretmen nereye yardım edeceğini görüyor; tabloyu not vermek için Excel'e de alabiliyor. Grafikler sınıfın genel durumunu bir bakışta gösteriyor. Duyuruyla bütün sınıfa tek seferde mesaj bırakıyor." |
| 1 dk | **Öğrenci** penceresini yenile → menüde *Geçmiş* yanında **1** rozeti → yol haritasını aç → yorum "Yeni" etiketiyle. Ana sayfada öğretmenin duyurusu, menüde *Sınıfım* yanında sayı. *Yazdır / PDF* düğmesi. Kullanıcı adına tıkla → *Profil*: çalışma serisi ve takvim. Sonra `test_calistir.bat` → **183 passed** | "Yorum gelince öğrenci bildirim görüyor; açınca okundu sayılıyor. Her özelliğin otomatik testi var; testler internete çıkmıyor, gerçek veriye dokunmuyor." |

**Demo için hatalı örnek kod** ("Kodumu incelet"e yapıştır; 8. satırda tür hatası, 9. satırda `3` ile `"3"` karışıklığı var):

```python
gorevler = []
while True:
    secim = input("1-Ekle 2-Sil 3-Çık: ")
    if secim == "1":
        gorevler.append(input("Görev: "))
    elif secim == "2":
        no = input("Kaçıncı görev? ")
        gorevler.remove(no)
    elif secim == 3:
        break
```

Bu kodla yaptığım gerçek denemede KodKoç iki hatayı da doğru satırla buldu ve düzeltilmiş kod vermeden, öğrenciye "girdi metin mi sayı mı?" diye sordu.

---

## 4. Hangi özellik kodda nerede?

### Veritabanı (SQLite)
| Ne | Nerede |
|---|---|
| Bağlantı açma | [veritabani.py:90](veritabani.py#L90) `baglan()` |
| 11 tablonun oluşturulması | [veritabani.py:100](veritabani.py#L100) `hazirla()` |
| Eski veritabanını yükseltme (göç) | [veritabani.py:252-263](veritabani.py#L252-L263) ve [veritabani.py:261](veritabani.py#L261) `sutun_yoksa_ekle()` |
| Yapay zekâ cevabını adımlara bölme | [veritabani.py:277](veritabani.py#L277) `cevabi_parcala()` |
| `INSERT` + `?` yer tutucular | [veritabani.py:318](veritabani.py#L318) `yol_haritasi_ekle()` |
| `LEFT JOIN`, `GROUP BY`, `LIKE`, `HAVING` | [veritabani.py:381](veritabani.py#L381) `tum_yol_haritalari()` |
| `UPDATE` | [veritabani.py:581](veritabani.py#L581) `adim_durumunu_degistir()` |
| `DELETE` + işlem (transaction) | [veritabani.py:454](veritabani.py#L454) `yol_haritasi_sil()` |

### Web (Flask)
| Ne | Nerede |
|---|---|
| Ana sayfa: "Kaldığın yerden devam et" (`ORDER BY ... LIMIT 1`) | [app.py:398](app.py#L398) `ana_sayfa()`, [veritabani.py:1145](veritabani.py#L1145) `devam_edilecek_adim()` |
| Yol haritası çıkarma, ardından yönlendirme (PRG) | [app.py:454](app.py#L454) `yol_haritasi()` |
| Yol haritası sayfasını hazırlama (öğrenci + öğretmen ortak) | [app.py:501](app.py#L501) `yol_haritasi_sayfasi()` |
| Adım ekleme / düzenleme / silme (numaraları yeniden sıralama) | [veritabani.py:1257](veritabani.py#L1257) `adim_sil()`, [app.py:830](app.py#L830) `adim_sil()` |
| Başlığı güncel numarayla gösterme (Jinja filtresi) | [app.py:280](app.py#L280) `adim_basligi()` |
| Rozetler (`NOT EXISTS`, alt sorguda `GROUP BY`/`HAVING`) | [veritabani.py:1294](veritabani.py#L1294) `rozet_verileri()`, [app.py:847](app.py#L847) `ROZETLER`, [templates/_rozetler.html](templates/_rozetler.html) (`include`) |
| Adım işaretleme | [app.py:971](app.py#L971) `adim_isaretle()` |
| Ortak sayfa iskeleti (şablon kalıtımı) | [templates/taban.html](templates/taban.html) |
| İlerleme çubuğu (genişlik = yüzde) | [templates/yol_haritasi.html:32](templates/yol_haritasi.html#L32) |

### Yapay zekâ
| Ne | Nerede |
|---|---|
| Yol haritası talimatı ("asla kod verme") | [kodkoc.py:48](kodkoc.py#L48) `TALIMAT` |
| İpucu talimatı (3 seviye) | [kodkoc.py:90](kodkoc.py#L90) `IPUCU_TALIMATI` |
| Kod bloğu filtresi (ikinci güvence) | [kodkoc.py:197](kodkoc.py#L197) `kod_bloklarini_temizle()` |
| Satır içi kod filtresi (`input()` kalır, `liste.pop(int(no))` silinir) | [kodkoc.py:215](kodkoc.py#L215) `satir_ici_kodu_temizle()` |
| Model sırası + yoğunlukta bekleyip tekrar deneme | [kodkoc.py:242](kodkoc.py#L242) `yapay_zekaya_sor()` |
| İpucu isteği ve 3 hak sınırı | [app.py:667](app.py#L667) `ipucu()` |
| Proje fikri: JSON cevap isteme ve doğrulama | [kodkoc.py:142](kodkoc.py#L142) `FIKIR_TALIMATI`, [kodkoc.py:297](kodkoc.py#L297) `proje_fikirleri_iste()`, [app.py:416](app.py#L416) `proje_fikri()` |
| Kod inceleme talimatı ("düzeltilmiş kod verme, satır numarası söyle") | [kodkoc.py:115](kodkoc.py#L115) `KOD_INCELEME_TALIMATI` |
| Koda satır numarası ekleme + yapay zekâya gönderme | [kodkoc.py:327](kodkoc.py#L327) `kod_incele()` |
| Kodumu incelet: doğrulama, 5 hak, kaydetme | [app.py:698](app.py#L698) `kod_incele()` ve [veritabani.py:1174](veritabani.py#L1174) `kod_incelemesi_ekle()` |
| Koça soru sor: talimat ("benzetmeyle anlat, kod isterse reddet") | [kodkoc.py:160](kodkoc.py#L160) `SORU_TALIMATI`, [kodkoc.py:338](kodkoc.py#L338) `soru_sor()` (önceki konuşmayı mesaja ekleme) |
| Koça soru sor: 10 hak, son 3 soru "hafıza" | [app.py:737](app.py#L737) `koca_soru_sor()`, [veritabani.py:1338](veritabani.py#L1338) `koc_sorusu_ekle()` |

### Kullanıcılar ve öğretmen
| Ne | Nerede |
|---|---|
| Şifre hash'leme | [veritabani.py:609](veritabani.py#L609) `kullanici_ekle()`, [veritabani.py:634](veritabani.py#L634) `kullanici_dogrula()` |
| Kayıt kuralları | [app.py:314](app.py#L314) `kayit()` |
| Her istekte kullanıcıyı yükleme (`before_request`, `g`) | [app.py:110](app.py#L110) `kullaniciyi_yukle()` |
| `@giris_gerekli` dekoratörü | [app.py:169](app.py#L169) |
| `@ogretmen_gerekli` (rol tabanlı yetki) | [app.py:183](app.py#L183) |
| "Bu kayıt senin mi?" (`AND kullanici_id = ?`) | [veritabani.py:355](veritabani.py#L355) `yol_haritasi_getir()` |
| Çoka-çok ilişki (ara tablo) | [veritabani.py:164-167](veritabani.py#L164-L167) `sinif_uyeleri` |
| Sınıf tablosu (ilişkili alt sorgular) | [veritabani.py:826](veritabani.py#L826) `sinif_ozeti()` |
| "Yardıma ihtiyacı olabilir" | [veritabani.py:876](veritabani.py#L876) `takilan_adimlar()` |
| Öğretmen öğrenciyi görebilir mi? (`EXISTS`) | [veritabani.py:1122](veritabani.py#L1122) `ogretmen_gorebilir_mi()` |
| Öğretmen yorumu | [app.py:1302](app.py#L1302) `yorum_yaz()` |
| Yeni yorum bildirimi (okundu) | [veritabani.py:1083](veritabani.py#L1083) `okunmamis_yorum_sayisi()`, [veritabani.py:1098](veritabani.py#L1098) `yorumlari_okundu_yap()`, [app.py:488](app.py#L488) `yol_haritasi_goster()` |
| Excel'e aktarma (CSV) | [app.py:1198](app.py#L1198) `sinif_indir()` |
| Sınıf istatistikleri ve grafikler | [app.py:1088](app.py#L1088) `sinif_istatistigi()`, [veritabani.py:903](veritabani.py#L903) `sinif_etkinlikleri()`, `templates/sinif_detay.html` |
| Sınıf duyurusu yazma / silme (sadece kendi sınıfı) | [app.py:1172](app.py#L1172) `duyuru_yaz()`, [veritabani.py:1493](veritabani.py#L1493) `duyuru_sil()` (`JOIN` ile sahiplik kontrolü) |
| Öğrencinin duyuruları ve "Yeni" bilgisi (tek sayıyla okundu takibi) | [veritabani.py:1515](veritabani.py#L1515) `ogrencinin_duyurulari()`, [veritabani.py:1556](veritabani.py#L1556) `duyurulari_okundu_yap()`, [app.py:1017](app.py#L1017) `sinifim()` |
| Şifre değiştirme (eski şifreyi doğrulama) | [veritabani.py:1387](veritabani.py#L1387) `sifre_degistir()`, [app.py:938](app.py#L938) `sifre_degistir()` |
| Çalışma günleri (`UNION ALL`, `DATE()`) | [veritabani.py:1428](veritabani.py#L1428) `calisma_gunleri()` |
| Çalışma serisi ve takvim (`timedelta`, küme) | [app.py:875](app.py#L875) `seri_hesapla()`, [app.py:899](app.py#L899) `takvim_olustur()`, [templates/profil.html](templates/profil.html) |

### GitHub
| Ne | Nerede |
|---|---|
| API'ye HTTP isteği, JSON, hata kodları | [github_takip.py:90](github_takip.py#L90) `commitleri_getir()` |
| Depo adresini anlama (regex) | [github_takip.py:45](github_takip.py#L45) `depo_adini_coz()` |
| Commit mesajında "Adım N" bulma | [github_takip.py:68](github_takip.py#L68) `ADIM_KURALI` |
| Tekrarsız kaydetme (`INSERT OR IGNORE`) | [veritabani.py:973](veritabani.py#L973) `commitleri_kaydet()` |
| 30 saniye bekleme kuralı | [app.py:626](app.py#L626) `github_yenile()` |

### Güvenlik
| Ne | Nerede |
|---|---|
| Gizli anahtar `.env`'de, koda yazılmıyor | [app.py:74](app.py#L74) `gizli_anahtari_hazirla()` |
| Çerez ayarları | [app.py:99](app.py#L99) |
| CSRF jetonu ve kontrolü | [app.py:140](app.py#L140) `csrf_jetonu()`, [app.py:152](app.py#L152) `csrf_kontrol()` |
| HTML kaçışı (XSS'e karşı) | [app.py:220](app.py#L220) `html_e_cevir()`, [app.py:243](app.py#L243) `guvenli_markdown()` |

### Testler
| Ne | Nerede |
|---|---|
| Ortak hazırlık (geçici veritabanı, sahte yapay zekâ) | [tests/conftest.py](tests/conftest.py) |
| Saldırı testleri (en etkileyici dosya) | [tests/test_guvenlik.py](tests/test_guvenlik.py) |
| Gizlilik testleri | [tests/test_ogretmen.py:85](tests/test_ogretmen.py#L85) |
| Bildirim ve CSV testleri | [tests/test_bildirim_ve_disa_aktarma.py](tests/test_bildirim_ve_disa_aktarma.py) |
| Kod inceleme testleri | [tests/test_kod_inceleme.py](tests/test_kod_inceleme.py) |
| Koyu tema testleri | [tests/test_tema.py](tests/test_tema.py) |
| Ana sayfa testleri (devam kartı, proje fikri) | [tests/test_ana_sayfa.py](tests/test_ana_sayfa.py) |
| Adım düzenleme testleri | [tests/test_adim_duzenleme.py](tests/test_adim_duzenleme.py) |
| Rozet testleri | [tests/test_rozetler.py](tests/test_rozetler.py) |
| Koça soru sor testleri | [tests/test_koca_soru.py](tests/test_koca_soru.py) |
| Profil testleri (şifre, seri, takvim) | [tests/test_profil.py](tests/test_profil.py) |
| Duyuru ve yazdırma testleri | [tests/test_duyurular.py](tests/test_duyurular.py) |
| Sınıf istatistikleri testleri | [tests/test_sinif_istatistik.py](tests/test_sinif_istatistik.py) |

### Tasarım
| Ne | Nerede |
|---|---|
| Renk değişkenleri + koyu tema | [static/style.css](static/style.css) (dosyanın başı) |
| Tema düğmesi ve hatırlama (`localStorage`) | [templates/taban.html](templates/taban.html) |
| Yazdır / PDF (`@media print`, `window.print()`) | [static/style.css](static/style.css) (dosyanın sonu), [templates/yol_haritasi.html](templates/yol_haritasi.html) |

---

## 5. Veritabanı şeması (11 tablo)

```
kullanicilar ──< yol_haritalari ──< adimlar ──< ipuclari
     │                  │              ├──< koc_sorulari
     │                  │              ├──< kod_incelemeleri
     │                  │              └──< ogretmen_yorumlari >── kullanicilar (öğretmen)
     │                  └──< commitler (adim_id ile adıma da bağlanabilir)
     │
     ├──< siniflar (ogretmen_id) ──< duyurular
     └──< sinif_uyeleri >── siniflar        ("──<" = bire-çok)
```

- **Bire-çok:** Bir yol haritasının çok adımı var; adımda `yol_haritasi_id` yabancı anahtarı tutuluyor.
- **Çoka-çok:** Bir sınıfta çok öğrenci, bir öğrencinin de çok sınıfı olabilir. Bu yüzden `sinif_uyeleri` ara tablosu var ve birincil anahtarı `(sinif_id, ogrenci_id)` ikilisi.

---

## 6. Hocanın sorabileceği sorular

**Neden SQLite?**
Ayrı bir sunucu kurmak gerekmiyor, Python'la birlikte geliyor, bütün veri tek bir dosyada (`kodkoc.db`) duruyor. Tek bilgisayarda çalışan bir uygulama için yeterli. 9. haftada canlıya geçerken PostgreSQL desteği ekledim; ayrıntısı 10. bölümde.

**Neden hazır bir ORM (ör. SQLAlchemy) kullanmadın?**
SQL'i öğrenmek istedim. Bütün sorgular açık yazılı: `JOIN`, `GROUP BY`, `HAVING` hepsi görünüyor.

**Yapay zekâ kuralı çiğneyip yine de kod verirse?**
İki katman var. Önce talimatta kesin kural var. Yine de kod gelirse iki filtre devreye giriyor:
- `kod_bloklarini_temizle()`: ```` ``` ```` ile yazılmış blokları siliyor.
- `satir_ici_kodu_temizle()`: Cümle içinde `` `...` `` ile yazılmış kod satırlarını siliyor. `input()`, `while`, `"3"`, `==` gibi kavram adları kalıyor; boşluk, `=` ya da içi dolu parantez içeren her şey (ör. `` `gorevler.pop(int(no) - 1)` ``) siliniyor.

**API anahtarı nerede duruyor?**
`.env` dosyasında. `.gitignore` sayesinde GitHub'a yüklenmiyor. Koda hiçbir anahtar yazılmadı; oturum için gereken gizli anahtar da ilk açılışta rastgele üretilip `.env`'e yazılıyor.

**Şifreler nasıl saklanıyor?**
Açık metin olarak değil, **hash** olarak. Hash tek yönlü: hash'ten şifre geri bulunamaz. Giriş yapılırken girilen şifrenin hash'i kayıtlı hash'le karşılaştırılıyor.

**Biri adres çubuğundaki sayıyı değiştirip başkasının yol haritasını açabilir mi?**
Hayır. Her sorguda `AND kullanici_id = ?` koşulu var; başkasının kaydı "bulunamadı" (404) döndürüyor. Bunun testi de var: `test_herkes_sadece_kendi_verisini_gorur`.

**Öğretmen herkesi görebiliyor mu?**
Hayır. Sadece kendi sınıfına **kendi isteğiyle kodla katılmış** öğrencileri görüyor. Erişimi öğretmen değil öğrenci veriyor. Bu yüzden biri kendini "öğretmen" diye kaydetse bile kimsenin verisini göremez. Öğrenci sınıftan ayrılınca erişim hemen kapanıyor.

**CSRF nedir, nasıl korudun?**
Ben KodKoç'a giriş yapmışken kötü niyetli başka bir site tarayıcım üzerinden gizlice form gönderebilir. Her formda, başka sitenin bilemeyeceği rastgele bir jeton var; jeton tutmazsa istek reddediliyor. Ek olarak çerez `SameSite=Lax`.

**SQL enjeksiyonu?**
Kullanıcıdan gelen hiçbir değer SQL metnine doğrudan yapıştırılmıyor; hepsi `?` yer tutucularıyla veriliyor. Test: `test_sql_enjeksiyonu_ise_yaramaz`.

**Şablonda `| safe` kullanmışsın, bu tehlikeli değil mi?**
`| safe` sadece önceden `html.escape` ile temizlenmiş metne uygulanıyor (`html_e_cevir`, `guvenli_markdown`). Öğrencinin yazdığı not ve proje gibi metinler `safe` olmadan gösteriliyor; Jinja onları otomatik kaçırıyor. Test: `test_html_kacisi_xss`.

**Form gönderildikten sonra neden yönlendirme (redirect) yapıyorsun?**
Post/Redirect/Get kalıbı. Sayfa yenilenince form tekrar gönderilmiyor; yoksa yapay zekâya boşuna ikinci kez istek giderdi.

**Gemini çökerse ya da yoğunsa?**
Önce listedeki diğer modeli deniyor. Hepsi yoğunsa 2 sn, sonra 4 sn bekleyip tekrar deniyor. Yine olmazsa Türkçe bir mesaj gösteriyor. Yanlış anahtar gibi kalıcı hatalarda boşuna beklemiyor.

**Testler gerçek yapay zekâyı ya da GitHub'ı çağırıyor mu?**
Hayır. `monkeypatch` ile sahte fonksiyonlar konuyor. Testler hızlı, ücretsiz ve her seferinde aynı sonucu veriyor. Her test kendi geçici veritabanını kullanıyor.

**Eski kayıtlar yeni sürümde ne oldu?**
Program açılınca `hazirla()` eksik tabloları ve sütunları ekliyor (göç / migration), veriler silinmiyor. Kullanıcı girişinden önceki kayıtlar ilk kayıt olan kişinin hesabına aktarılıyor.

**CSV'de neden noktalı virgül var, dosyanın başındaki görünmez karakter ne?**
Türkçe Excel ondalık sayılar için virgül kullanıyor, bu yüzden ayraç olarak `;` seçtik. Baştaki görünmez karakter **BOM**: Excel'e dosyanın UTF-8 olduğunu söylüyor, yoksa ğ, ş, ı bozuk görünür.

**"Kodumu incelet" öğrenciye cevabı vermiş olmuyor mu?**
Hayır. Talimat düzeltilmiş kod yazmayı ve öğrencinin satırlarını düzeltip tekrar yazmayı açıkça yasaklıyor. Yapay zekâ sadece satır numarasını söylüyor ve bir soru soruyor; düzeltmeyi öğrenci yapıyor. Yine de kod gelirse iki filtre (blok ve satır içi) siliyor. Her adımda 5 hak var; hem kotayı koruyor hem öğrenciyi her denemede incelemeye göndermek yerine düşünmeye itiyor. Öğretmen de gönderilen kodu görüyor.

**Öğrencinin kodunda `<script>` olursa sayfa bozulur mu?**
Hayır. Kod `<pre>` içinde Jinja'nın otomatik kaçırmasıyla gösteriliyor; düz metin olarak görünüyor. Test: `test_koddaki_html_calismaz`.

**Adım silince "Adım 4" neden "Adım 3" oluyor, GitHub eşlemesi bozulmuyor mu?**
Silmeden sonra `UPDATE adimlar SET sira = sira - 1 WHERE ... sira > silinen` ile arkadaki adımlar bir öne kayıyor; numaralarda boşluk kalmıyor. Başlıktaki numara da yazıdan değil `sira` sütunundan geliyor (`adim_basligi` filtresi). Commit'ler adıma `adim_id` ile bağlı olduğu için eski eşlemeler bozulmuyor. Silinen adımın commit'leri silinmiyor, çünkü GitHub'da hâlâ varlar; sadece "adıma bağlı değil" oluyorlar. Son adım silinemiyor.

**Rozetler nasıl hesaplanıyor, ayrı bir tabloda mı?**
Hayır, saklanmıyor; her seferinde mevcut verilerden **hesaplanıyor**. Böylece tutarsız olamaz (ör. adımı geri alınca rozet de gider). Tek bir sorguda 8 alt sorgu var. Örneğin "ipucu almadan biten adım" için `NOT EXISTS (SELECT 1 FROM ipuclari WHERE adim_id = a.id)` kullanılıyor.

**"Koça soru sor" ile "ipucu" arasındaki fark ne?**
İpucu "takıldım, çözüme yaklaştır" demek; 3 seviyede gittikçe açılıyor. Soru ise "bu kavram ne, neden böyle?" gibi bir anlama sorusu. Koç benzetmeyle anlatıyor (liste = alışveriş listesi), sonunda öğrenciye küçük bir soru soruyor. İkisinde de kod yok; kod istenirse nazikçe reddediyor (gerçek Gemini ile denendi).

**Yapay zekâ önceki soruları nasıl hatırlıyor?**
Hatırlamıyor; yapay zekânın kendi hafızası yok. Her yeni soruda, o adımdaki son 3 soru-cevabı veritabanından okuyup mesajın içine biz koyuyoruz. Hepsini değil 3 tanesini gönderiyoruz, mesaj gereksiz uzamasın diye.

**Şifre değiştirirken neden eski şifreyi soruyorsun?**
Öğrenci bilgisayarını açık bırakırsa, başkası oturumu kullanıp şifreyi değiştirerek hesabı ele geçiremesin diye. Eski şifre yanlışsa hiçbir şey değişmiyor. Yeni şifre de yine hash olarak saklanıyor.

**Çalışma serisi nasıl hesaplanıyor?**
Önce veritabanından öğrencinin bir şey yaptığı günleri alıyorum: beş tablodan `UNION ALL` ile birleştirip `SUBSTR(zaman, 1, 10)` ile saati atıyorum (önceden `DATE()` kullanıyordum; PostgreSQL'de metin yerine tarih tipi döndürdüğü için değiştirdim). Sonra Python'da bugünden geriye doğru boş bir güne gelene kadar sayıyorum. Bugün henüz çalışmadıysa seri dünden sayılıyor; gün bitmeden seri "0" görünmesin diye. En uzun seri için her serinin ilk gününü (önceki günü boş olan gün) bulup ileri doğru sayıyorum. Günler bir **küme** (`set`) içinde, "bu gün var mı?" sorusu çok hızlı.

**Duyuruların okunup okunmadığını nasıl takip ediyorsun? Her duyuru için ayrı kayıt mı var?**
Hayır. Duyurular sırayla eklendiği için id'leri hep artıyor. Her öğrencide tek bir sayı tutuyorum: `son_okunan_duyuru`, yani "bu id'ye kadar hepsini gördü". Bundan büyük id'li duyurular yeni. Öğrenci "Sınıfım"ı açınca bu sayı, görebildiği en büyük duyuru id'sine çekiliyor. Önce duyurular "yeni" bilgisiyle okunuyor, sonra okundu yapılıyor; sıra ters olsaydı hiçbiri "Yeni" görünmezdi. Öğretmen yorumlarında ise her yorumun kendi `okundu` sütunu var. İki farklı yol da çalışıyor; duyurularda tek sayı daha az yer kaplıyor.

**Yazdır düğmesi PDF'i nasıl oluşturuyor?**
PDF'i ben oluşturmuyorum; tarayıcının kendi yazdırma penceresini açıyorum (`window.print()`). Orada "PDF olarak kaydet" seçilebiliyor. Kâğıtta neyin görüneceğini CSS'teki `@media print` kuralları belirliyor: menü, düğmeler ve formlar gizleniyor, öğrencinin notları görünüyor, biten adımlara "✓ tamamlandı" ekleniyor. Koyu tema seçili olsa bile renk değişkenleri beyaz kâğıda göre yeniden tanımlanıyor; mürekkep boşa gitmiyor ve yazı okunuyor.

**Sınıf grafiklerini hangi kütüphaneyle çizdin?**
Kütüphane kullanmadım. Her çubuk bir `<span>`; boyunu `style="width: 40%"` (yatay) ya da `style="height: 40%"` (dikey) belirliyor. Yüzdeyi Python'da hesaplıyorum: dağılımda sınıf mevcuduna göre, günlük grafikte en kalabalık güne göre (o gün tam boy). Veritabanından `DISTINCT` ile "hangi öğrenci hangi gün çalıştı" çiftlerini alıyorum; aynı öğrenci bir günde 5 iş yapsa bile bir kez sayılıyor. Ekran okuyucular için aynı sayılar görünmez bir tabloda da var.

**Proje fikirlerini nasıl alıyorsun, yapay zekâ saçma bir şey döndürürse?**
Yapay zekâdan cevabı **JSON** olarak istiyorum (`response_mime_type="application/json"`), sonra `json.loads` ile listeye çeviriyorum. Dışarıdan gelen veriye güvenmiyorum: liste mi, her öğede `baslik` ve `aciklama` metin olarak var mı, en fazla 3 tane mi, çok uzun mu, hepsini kontrol ediyorum. Bozuksa `ValueError` fırlatılıyor ve öğrenci "bir kez daha dener misin?" mesajı görüyor.

**"Bu fikri seç" neden POST değil de GET formu?**
Hiçbir şeyi değiştirmiyor, sadece ana sayfayı formu dolu olarak açıyor (`/?proje=...`). Kural: GET okumak için, POST değiştirmek için. GET olduğu için CSRF jetonu da gerekmiyor.

**Koyu tema nasıl çalışıyor?**
Bütün renkler `style.css`'in başında **CSS değişkenleri** (`--zemin`, `--vurgu`...) olarak bir kez tanımlı. Koyu tema sadece bu değişkenlerin değerlerini değiştiriyor. Bilgisayar koyu moddaysa otomatik açılıyor (`prefers-color-scheme`); üstteki düğmeyle elle de seçilebiliyor ve seçim tarayıcıda (`localStorage`) hatırlanıyor. Bütün yazı/zemin çiftlerinin kontrast oranı erişilebilirlik standardını (WCAG, en az 4,5) geçiyor. Bir test de CSS'te değişken dışında renk kodu kalmadığını kontrol ediyor.

**Öğretmen öğrencinin sayfasına bakınca yorum "okundu" oluyor mu?**
Hayır. Sadece öğrenci kendi sayfasını açınca okundu sayılıyor. Bunun da testi var: `test_ogretmenin_baktigi_sayfa_okundu_yapmaz`.

---

## 7. Bilinen sınırlamalar (sorulursa dürüstçe söyle)

- **Türkçe arama:** Arama `LOWER()` ile büyük/küçük harfe duyarsız, ama SQLite'ın `LOWER()`'ı sadece İngilizce harfleri çeviriyor. "ışık" ile "IŞIK" eşleşmeyebilir.
- **Şifre kilidi kullanıcı adına göre:** Biri başkasının adıyla 5 kez yanlış şifre girerse o kişi 10 dakika giriş yapamaz. IP'ye göre yapmadım, çünkü okulda bütün sınıf aynı IP'den bağlanıyor.
- **Ücretsiz sunucu uykuya geçiyor:** Render'ın ücretsiz planında site 15 dakika kimse girmezse uyuyor; ilk açılış 30-60 saniye sürebilir. Sunumdan önce siteyi bir kez aç.
- **GitHub:** Sadece **herkese açık** depolarla çalışıyor. Anahtarsız kullanımda saatte 60 istek sınırı var.
- **Gemini:** Ücretsiz kotası var ve bazen yoğunluk hatası veriyor.
- **Bildirim:** Sadece site içinde çalışıyor; e-posta ya da telefon bildirimi yok.

---

## 8. Bu hafta öğrendiğim kavramlar (kontrol listesi)

**Veritabanı:**
- [ ] SQLite, tablo, sütun, satır, veri tipleri
- [ ] Birincil anahtar, yabancı anahtar, `UNIQUE`, `NOT NULL`, `DEFAULT`
- [ ] Bire-çok ve çoka-çok ilişki, ara tablo, bileşik birincil anahtar
- [ ] `CREATE`, `INSERT`, `SELECT`, `UPDATE`, `DELETE`, `ALTER TABLE`
- [ ] `JOIN` / `LEFT JOIN`, `GROUP BY`, `HAVING`, `COUNT` / `SUM` / `MAX`, `LIKE`, `EXISTS`, `IN (...)`
- [ ] Alt sorgu ve ilişkili alt sorgu, `UNION ALL`, `DATE()`
- [ ] İşlem (transaction): `commit`
- [ ] Göç (migration)

**Web:**
- [ ] Flask route, GET / POST
- [ ] URL'den değer alma (`<int:harita_id>`)
- [ ] `redirect` ve Post/Redirect/Get kalıbı
- [ ] HTTP durum kodları: 200, 302, 400, 404, 405
- [ ] Jinja şablon kalıtımı (`extends`, `block`), `include`, kendi filtren (`template_filter`), `flash`
- [ ] Oturum (session) ve çerez (cookie)
- [ ] `before_request`, `g`
- [ ] Dosya indirme: `send_file`, `Content-Disposition`
- [ ] CSS değişkenleri, `prefers-color-scheme`, `localStorage`, renk kontrastı (erişilebilirlik)

**Güvenlik:**
- [ ] Şifre hash'leme
- [ ] Kimlik doğrulama ile yetkilendirme farkı, rol tabanlı yetki
- [ ] SQL enjeksiyonu, XSS, CSRF
- [ ] `.env` ve gizli anahtarlar
- [ ] Sunucu tarafı doğrulama

**Dış servisler ve dosyalar:**
- [ ] API, HTTP isteği ve başlıkları, JSON
- [ ] İstek sınırı (rate limit)
- [ ] Hata yönetimi ve tekrar deneme
- [ ] UTC ve yerel saat
- [ ] CSV, karakter kodlaması (UTF-8, BOM), `io.StringIO` (bellekte dosya)

**Python ve test:**
- [ ] Dekoratör
- [ ] Düzenli ifade (regex)
- [ ] Fonksiyonu parametre olarak geçirmek
- [ ] Kalıtım
- [ ] pytest: `assert`, fixture, `parametrize`, `monkeypatch`, sahte nesne (mock)

---

## 9. Haftalara göre ilerleme

| Hafta | Ne yapıldı |
|---|---|
| 6 | Terminal sürümü: proje anlatımından yol haritası, `.md` dosyasına kaydetme |
| 7 | Flask web arayüzü, tasarım, adımlar ayrı kutularda |
| 8 | Veritabanı, ilerleme, ipucu, not, kullanıcı girişi, öğretmen paneli, GitHub takibi, yorumlar ve bildirim, Excel'e aktarma, kodumu incelet, proje fikri, kaldığın yerden devam, adım düzenleme, rozetler, koça soru sor, profil ve çalışma serisi, sınıf duyuruları, sınıf istatistikleri, yazdır/PDF, koyu tema, CSRF, 183 otomatik test |
| 9 | Canlıya hazırlık: canlı mod, öğretmen davet kodu, kişi başı ve site geneli yapay zekâ sınırı, şifre deneme sınırı, güvenlik başlıkları, hata sayfası. PostgreSQL desteği (aynı kod iki veritabanıyla), SQLite'tan PostgreSQL'e taşıma betiği, Render kurulum dosyası, sağlık kontrolü, git. 212 test (PostgreSQL'de de geçiyor) |

---

## 10. 9. hafta: Canlıya geçiş

### Tek cümlede
KodKoç artık herkesin kendi bilgisayarında değil, **tek bir sunucuda ortak** çalışabiliyor. Bunun için önce "herkes aynı siteyi kullanınca ne bozulur?" sorusunu sordum ve o açıkları kapattım, sonra veritabanını **PostgreSQL**'e bağlanabilir hale getirdim.

### Hangi özellik kodda nerede?
| Ne | Nerede |
|---|---|
| Canlı mod (`KODKOC_CANLI=1`) ve ayarlar | `app.py` başı: `CANLI`, `OGRETMEN_KODU`, `GUNLUK_YZ_SINIRI`, `GUNLUK_TOPLAM_YZ_SINIRI` |
| Gemini anahtarı siteden değiştirilemez | `app.py` → `anahtar_kaydet()` (canlıda 404) |
| Öğretmen davet kodu | `app.py` → `kayit()`; `secrets.compare_digest` ile karşılaştırma |
| Günlük yapay zekâ sınırı | `app.py` → `yz_kotasi_doldu()`, `site_kotasi_doldu()`; `veritabani.py` 16. bölüm (`yz_kullanimi` tablosu, UPSERT) |
| Şifre deneme sınırı | `app.py` → `giris()`; `giris_denemeleri` tablosu |
| Güvenlik başlıkları, HSTS, ProxyFix | `app.py` → `GUVENLIK_BASLIKLARI`, `guvenlik_basliklari_ekle()` |
| SQLite / PostgreSQL seçimi | `veritabani.py` → `POSTGRES`, `Baglanti` sınıfı, `postgres_sql()` |
| Veri taşıma | `tasima.py` |
| Sunucu kurulumu | `render.yaml`, `Procfile`, `.env.example`, `/saglik` |
| Testler | `tests/test_canli.py`, `tests/test_tasima.py` |

### Hocanın sorabileceği sorular

**Yerelde çalışan bir uygulamayı canlıya almak neden sadece "yüklemek" değil?**
Yerelde tek kullanıcı vardı ve bilgisayar ona aitti. Canlıda herkes aynı sunucuyu kullanıyor. Örneğin eskiden ana sayfadaki form API anahtarını `.env`'e yazıyordu; canlıda bu, siteye giren herhangi birinin **herkesin kullandığı anahtarı** değiştirebilmesi demekti. Aynı şekilde herkes kendini öğretmen yapabiliyordu ve biri ortak Gemini kotasını tek başına bitirebiliyordu.

**Neden PostgreSQL? SQLite yetmez miydi?**
Ücretsiz sunucuların çoğunda dosyalar her yeniden başlatmada siliniyor; `kodkoc.db` dosyası, yani bütün veriler giderdi. PostgreSQL ayrı çalışan bir veritabanı **sunucusu**; programımız ona internet üzerinden bağlanıyor ve veriler orada kalıcı. Ayrıca aynı anda çok kişinin yazmasına SQLite'tan daha uygun.

**Bütün SQL'i yeniden mi yazdın?**
Hayır. Sorguların çoğu iki veritabanında aynı. Farklı olanlar için `Baglanti` sınıfı yazdım; kodun geri kalanı hangi veritabanının kullanıldığını bilmiyor. `postgres_sql()` fonksiyonu `?` yer tutucularını `%s`'e, `:k`'yi `%(k)s`'e çeviriyor. Tırnak içindeki metinlere ve `--` yorumlarına dokunmuyor (yoksa `'10:00:00'` içindeki `:00` bozulurdu; bunun testi var). Farklı olan birkaç yeri ise iki veritabanında da çalışan yazımlara çevirdim:
- `lastrowid` → PostgreSQL'de `RETURNING id` (`ekle()` metodu)
- `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`
- İki değerli `MAX(a, b)` → PostgreSQL'de `GREATEST(a, b)`
- `DATE()` → `SUBSTR(..., 1, 10)`
- `COLLATE NOCASE` → `LOWER()` ve `LOWER(kullanici_adi)` üzerine `UNIQUE` indeks
- `GROUP BY a.id` → PostgreSQL seçilen bütün tabloların gruplamada olmasını istiyor: `GROUP BY a.id, k.id, y.id`

**Bunun çalıştığını nereden biliyorsun?**
Bütün testleri gerçek bir PostgreSQL 17 üzerinde de çalıştırdım; hepsi geçti. Testleri PostgreSQL ile çalıştırmak için `TEST_DATABASE_URL` veriliyor; testler bu durumda her testten önce tabloları `TRUNCATE ... RESTART IDENTITY` ile boşaltıyor.

**Bağlantı havuzu (connection pool) nedir?**
Uzaktaki bir veritabanına bağlanmak (şifreli bağlantı kurmak) her seferinde zaman alıyor. Havuz birkaç bağlantıyı açık tutuyor; bir sorgu bitince bağlantı kapatılmıyor, havuza geri veriliyor ve sonraki sorgu onu kullanıyor. Kopmuş bir bağlantı verilmeden önce kontrol ediliyor.

**Bir kullanıcı çok hesap açıp yapay zekâ sınırını aşarsa?**
İki sınır var: kişi başı (günde 40) ve bütün site için (ör. günde 400). Site sınırı dolunca yeni hesaplar da kullanamıyor. Başarısız istekler haktan düşmüyor. Kayıtlara IP başına sınır koymadım: okulda bütün sınıf aynı IP'den çıkıyor, ders başında herkes kayıt olurken engellenirdi.

**Şifreyi deneye deneye bulmayı nasıl engelledin?**
10 dakika içinde aynı kullanıcı adına 5 yanlış şifre girilirse, doğru şifre girilse bile 10 dakika giriş reddediliyor (429 "çok fazla istek" kodu). Doğru girişte sayaç sıfırlanıyor; eski denemeler tablodan siliniyor ki tablo sonsuza kadar büyümesin.

**Gizli anahtarlar sunucuda nerede?**
Kodda ya da GitHub'da değil, sunucunun **ortam değişkenlerinde** (environment variables). `render.yaml`'da `sync: false` yazanlar kurulumda soruluyor; `FLASK_SECRET_KEY`'i Render kendisi rastgele üretiyor. Canlıda `FLASK_SECRET_KEY` yoksa program bilerek başlamıyor: her açılışta yeni anahtar üretilseydi herkesin oturumu kapanırdı.

**Güvenlik başlıkları ne işe yarıyor?**
Tarayıcıya "bu siteyi nasıl korumalısın" diyor. `Content-Security-Policy` sayfanın sadece izin verilen yerlerden betik ve yazı tipi yüklemesine izin veriyor, `frame-ancestors 'none'` KodKoç'un başka bir sitenin içine gizlice gömülmesini engelliyor, `Strict-Transport-Security` tarayıcıya "bu siteye hep HTTPS ile gel" diyor.

**ProxyFix neden gerekli?**
Render'da HTTPS'i önündeki ara sunucu çözüyor ve isteği uygulamaya düz http olarak iletiyor. ProxyFix, ara sunucunun eklediği başlıkları okuyup Flask'a "aslında bağlantı HTTPS, ziyaretçinin adresi bu" diyor. Sadece canlıda açık; yerelde bu başlıklara güvenmek yanlış olurdu, çünkü herkes istediği başlığı gönderebilir.

**Saatler neden önemli?**
Sunucular genelde dünya saatiyle (UTC) çalışıyor; Türkiye 3 saat ileride. "Bugün"ü yanlış hesaplasaydık gece 00:00-03:00 arası yapılan çalışmalar önceki güne yazılır, seri bozulurdu. Program açılırken saat dilimini `Europe/Istanbul` yapıyorum.

### Bu hafta öğrendiğim kavramlar
- [ ] Yerel uygulama ile canlı (çok kullanıcılı) uygulama farkı
- [ ] Ortam değişkenleri, gizli anahtar yönetimi
- [ ] PostgreSQL, bağlantı adresi (`DATABASE_URL`), bağlantı havuzu
- [ ] `RETURNING`, `ON CONFLICT` (UPSERT), `GREATEST`, `TRUNCATE`, indeks
- [ ] İşlemi geri alma (`rollback`): PostgreSQL hatadan sonra rollback olmadan yeni komut kabul etmiyor
- [ ] Kaba kuvvet (brute force) saldırısı ve deneme sınırı, kota
- [ ] HTTPS, güvenlik başlıkları (CSP, HSTS), ara sunucu (proxy)
- [ ] gunicorn, worker, sağlık kontrolü, `render.yaml`
- [ ] git: depo, `.gitignore`, commit
