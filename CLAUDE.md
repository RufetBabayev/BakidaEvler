# BakıdaEvlər.az

Şəxsi istifadə üçün Android tətbiqi. Azərbaycandakı əmlak saytlarından Bakıda YENİ satış elanlarını toplayır və ev sahibi (mülkiyyətçi) / makler (vasitəçi) kimi ayırır. Play Store-a çıxmayacaq, APK telefona birbaşa yüklənəcək. Tətbiqdə görünən ad: "BakıdaEvlər.az". Kod qovluğunun adı ASCII-dir: `BakidaEvler`.

## Qovluq quruluşu

```
BakidaEvler/
├── CLAUDE.md
├── toplayici/            # Python toplayıcı (bütün kod burada)
│   ├── makler.py         # makler aşkarlama (eyni telefon → şübhəli makler)
│   ├── main.py           # giriş nöqtəsi: scraper-ləri işlədir, seen.json və data/ ilə işləyir
│   ├── scrapers/
│   │   └── bina.py       # hər sayt üçün ayrı fayl, eyni sahə formatı
│   ├── data/             # bina_YYYY-MM-DD_HHMM.json nəticələri
│   ├── seen.json         # görülmüş elan_id-lər (+ satıcı tipi/telefon keşi)
│   ├── requirements.txt
│   └── README.md
└── tetbiq/               # Expo tətbiqi (hələlik boş, yalnız README)
```

## Mərhələlər

1. **bina.az toplayıcısı** — BİTDİ (bax: aşağıdakı qeydlər)
2. Makler aşkarlama (eyni telefonla çoxlu elan) — BİRİNCİ VERSİYA HAZIRDIR (`toplayici/makler.py`)
3. Supabase bazası + GitHub Actions ilə avtomatik işləmə — KOD HAZIRDIR, işə salınma yoxlanılır (bax: Mərhələ 3 qeydləri)
4. Expo (React Native) tətbiqi — `tetbiq/`
5. Digər saytlar: tap.az, yeniemlak.az, emlak.az, vipemlak.az, rahatemlak.az, domik.az, korter.az
6. Push bildirişlər

## Texnologiyalar

Python 3, `requests`. Mərhələ 3-dən sonra Supabase, GitHub Actions; mərhələ 4-də Expo (React Native).

## Məhdudiyyətlər (pozma)

- Yalnız bina.az, yalnız Bakı, yalnız satış (kirayə və digər şəhərlər yox) — digər saytlar yalnız mərhələ 5-də.
- Cari mərhələdə tətbiq, baza, bulud yoxdur.
- Fayl/qovluq adları ASCII (ə, ı, ö, ü, ş, ç, ğ yox). JSON sahə adları və mətnlər Azərbaycanca ola bilər (UTF-8, `ensure_ascii=False`).
- Sorğular arası 2-4 san təsadüfi fasilə, normal brauzer User-Agent, bir işləmədə maksimum 3 siyahı səhifəsi.
- Login, captcha keçmə, qorunmanı aşma yoxdur. Bloklanma olsa DAYAN və istifadəçiyə de.
- Yüngül kitabxanalar (requests). Playwright/Selenium yalnız soruşandan sonra.
- Hər scraper `scrapers/<sayt>.py` olur, `SOURCE` və `fetch(known_ids, reveal_phone, max_pages, log)` verir; eyni sahə formatı.
- `BakidaEvler` qovluğundan kənarda fayl yaratma/dəyişmə.
- İstifadəçi proqramçı deyil: izahlar sadə və Azərbaycanca.
- Hər mərhələ bitəndə bu faylı yenilə.

## Mərhələ 1 qeydləri (bina.az)

- Sayt Next.js-dir. HTML əvəzinə daxili GraphQL (`POST https://bina.az/graphql`) işlədilir: siyahı (`itemsConnection`) və elan (`item`). Başlıq `X-Platform: desktop`.
- Kateqoriyalar: 1 = Mənzil (yeni+köhnə tikili), 5 = Həyət evi/Bağ evi. Sıralama `BUMPED_AT_DESC` (saytın "ən yeni" sırası; yenilənən elan yenidən yuxarı çıxır).
- Telefon siyahı/elan sorğusunda MASKALI gəlir: `(077) 710-16-●●`. Tam nömrə saytın `revealPhones` sorğusu ilə alınır (login/captcha yoxdur) — yalnız `--telefon` bayrağı ilə, yeni elanlar üçün.
- `paylaşılma_tarixi` sayt tərəfindən verilmir (null); `yenilənmə_tarixi` = `updatedAt`.
- DİQQƏT: bina.az-ın "ən yeni" siyahısı bump (yenilənmə) vaxtına görədir, köhnə elanlar da yuxarı çıxır; 75 elan ~3 dəqiqəni əhatə edir. Elan ID-ləri isə yaranma sırası ilə artır (təxminən dəqiqədə 1 ID).
- Ona görə iş rejimləri: ilk işləmə (və ya `--siyahi`) siyahıdan başlayır və `son_max_id` yadda saxlayır; sonrakı işləmələr `item(id)` ilə `son_max_id`-dən yuxarı ID-ləri bir-bir yoxlayır (8 ardıcıl boş ID-də dayanır, max 60 sorğu). Boş çıxan ID-lər (moderasiya) `gozleyen` siyahısında 150 ID müddətinə yenidən yoxlanılır. Yalnız dərc olunmuş, satış, Bakı, kateqoriya 1/2/3/5 elanlar saxlanır.
- `seen.json` quruluşu: `{"bina.az": {"son_max_id", "gozleyen", "elanlar": {id: {ilk_görülmə, satıcı_tipi, satıcı_adı, telefon}}}}`.

## Mərhələ 2 qeydləri (makler)

- Hər elana `telefon_elan_sayı` və `makler_nəticə` ("makler" / "şübhəli makler" / "ev sahibi") əlavə olunur. "Şübhəli" = mülkiyyətçi yazılıb, amma eyni telefonla 3+ elan.
- Telefon maskalıdır (son 2 rəqəm gizli), ona görə təsadüfi üst-üstə düşmə mümkündür. Dəqiqlik üçün `--telefon` ilə tam nömrə. Hələ real məlumatla yetərincə yoxlanmayıb: elan toplandıqca hədd (3) tənzimlənməlidir.
- Hazırda yalnız 3 "şübhəli" (Sea Breeze, korporativ hesab) tapılıb; saxta mülkiyyətçi nümunəsi hələ yoxdur.

## Mərhələ 3 qeydləri (Supabase + GitHub Actions)

- Supabase layihəsi: `bakidaevler` (ref `zlxvaztepmprydphxmwu`). Cədvəllər: `elanlar`, `toplayici_veziyyet` (`toplayici/schema.sql`). RLS açıq, siyasət yoxdur; yalnız `service_role` açarı yazır.
- GitHub repo: `RufetBabayev/BakidaEvler` (PRIVATE). İş axını: `.github/workflows/toplayici.yml`, hər 15 dəqiqə, yalnız Bakı vaxtı 08:00-22:45 (private repoda pulsuz limit ~2000 dəq/ay).
- Gizli açarlar GitHub Secrets-də: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`. Heç vaxt kodda və ya söhbətdə yazma. `SUPABASE_*` mühit dəyişənləri olanda `main.py` vəziyyəti bazada saxlayır, yoxdursa yerli `seen.json` ilə işləyir.
