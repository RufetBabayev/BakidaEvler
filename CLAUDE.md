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
3. Supabase bazası + GitHub Actions ilə avtomatik işləmə — BİTDİ (ilk əl ilə işləmə 2026-11-19: 75 elan bazaya yazıldı, 4m18s)
4. Expo (React Native) tətbiqi — `tetbiq/` — İLK VERSİYA YAZILDI (giriş + siyahı + filtrlər), telefonda sınanmayıb
5. Digər saytlar: tap.az, yeniemlak.az, emlak.az, vipemlak.az, rahatemlak.az, domik.az, korter.az
6. Push bildirişlər — ntfy.sh ilə HAZIRDIR (bax: Mərhələ 6 qeydləri)

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
- GitHub repo: `RufetBabayev/BakidaEvler` (PUBLIC, çünki ~100 dəq/gün iş private repoda pulsuz 2000 dəq/ay limitinə sığmır). İş axını: `.github/workflows/toplayici.yml`, hər 15 dəqiqə, 24 saat. Commit e-poçtu: GitHub noreply (şəxsi e-poçtu commit-ə yazma).
- Gizli açarlar GitHub Secrets-də: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`. Heç vaxt kodda və ya söhbətdə yazma. `SUPABASE_*` mühit dəyişənləri olanda `main.py` vəziyyəti bazada saxlayır, yoxdursa yerli `seen.json` ilə işləyir.

## Mərhələ 4 qeydləri (tətbiq)

- Expo SDK 58, TypeScript. Expo API-ləri dəyişib: kod yazmazdan əvvəl `tetbiq/AGENTS.md`-ə və https://docs.expo.dev/llms.txt-ə bax, paketləri `npx expo install` ilə qur.
- Giriş: Supabase Auth (e-poçt+parol). Qeydiyyat söndürülməlidir; istifadəçini sahibi Supabase panelində əl ilə yaradır. Oxuma siyasəti: `elanlar` cədvəli yalnız `authenticated` üçün SELECT (schema.sql-in sonu).
- Ekranlar: `src/LoginScreen.tsx`, `src/ListScreen.tsx` (satıcı filtri: hamısı / ev sahibi / şübhəli / makler; otaq, qiymət, rayon). Elana toxunanda `link` açılır.
- `src/config.ts`: ictimai publishable açar (gizli deyil). service_role açarını tətbiqə qoyma.
- Qalanlar: telefonda sınaq (Expo Go), APK (EAS Build), push bildirişlər (mərhələ 6).

## Mərhələ 5 qeydləri (çoxlu sayt)

- Scraper interfeysi: bina.az `fetch` + `fetch_incremental` (ID skanı). List əsaslı saytlar `fetch_latest(known_ids, min_new_id, reveal_phone, log) -> (elanlar, xetalar, max_id)` verir; ortaq köməkçilər `scrapers/common.py`. Yeni sayt: `scrapers/<sayt>.py` + `main.py`-dakı `SCRAPERS` siyahısı.
- Satıcı açarı `satıcı_açar` ("tel:<maskalı telefon>" bina.az, "tap:<istifadəçi ID>" tap.az) makler sayını bütün saytlar üzrə hesablayır (`makler.py`).
- **tap.az** (hazırdır): GraphQL `https://tap.az/graphql`, Bakı + satış filtri (mənzil: property 740/3722, həyət evi: 750/3869). Telefon tam gizlidir ("+994 •••"). Satıcı tipi: mağaza hesabı = vasitəçi, şəxsi hesab = mülkiyyətçi; amma çox elanlı şəxsi hesablar (satıcının_elan_sayı ≥ 5) "şübhəli makler" olur. Mərtəbə yoxdur.
- **rahatemlak.az** (hazırdır): HTML (BeautifulSoup), `/search-property?ad_type=1&city=6&property_type=8|3`. Satıcı tipi + paylaşılma vaxtı var. Telefon çox maskalıdır `(055) 220-●●-●●`, ona görə satıcı açarı telefon+ad (`tn:`) olur; "mülkiyyətçi" yazıb agentlik adı ilə yazanlar "şübhəli makler" çıxır.
- **vipemlak.az** (hazırdır): HTML, `/yeni-tikili`, `/kohne-tikili`, `/heyet-evi-villa`. Satıcı tipi YOXDUR (`naməlum`), satıcı hesab ID-si (`vip:<id>`) ilə tanınır; eyni satıcının 3+ elanı = makler. Bakı rayonları adla süzülür.
- **yeniemlak.az** (hazırdır): HTML, `/elan/axtar?emlak=1|2&elan_nov=1&seher[]=7`. Satıcı tipi var. Telefon şəkil kimi (URL-də nömrə var) göstərilir — bu saytın qorumasıdır, OXUMURUQ; telefon boş, satıcı ad ilə tanınır (`ye:<ad>`). ID-lər tam yaranma sırasında deyil, ona görə "yeni" = görülməyib + şəkil tarixi ≥ dünən.
- **domik.az** (hazırdır): HTML, `/elanlar/satis/menzil|heyet-evi`. Satıcı tipi, ad, maskalı telefon, yerləşdirmə/yenilənmə vaxtı var.
- **emlak.az**: 403 verir (bloklayır) — keçilmir. **korter.az**: yeni tikili/developer kataloqudur (ev sahibi elanı yoxdur), mənası yoxdur — əlavə olunmadı.
- `makler_nəticə`: "ev sahibi" / "makler" / "şübhəli makler" / "naməlum" (saytda satıcı tipi yoxdur və elan sayı < 3).

