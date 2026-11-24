# Günlük Pazarlama Brifingi — Boyer Hukuk Bürosu · 2026-11-24

> **Bu bir örnek çıktıdır.** Sistemin her sabah Slack'e ve e-postaya gönderdiği
> brifingin birebir biçimi. **AI görünürlüğü** (Google AI Mode, ABD konumu, Türkçe) ve
> **site kontrolleri**, floridaturkavukat.com için 24 Kasım 2026'da yapılmış **gerçek
> ölçümlerdir**. Search Console, Google yorumları ve ChatGPT / Gemini / Perplexity /
> Claude sonuçları ilgili API anahtarları eklendiğinde dolar; burada uydurma rakam yoktur.
> "Viral videolar" tablosu **temsilîdir**.

## ✅ Otomatik yapıldı
- 5 AI sorusu test edildi; firma 4 cevapta geçiyor, 1 cevapta hiç yok
- Site denetlendi: başlık, açıklama, H1, schema, `llms.txt`, `robots.txt` ve reklam uyarısı bağlantısı
- 10 rakip büro izleme listesine eklendi (sayfa değişikliği takibi ilk otomatik çalıştırmadan itibaren başlar)

## 📝 Onayına hazır taslaklar

**1. Uyumluluk düzeltmesi: "Avukat Reklamları" bağlantısı boş (~10 dk) · öncelik: yüksek**
Sitenin alt bilgisindeki "Avukat Reklamları" bağlantısı `#` adresine gidiyor ve ana sayfada tam bir reklam uyarısı metni görünmüyor. Önerilen sayfa `/avukat-reklami/`:
> *Bu web sitesi Florida Barosu kuralları kapsamında avukat reklamıdır (Attorney Advertising). Sitedeki bilgiler genel bilgilendirme amaçlıdır, hukuki tavsiye değildir ve avukat-müvekkil ilişkisi doğurmaz. Geçmiş sonuçlar gelecekteki sonuçları garanti etmez. İstanbul'daki nokta müvekkil destek ofisidir; büro Türk hukuku kapsamında hizmet vermez.*

Metni yayından önce büronun sorumlu avukatına onaylat.

**2. GEO düzeltmesi: "Amerika'da Türk göçmenlik avukatı" sorgusunda yokuz (~25 dk)**
Google AI Mode bu soruda Gozel Law Firm, Yildiz Law Firm ve Alaz Law'u öneriyor. Cevap "göçmenlik federal bir alan, avukat hangi eyalette olursa olsun uzaktan çalışabilir" diye başlıyor. Bizim sitede bu bilgi açıkça yazmadığı için Florida dışı aramalarda elenmiş olabiliriz.
- `/avukatlik-alanlari/amerika-gocmenlik-avukati/` sayfasının en üstüne şu cevap bloğu eklenebilir (**önce doğrula:** Florida dışındaki ve Türkiye'deki müvekkillere uzaktan göçmenlik hizmeti veriyor muyuz?):
  > *Boyer Hukuk Bürosu, ABD göçmenlik başvurularında Türkçe iletişim desteği verir. Göçmenlik hukuku federal olduğu için Florida'da, başka eyaletlerde ya da Türkiye'de yaşayan müvekkillerle görüşmeler online yapılabilir. E-2, EB-5, EB-1/EB-2/EB-3, L-1, H-1B, aile ve evlilik yoluyla Green Card ile vatandaşlık başvurularında çalışırız.*
- Aynı soru-cevabı SSS sayfasına `FAQPage` schema ile ekle.

**3. "Amerika'da Türk avukat" sorgusunda 9 firma arasında 8. sıradayız (~40 dk)**
Florida sorgularında güçlüyüz, ülke genelindeki sorguda geride kalıyoruz. "Amerika'da Türk Avukat" başlıklı bir ana sayfa öner:
- Başlık (≤60 karakter): *Amerika'da Türk Avukat: Türkçe Hukuk Desteği | Boyer*
- H2 başlıkları: Hangi konularda Türkçe destek veriyoruz · Göçmenlik (her eyalette) · Florida ve New York davaları · Uluslararası boşanma, velayet ve miras · Türkiye mahkeme kararlarının ABD'de tanınması · Ofislerimiz · SSS
- AI cevabında kaynak olarak gösterilen siteler: Yeşilkart Forum ve Gozel Law Firm. Yeşilkart Forum'da faydalı ve reklam içermeyen cevaplarla görünür olmayı değerlendir.

**4. Reel: "E-2 başvurusunda en sık 3 hata" (~20 dk çekim)**
Neden: Google AI Mode, "Florida E-2 vizesi Türkçe avukat" sorusunda bizi **1. sırada** öneriyor. Güçlü olduğumuz konuyu videoyla destekleyelim. Format, viral-radar'ın o gün en çok öne çıkan bulduğu "yaygın hata" kalıbından seçildi (bu örnekte temsilî).
Hook: E-2 başvurusunda en sık yapılan 3 hata
- 0–3 sn: Avukat kameraya bakıyor. Ekran yazısı: "E-2'de 3 hata"
- 3–10 sn: 1) Yatırımın "riskte" olmaması 2) İş planının zayıf kalması 3) Fonun kaynağının belgelenmemesi
- 10–15 sn: "Dosyanız farklı olabilir; ilk görüşmede durumunuzu birlikte değerlendirelim"
- Açıklama: E-2 yatırımcı vizesi sürecini Türkçe anlatıyoruz. Bu video genel bilgilendirmedir, hukuki tavsiye değildir. Avukat Reklamı. #e2vizesi #amerikadaturkler #amerikadasirketkurmak #floridaturkavukat