## Performans və etibarlılıq (2026-11-19)

- Problem: ilk işləmə bütün saytların ~400 elan detalını ARDICIL çəkirdi (2-4 s fasilə) = 20+ dəq; loq da görünmürdü (stdout bufer). `seen.json` problem deyildi: Supabase rejimində vəziyyət bazadadır (`toplayici_veziyyet` + `elanlar`), işləmələr arasında saxlanır. Köhnə elanların detalı onsuz da açılmırdı (siyahıdan ID/keşlə tanınır).
- Həll: saytlar PARALEL (ThreadPoolExecutor, hər saytın öz `Client`-i → eyni sayta eyni anda 1 sorğu, 2-4 s fasilə qalır); hər sayta 180 s vaxt limiti (`SITE_TIME_LIMIT`), bitəndə "VAXT BİTDİ", topladığı saxlanır, qalanı növbəti işləmədə davam edir (ID-lər irəliləmir); timeout (10 s connect, 20 s read), şəbəkə xətasında max 2 retry; 403/429/503/Cloudflare/captcha → "BLOKLANDI: status X", sayt dayanır, digərləri davam edir. `python -u` + `PYTHONUNBUFFERED=1`, `timeout-minutes: 10`, `concurrency` var.
- Sayt ortalama vaxtları (adi işləmə, yerli ölçü): rahatemlak ~10 s, vipemlak ~10 s, yeniemlak ~4 s, domik ~12 s, tap ~40 s, bina 1-3 dəq (ID skanı, yeni ID sayından asılıdır).
- Mərkəzləşdirilmiş HTTP kodu: `scrapers/common.py` (`Client`, `Dayandi`/`Bloklandi`/`VaxtBitdi`). Yeni scraper `Client(BASE)` işlətməlidir və `Dayandi`-ni tutub `errors.append(str(e))` etməlidir.

## Avtomatik işləmə: öz-özünü davam etdirən zəncir (2026-11-19)

- GitHub `schedule` (cron) bu repoda 2+ saat heç vaxt işə düşmədi (yalnız əl ilə işə salınanlar işlədi; :00/:15 yerinə 7,22,37,52 də kömək etmədi).
- Həll: `.github/workflows/toplayici.yml` bir işləmədə ~5 saat 40 dəq ərzində hər 15 dəqiqədən bir `python -u main.py` çağırır, sonda `gh workflow run` ilə növbəti işləməni özü başladır (GITHUB_TOKEN-in `workflow_dispatch` etməsinə icazə var, `permissions: actions: write`). `concurrency` işləmələrin üst-üstə düşməsinin qarşısını alır. `schedule` ehtiyat kimi qalır.
- Zənciri dayandırmaq: Actions-da işləyən "toplayici"-ni Cancel et (Cancel zamanı növbəti işləmə başlamır). Yenidən başlatmaq: "Run workflow".
- Risk: zəncir qırılsa (GitHub nasazlığı, əl ilə cancel), yeni elan yığılmır; təkrar "Run workflow" lazımdır. Zəncir qırılması üçün xəbərdarlıq hələ yoxdur.

## Mərhələ 6 qeydləri (bildirişlər)

- Real push: tətbiq girişdən sonra bildiriş icazəsi istəyir (Android 13+ pəncərəsi), Expo push tokenini `push_tokenlar` cədvəlinə yazır (`tetbiq/src/push.ts`). Toplayıcı (`toplayici/notify.py`) yeni **"ev sahibi"** elanı tapanda bütün tokenlərə https://exp.host/--/api/v2/push/send ilə göndərir (FCM üzərindən). Bildiriş tətbiqin quraşdırılmış (APK) versiyasında işləyir, Expo Go-da yox.
- Qaydalar: yalnız `makler_nəticə == "ev sahibi"`, yerləşdirmə tarixi (varsa) 24 saatdan köhnə deyil, bazaya uğurla yazılıb. Bir işləmədə 5-dən çox olarsa bir ümumi bildiriş. `DeviceNotRegistered` tokenlər silinir.
- FCM qurulumu (bir dəfəlik, sahibi edir): Firebase layihəsi, Android tətbiqi `az.bakidaevler`, `google-services.json` -> `tetbiq/` + `app.json` `android.googleServicesFile`; Firebase service account açarı (gizli, repoya YAZMA) EAS-ə yüklənir (expo.dev -> Credentials -> FCM V1).
- 30 günlük təmizlik: hər işləmənin sonunda `db.cleanup(30)` köhnə elanları silir.
- Tətbiq `AppState` "active" olanda siyahını avtomatik yeniləyir.
- Workflow dəyişikliyi və yeni kod işləyən zəncirə təsir etmir: zənciri Cancel edib yenidən "Run workflow" etmək lazımdır.
- Ən son (2026-11-19) ntfy.sh ilə sınaq yolu atıldı (texniki olmayan istifadəçi üçün çətin idi).