**5. Teknik SEO: `robots.txt` boş (~5 dk)**
`floridaturkavukat.com/robots.txt` adresi içerik döndürmüyor; site haritası da gösterilmiyor. Şu üç satırı ekle:
```
User-agent: *
Allow: /
Sitemap: https://floridaturkavukat.com/sitemap_index.xml
```
Site haritasının gerçek adresini (`/sitemap_index.xml` ya da `/sitemap.xml`) eklemeden önce kontrol et. `llms.txt` var (7 KB). İlk paragrafına "Türkçe iletişim desteği" ve 7 ofis bilgisini ekle.

## 🎨 Sadece senin kararın
- **Konumlanma:** Ülke genelindeki Türk göçmenlik pazarında AI'ların önerdiği firmalar uzaktan çalışan göçmenlik büroları. (a) Ülke geneline uzaktan göçmenlik vurgusuyla girelim (b) Florida + uluslararası aile/miras nişinde derinleşelim (c) ikisi, ayrı sayfalarla
- **Board Certified farkı:** Google AI Mode, Boyer'i anlatırken "Florida Barosu tarafından uluslararası hukuk alanında sertifikalı" ifadesini kullanıyor. Yani AI'lar bu farkı zaten görüyor. (a) Tüm uluslararası hukuk sayfalarında ve videolarda öne çıkar (b) yalnızca Hakkımızda ve avukat sayfasında kalsın
- **Ön görüşme teklifi:** Yellow Law Group sitesinde "Ücretsiz Ön Değerlendirme" sunuyor. (a) Benzer bir ilk görüşme teklifi (b) ücretli ama net fiyatlı danışma (c) değişiklik yok

## 📊 Veriler

**AI görünürlüğü: Google AI Mode (24 Kasım, ABD, Türkçe)**

| Soru | Boyer | Önerilen firmalar (cevaptaki sırayla) |
|---|---|---|
| Florida E-2 yatırımcı vizesi Türkçe avukat | **1.** | Boyer · Yildiz Law · Alaz Law |
| Florida'da Türkçe konuşan boşanma avukatı | **2.** (kaynak olarak da gösteriliyor) | Sema Yildirim · Boyer |
| Florida'da Türk avukat | 4. (kaynak olarak da birden çok kez gösteriliyor) | Cem Tahir · Ozek · Barlas · Boyer · Sema Yildirim · Atilla Babacan |
| Amerika'da Türk avukat | 8. / 9 | Gozel · Grape · Yildiz · Relief · MC · CK · Yellow · Boyer · Onal |
| Amerika'da Türk göçmenlik avukatı | **yok** | Gozel · Yildiz · Alaz |

**Site kontrolleri (24 Kasım)**

| Kontrol | Durum |
|---|---|
| Ana sayfa başlığı ve açıklaması | ✅ var, uygun uzunlukta |
| H1 | ✅ 1 adet |
| Schema | ✅ Attorney, Organization, WebSite · ⚠️ ana sayfada FAQPage yok |
| `llms.txt` | ✅ var (7 KB) |
| `robots.txt` | ⚠️ boş, site haritası satırı yok |
| "Avukat Reklamları" bağlantısı | ❌ `#` adresine gidiyor |
| Blog | ✅ aktif (son yazılar: 16, 18 ve 23 Kasım) |

**Viral kısa videolar** *(temsilî örnek)*

| Kat | Platform | Hook | Format |
|---|---|---|---|
| 42x | youtube_shorts | Green Card mülakatında bu soruyu sakın böyle cevaplamayın | myth / mistake |
| 8x | youtube_shorts | 3 mistakes that get E-2 visas denied | list / myth |
| 0,3x | youtube_shorts | Amerika'da bir günüm: Florida'da market fiyatları | day in the life |

_Bu rapor bugün tahminen 120 dk elle çalışma yerine geçti._
